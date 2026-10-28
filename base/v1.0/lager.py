# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Lager i SNOWMAN Base (SQLite, data/base.db): maskiner, delte målingar, anleggspakker, forslag og forbetringar.

    maskiner      siste hjarteslag frå kvar maskin (versjon, anleggspakke, posisjon, FIX-del)
    maalingar     snødjupne frå maskinene (berre RTK FIX frå kalibrerte maskiner) – deling siste 12 t (v1.8)
    pakkar        versjonar av anleggspakka; éin er aktiv og blir henta av maskinene (kap. 6/16)
    forslag       frå maskinene: ny hindring, merknad eller forbetring av programmet – kontoret godkjenner
    forbetringar  forslag frå forbetringsmotoren (reglar og AI), med status og historikk
    dagstal       eitt samandrag per døgn – grunnlag for trendar og læring
"""
import hashlib
import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS maskiner (id TEXT PRIMARY KEY, namn TEXT, versjon TEXT, pakke TEXT, lat REAL, lon REAL,
  fix INTEGER, fixdel REAL, sist REAL, forst REAL, ip TEXT, ekstra TEXT);
CREATE TABLE IF NOT EXISTS maalingar (id INTEGER PRIMARY KEY AUTOINCREMENT, maskin TEXT, t REAL, lat REAL, lon REAL,
  h REAL, djupne REAL, mottatt REAL);
CREATE INDEX IF NOT EXISTS maalingar_t ON maalingar(t);
CREATE TABLE IF NOT EXISTS pakkar (versjon INTEGER PRIMARY KEY, fil TEXT, sha256 TEXT, storleik INTEGER, dato REAL,
  merknad TEXT, aktiv INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS forslag (id INTEGER PRIMARY KEY AUTOINCREMENT, maskin TEXT, type TEXT, tekst TEXT, lat REAL,
  lon REAL, dato REAL, status TEXT DEFAULT 'ny', svar TEXT);
CREATE TABLE IF NOT EXISTS forbetringar (nokkel TEXT PRIMARY KEY, kategori TEXT, alvor TEXT, tittel TEXT, grunn TEXT,
  tiltak TEXT, kjelde TEXT, forst REAL, sist REAL, tal INTEGER DEFAULT 1, status TEXT DEFAULT 'ny', merknad TEXT);
CREATE TABLE IF NOT EXISTS dagstal (dato TEXT PRIMARY KEY, data TEXT);
"""


class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.pkgdir = self.folder / "anleggspakke"
        self.pkgdir.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.folder / "base.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()

    def q(self, sql, args=(), one=False):
        with self.lock:
            cur = self.db.execute(sql, args)
            rows = [dict(r) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows

    def x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    # ---------- maskiner ----------
    def heartbeat(self, mid, d, ip, max_seats=0):
        """Hjarteslag frå ei maskin. Returnerer (ok, feilmelding)."""
        now = time.time()
        old = self.q("SELECT id FROM maskiner WHERE id=?", (mid,), one=True)
        if old is None and max_seats:
            n = self.q("SELECT COUNT(*) n FROM maskiner", one=True)["n"]
            if n >= max_seats:
                return False, f"Alle {max_seats} maskinplassane er i bruk. Fjern ei maskin på kontorsida først."
        extra = {k: v for k, v in d.items() if k not in ("id", "namn", "versjon", "pakke", "lat", "lon", "fix", "fixdel")}
        if old is None:
            self.x("INSERT INTO maskiner (id, forst) VALUES (?, ?)", (mid, now))
        self.x("UPDATE maskiner SET namn=?, versjon=?, pakke=?, lat=?, lon=?, fix=?, fixdel=?, sist=?, ip=?, ekstra=? "
               "WHERE id=?", (str(d.get("namn") or mid)[:60], str(d.get("versjon") or "")[:20],
                              str(d.get("pakke") or "")[:20], d.get("lat"), d.get("lon"), d.get("fix"),
                              d.get("fixdel"), now, ip, json.dumps(extra, ensure_ascii=False)[:4000], mid))
        return True, ""

    def machines(self):
        rows = self.q("SELECT * FROM maskiner ORDER BY namn")
        for r in rows:
            r["ekstra"] = json.loads(r["ekstra"] or "{}")
            r["age"] = round(time.time() - r["sist"]) if r["sist"] else None
        return rows

    def remove_machine(self, mid):
        return self.x("DELETE FROM maskiner WHERE id=?", (mid,)).rowcount > 0

    # ---------- delte målingar ----------
    def add_measurements(self, mid, points, hours=12):
        """Berre gyldige punkt: RTK FIX (4), kalibrert maskin, ikkje demo, og innanfor delingsvindauget."""
        now = time.time()
        ok, bad = [], 0
        for p in points or []:
            try:
                t = float(p["t"])
                if int(p.get("fix", 0)) != 4 or not p.get("kalibrert", False) or p.get("demo") or p.get("simulert"):
                    bad += 1
                    continue
                if t < now - hours * 3600 or t > now + 600:
                    bad += 1
                    continue
                ok.append((mid, t, float(p["lat"]), float(p["lon"]), float(p.get("h") or 0), float(p["djupne"]), now))
            except (KeyError, TypeError, ValueError):
                bad += 1
        if ok:
            with self.lock:
                self.db.executemany("INSERT INTO maalingar (maskin, t, lat, lon, h, djupne, mottatt) "
                                    "VALUES (?,?,?,?,?,?,?)", ok)
                self.db.commit()
        return len(ok), bad

    def measurements(self, after_id=0, hours=12, exclude=None, limit=5000):
        cut = time.time() - hours * 3600
        sql = "SELECT * FROM maalingar WHERE id>? AND t>=?"
        args = [int(after_id), cut]
        if exclude:
            sql += " AND maskin<>?"
            args.append(exclude)
        rows = self.q(sql + " ORDER BY id LIMIT ?", (*args, int(limit)))
        last = rows[-1]["id"] if rows else int(after_id)
        return rows, last

    def clean(self, keep_days=30):
        self.x("DELETE FROM maalingar WHERE t<?", (time.time() - keep_days * 86400,))

    # ---------- anleggspakke ----------
    def add_package(self, src_path, note="", keep=20):
        h = hashlib.sha256()
        with open(src_path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        row = self.q("SELECT MAX(versjon) v FROM pakkar", one=True)
        v = (row["v"] or 0) + 1
        dst = self.pkgdir / f"anleggspakke-v{v}.zip"
        shutil.move(str(src_path), dst)
        self.x("UPDATE pakkar SET aktiv=0")
        self.x("INSERT INTO pakkar (versjon, fil, sha256, storleik, dato, merknad, aktiv) VALUES (?,?,?,?,?,?,1)",
               (v, dst.name, h.hexdigest(), dst.stat().st_size, time.time(), str(note)[:500]))
        old = self.q("SELECT versjon, fil FROM pakkar WHERE aktiv=0 ORDER BY versjon DESC")
        for r in old[max(0, keep - 1):]:
            (self.pkgdir / r["fil"]).unlink(missing_ok=True)
            self.x("DELETE FROM pakkar WHERE versjon=?", (r["versjon"],))
        return self.package(v)

    def package(self, version=None):
        if version is None:
            return self.q("SELECT * FROM pakkar WHERE aktiv=1", one=True)
        return self.q("SELECT * FROM pakkar WHERE versjon=?", (int(version),), one=True)

    def packages(self):
        return self.q("SELECT * FROM pakkar ORDER BY versjon DESC")

    def activate(self, version):
        if not self.package(version):
            return False
        self.x("UPDATE pakkar SET aktiv=CASE WHEN versjon=? THEN 1 ELSE 0 END", (int(version),))
        return True

    # ---------- forslag frå maskinene ----------
    def add_proposal(self, mid, d):
        kind = d.get("type") if d.get("type") in ("hindring", "merknad", "program", "anna") else "anna"
        cur = self.x("INSERT INTO forslag (maskin, type, tekst, lat, lon, dato) VALUES (?,?,?,?,?,?)",
                     (mid, kind, str(d.get("tekst") or "")[:2000], d.get("lat"), d.get("lon"), time.time()))
        return cur.lastrowid

    def proposals(self, status=None):
        if status:
            return self.q("SELECT * FROM forslag WHERE status=? ORDER BY dato DESC", (status,))
        return self.q("SELECT * FROM forslag ORDER BY dato DESC LIMIT 500")

    def set_proposal(self, pid, status, reply=""):
        return self.x("UPDATE forslag SET status=?, svar=? WHERE id=?", (status, str(reply)[:1000], int(pid))).rowcount

    # ---------- forbetringar ----------
    def upsert_improvement(self, s):
        now = time.time()
        old = self.q("SELECT * FROM forbetringar WHERE nokkel=?", (s["nokkel"],), one=True)
        if old:
            status = old["status"] if old["status"] != "gjort" else "ny"      # kjem att etter at det vart gjort
            self.x("UPDATE forbetringar SET alvor=?, tittel=?, grunn=?, tiltak=?, sist=?, tal=tal+1, status=? "
                   "WHERE nokkel=?", (s["alvor"], s["tittel"], s["grunn"], s["tiltak"], now, status, s["nokkel"]))
        else:
            self.x("INSERT INTO forbetringar (nokkel, kategori, alvor, tittel, grunn, tiltak, kjelde, forst, sist) "
                   "VALUES (?,?,?,?,?,?,?,?,?)", (s["nokkel"], s["kategori"], s["alvor"], s["tittel"], s["grunn"],
                                                   s["tiltak"], s.get("kjelde", "regel"), now, now))

    def improvements(self, include_done=False):
        sql = "SELECT * FROM forbetringar" + ("" if include_done else " WHERE status NOT IN ('gjort','avvist')")
        rows = self.q(sql)
        order = {"høg": 0, "middels": 1, "låg": 2}
        rows.sort(key=lambda r: (order.get(r["alvor"], 3), -r["sist"]))
        return rows

    def set_improvement(self, key, status, note=""):
        return self.x("UPDATE forbetringar SET status=?, merknad=? WHERE nokkel=?",
                      (status, str(note)[:1000], key)).rowcount

    # ---------- dagstal ----------
    def save_day(self, date, data):
        self.x("INSERT OR REPLACE INTO dagstal (dato, data) VALUES (?,?)", (date, json.dumps(data, ensure_ascii=False)))

    def days(self, n=60):
        rows = self.q("SELECT * FROM dagstal ORDER BY dato DESC LIMIT ?", (n,))
        return [{"dato": r["dato"], **json.loads(r["data"])} for r in rows]
