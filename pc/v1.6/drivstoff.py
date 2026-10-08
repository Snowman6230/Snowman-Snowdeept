# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Drivstoff (manuell registrering) og rapport per prepareringsdøgn.

Drivstoff – «full tank»-metoden:
  Føraren fyller tanken heilt opp og skriv inn liter (og helst timeteljaren på motoren).
  Literane ved ei fylling er det maskina har brukt sidan førre fylling. Då kan SNOWMAN rekne:
    liter per motortime  = liter / (timeteljar no − timeteljar ved førre fylling)
    liter per daa        = liter / preparert areal (frå øktene) i same tidsrom
  Utan timeteljar blir tida med prep på (frå øktene) brukt i staden – merkt «prep-tid».
  Ei fylling som ikkje er heilt full blir lagt saman med neste fulle fylling.
  Første fylling er startpunkt og gir ingen tal.

Rapport: økter, trasear (prosent, snødjupne) og drivstoff for eitt prepareringsdøgn (kl. 12–12).
Demo og simulator er merka TEST og er ikkje med i summane.
"""
import json, math, threading, time, uuid
from pathlib import Path

import numpy as np

from trasear import Local, MAX_GAP_M, MAX_GAP_S, MAX_PREP_SPEED, prep_day_start


def track_stats(pts, width):
    """Køyrd lengd (m), tid med prep (s), areal (m², overlapp tel fleire gonger) og snødjupner for ei økt."""
    if len(pts) < 2:
        return {"dist": 0.0, "secs": 0.0, "area": 0.0, "transport": 0.0, "depths": pts[:, 3][np.isfinite(pts[:, 3])] if len(pts) else np.array([])}
    L = Local(float(np.nanmean(pts[:, 0])), float(np.nanmean(pts[:, 1])))
    x, y = L.xy(pts[:, 0], pts[:, 1])
    d, dt = np.hypot(np.diff(x), np.diff(y)), np.diff(pts[:, 2])
    ok = (d <= MAX_GAP_M) & (dt <= MAX_GAP_S) & (dt >= 0)
    prep = ok & (d <= np.maximum(dt, 0.2) * MAX_PREP_SPEED)   # transport (> 40 km/t) gir ikkje areal eller prep-tid
    dist = float(d[ok].sum())
    dep = pts[:, 3]
    return {"dist": dist, "secs": float(dt[prep].sum()), "area": float(d[prep].sum()) * width,
            "transport": float(d[ok & ~prep].sum()), "depths": dep[np.isfinite(dep)]}


class Drivstoff:
    def __init__(self, path, trasear):
        self.path = Path(path)
        self.tra = trasear  # Trasear-objektet: les øktene
        self.lock = threading.Lock()
        self.items = []
        try:
            self.items = json.loads(self.path.read_text("utf-8")).get("fyllingar", [])
        except FileNotFoundError:
            pass
        except Exception as e:
            print("Kunne ikkje lese drivstoff.json:", e)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fyllingar": self.items}, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)

    def add(self, d, machine=""):
        litres = float(str(d.get("litres", "")).replace(",", "."))
        if not (0 < litres <= 2000):
            raise ValueError("Liter må vere mellom 0 og 2000.")
        hours = d.get("hours")
        hours = None if hours in (None, "") else float(str(hours).replace(",", "."))
        if hours is not None and not (0 <= hours < 200000):
            raise ValueError("Ugyldig timeteljar.")
        t = int(d.get("t") or time.time() * 1000)
        with self.lock:
            prev = [f for f in self.items if f["t"] < t and f.get("hours") is not None]
            if hours is not None and prev and hours < max(prev, key=lambda f: f["t"])["hours"]:
                raise ValueError("Timeteljaren er lågare enn ved førre fylling.")
            f = {"id": uuid.uuid4().hex[:8], "t": t, "litres": round(litres, 1), "hours": hours, "full": bool(d.get("full", True)),
                 "machine": str(d.get("machine") or machine or "")[:40], "note": str(d.get("note") or "")[:120],
                 "registered": time.strftime("%Y-%m-%d %H:%M")}
            self.items.append(f)
            self.items.sort(key=lambda f: f["t"])
            self._save()
            return f

    def delete(self, fid):
        with self.lock:
            self.items = [f for f in self.items if f["id"] != fid]
            self._save()

    def _prep(self, t0_ms, t1_ms):
        """Tid med prep og preparert areal frå ekte økter mellom to tidspunkt."""
        secs = area = 0.0
        for s in self.tra.sessions(t0_ms / 1000.0, t1_ms / 1000.0):
            if s["test"]:
                continue
            st = track_stats(s["pts"], s["width"])
            secs += st["secs"]
            area += st["area"]
        return secs, area

    def computed(self):
        """Fyllingane med utrekna forbruk (nyaste først)."""
        with self.lock:
            items = [dict(f) for f in self.items]
        out, base, acc = [], None, 0.0
        for f in items:
            f["lph"] = f["lpdaa"] = f["hoursUsed"] = f["prepHours"] = f["areaDaa"] = None
            f["hourSource"] = None
            if base is not None:
                acc += f["litres"]
                if f["full"]:
                    secs, area = self._prep(base["t"], f["t"])
                    f["prepHours"] = round(secs / 3600, 2)
                    f["areaDaa"] = round(area / 1000, 1)
                    if f.get("hours") is not None and base.get("hours") is not None and f["hours"] > base["hours"]:
                        f["hoursUsed"], f["hourSource"] = round(f["hours"] - base["hours"], 2), "motor"
                    elif secs > 600:
                        f["hoursUsed"], f["hourSource"] = round(secs / 3600, 2), "prep"
                    if f["hoursUsed"]:
                        f["lph"] = round(acc / f["hoursUsed"], 1)
                    if area > 1000:
                        f["lpdaa"] = round(acc / (area / 1000), 2)
                    f["litresInterval"] = round(acc, 1)
            if f["full"]:
                base, acc = f, 0.0
            out.append(f)
        return list(reversed(out))

    def summary(self, days=30):
        since = (time.time() - days * 86400) * 1000
        c = [f for f in self.computed() if f["t"] >= since and f.get("litresInterval")]
        lit = sum(f["litresInterval"] for f in c)
        hrs = sum(f["hoursUsed"] or 0 for f in c if f["lph"])
        area = sum(f["areaDaa"] or 0 for f in c if f["lpdaa"])
        return {"days": days, "litres": round(sum(f["litres"] for f in self.items if f["t"] >= since), 1),
                "lph": round(sum(f["litresInterval"] for f in c if f["lph"]) / hrs, 1) if hrs else None,
                "lpdaa": round(sum(f["litresInterval"] for f in c if f["lpdaa"]) / area, 2) if area else None}

    # ---------------- rapport ----------------
    def days(self):
        """Prepareringsdøgn som har økter eller fyllingar (nyaste først)."""
        out = set()
        if self.tra.sess.exists():
            for f in self.tra.sess.glob("*.json"):
                try:
                    st = int(f.stem.split("-")[-1]) / 1000.0
                except ValueError:
                    st = f.stat().st_mtime
                out.add(time.strftime("%Y-%m-%d", time.localtime(prep_day_start(st))))
        for f in self.items:
            out.add(time.strftime("%Y-%m-%d", time.localtime(prep_day_start(f["t"] / 1000.0))))
        return sorted(out, reverse=True)

    def report(self, date=None, maps=False):
        t0 = prep_day_start(date=date) if date else prep_day_start()
        t1 = t0 + 86400
        date = time.strftime("%Y-%m-%d", time.localtime(t0))
        sess = []
        tot = {"secs": 0.0, "dist": 0.0, "area": 0.0, "depths": []}
        test = {"secs": 0.0, "dist": 0.0, "area": 0.0, "n": 0}
        for s in sorted(self.tra.sessions(t0, t1), key=lambda s: s["pts"][0, 2]):
            st = track_stats(s["pts"], s["width"])
            dep = st["depths"]
            row = {"id": s["id"], "machine": s["machine"], "test": s["test"], "start": int(s["pts"][0, 2] * 1000),
                   "end": int(s["pts"][-1, 2] * 1000), "prepMin": round(st["secs"] / 60), "km": round(st["dist"] / 1000, 2),
                   "areaDaa": round(st["area"] / 1000, 1), "width": s["width"],
                   "depthAvg": round(float(dep.mean()), 2) if len(dep) and not s["test"] else None,
                   "depthMin": round(float(dep.min()), 2) if len(dep) and not s["test"] else None}
            sess.append(row)
            if s["test"]:
                test["n"] += 1
                for k in ("secs", "dist", "area"):
                    test[k] += st[k]
            else:
                for k in ("secs", "dist", "area"):
                    tot[k] += st[k]
                tot["depths"] += [float(v) for v in dep]
        trs = self.tra.status(t0, t1, cache_s=0, with_map=maps)["status"]
        names = {t["id"]: t for t in self.tra.listing()}
        trasear = []
        for tid, s in trs.items():
            t = names.get(tid)
            if t:
                trasear.append({"id": tid, "name": t["name"], "level": t["level"], "color": t["color"], "target": t.get("target"),
                                "areaDaa": round(s["area"] / 1000, 1), "pct": s["pct"], "pctTest": s["pctTest"],
                                "coveredDaa": round(s["covered"] / 1000, 1), "last": s["last"], "depthAvg": s["depthAvg"],
                                "depthMin": s["depthMin"], "sessions": len([x for x in s["sessions"] if not x["test"]]),
                                "min": round(s.get("secs", 0) / 60), "minTest": round(s.get("secsTest", 0) / 60)})
                if maps and s.get("map"):
                    m = dict(s["map"])
                    try:   # snødjupna i traseen, til fargekartet i rapporten
                        dg, sim = self.tra.depth_grid(m["lat0"], m["lon0"], m["x0"], m["y0"], m["cell"], m["W"], m["H"], t0, t1)
                        m["depth"], m["depthSim"] = enc_depth(dg), sim
                    except Exception:
                        pass
                    trasear[-1]["map"] = m
        trasear.sort(key=lambda r: r["name"].lower())
        comp = {f["id"]: f for f in self.computed()}
        fuel = [comp[f["id"]] for f in self.items if t0 * 1000 <= f["t"] < t1 * 1000]
        d = tot["depths"]
        area = None
        if maps and not trasear:   # ingen trasear: kart over heile området som er køyrt dette døgnet
            try:
                area = self.tra.coverage(t0, t1, include_test=False, max_cells=250_000)
                if area.get("empty"):   # berre demo/test dette døgnet: vis det, tydeleg merka TEST
                    area = dict(self.tra.coverage(t0, t1, include_test=True, max_cells=250_000), onlyTest=True)
                area.pop("passes", None)
                if not area.get("empty"):
                    try:
                        dg, sim = self.tra.depth_grid(area["lat0"], area["lon0"], area["x0"], area["y0"], area["cell"], area["W"], area["H"], t0, t1)
                        area["depth"], area["depthSim"] = enc_depth(dg), sim
                    except Exception:
                        pass
                    area["parts"] = split_area(area)
            except Exception as e:
                area = {"empty": True, "error": str(e)}
        return {
            "area": area,
            "date": date, "from": int(t0 * 1000), "to": int(t1 * 1000), "sessions": sess, "trasear": trasear, "fuel": fuel,
            "total": {"prepMin": round(tot["secs"] / 60), "km": round(tot["dist"] / 1000, 2), "areaDaa": round(tot["area"] / 1000, 1),
                      "litres": round(sum(f["litres"] for f in fuel), 1), "depthAvg": round(sum(d) / len(d), 2) if d else None,
                      "depthMin": round(min(d), 2) if d else None},
            "test": {"n": test["n"], "prepMin": round(test["secs"] / 60), "km": round(test["dist"] / 1000, 2), "areaDaa": round(test["area"] / 1000, 1)},
        }

    def report_csv(self, date=None):
        """Rapporten som CSV (semikolon og desimalkomma – opnar rett i norsk Excel)."""
        r = self.report(date)
        num = lambda v: "" if v is None else str(v).replace(".", ",")
        hm = lambda ms: time.strftime("%H:%M", time.localtime(ms / 1000)) if ms else ""
        L = [f"SNOWMAN rapport;prepareringsdøgn {r['date']} kl. 12 til neste dag kl. 12", ""]
        T = r["total"]
        L += ["SAMLA (utan demo/test)", "Prep-tid (min);Køyrd (km);Areal køyrt (daa);Drivstoff fylt (l);Snødjupne snitt (m);Snødjupne minst (m)",
              ";".join(num(v) for v in (T["prepMin"], T["km"], T["areaDaa"], T["litres"], T["depthAvg"], T["depthMin"])), ""]
        L += ["TRASEAR", "Trasé;Areal (daa);Preparert (%);Preparert (daa);Tid i traseen (min);Sist preparert;Måldjupne (m);Snødjupne snitt (m);Snødjupne minst (m);Økter"]
        for t in r["trasear"]:
            L.append(";".join([t["name"], num(t["areaDaa"]), num(t["pct"]), num(t["coveredDaa"]), num(t["min"]), hm(t["last"]), num(t["target"]),
                               num(t["depthAvg"]), num(t["depthMin"]), str(t["sessions"])]))
        L += ["", "ØKTER", "Økt;Maskin;Start;Slutt;Prep-tid (min);Køyrd (km);Fresbreidd (m);Areal (daa);Snødjupne snitt (m);Snødjupne minst (m);Merknad"]
        for s in r["sessions"]:
            L.append(";".join([s["id"], s["machine"], hm(s["start"]), hm(s["end"]), num(s["prepMin"]), num(s["km"]), num(s["width"]),
                               num(s["areaDaa"]), num(s["depthAvg"]), num(s["depthMin"]), "TEST/DEMO – ikkje med i summen" if s["test"] else ""]))
        L += ["", "DRIVSTOFF", "Tid;Liter;Timeteljar;Full tank;Liter per time;Grunnlag for time;Liter per daa;Merknad"]
        for f in r["fuel"]:
            L.append(";".join([hm(f["t"]), num(f["litres"]), num(f["hours"]), "ja" if f["full"] else "nei", num(f["lph"]),
                               {"motor": "timeteljar", "prep": "prep-tid"}.get(f["hourSource"], ""), num(f["lpdaa"]), f["note"].replace(";", ",")]))
        return "﻿" + "\r\n".join(L) + "\r\n"


# ---------------------------------------------------------------------------------------------
# Automatisk lagring av rapportar til ei mappe (t.d. OneDrive/Google Drive-mappa på PC-en).
# SNOWMAN skriv alltid lokalt – også utan nett. Synkroniseringsprogrammet (OneDrive, Google Drive for skrivebord,
# Dropbox …) lastar filene opp når PC-en har nett (wifi eller mobildata). Ingen passord i SNOWMAN.
# ---------------------------------------------------------------------------------------------
def documents_dir():
    """«Dokument»-mappa til brukaren (på Windows også når ho er flytt til OneDrive)."""
    import os, subprocess
    if os.name == "nt":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('MyDocuments')"],
                               capture_output=True, text=True, timeout=15)
            p = Path(r.stdout.strip())
            if r.stdout.strip() and p.exists():
                return p
        except Exception:
            pass
        return Path.home() / "Documents"
    try:
        r = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=5)
        p = Path(r.stdout.strip())
        if r.stdout.strip() and p.exists() and p != Path.home():
            return p
    except Exception:
        pass
    for n in ("Documents", "Dokumenter", "Dokument"):
        if (Path.home() / n).exists():
            return Path.home() / n
    return Path.home()


_DOCS = []


def default_report_dir():
    if not _DOCS:
        _DOCS.append(documents_dir() / "SNOWMAN-rapportar")
    return _DOCS[0]


def enc_depth(d):
    """Snødjupne-rutenett (m, nan = ikkje målt) som base64 av uint8: verdi = cm/2 (0–5 m), 255 = ikkje målt."""
    import base64
    v = np.full(d.shape, 255, np.uint8)
    ok = np.isfinite(d)
    v[ok] = np.clip(np.round(d[ok] * 50), 0, 250).astype(np.uint8)
    return base64.b64encode(v.tobytes()).decode()


def split_area(a, block_m=60.0, max_parts=4, pad=6):
    """Del trakka område i samanhengande delar (t.d. to bakkar langt frå kvarandre), kvar med sitt eige utsnitt,
    så karta i rapporten blir store nok å lese. Største delen først."""
    import base64
    from collections import deque
    W, H, cell = a["W"], a["H"], a["cell"]
    age = np.frombuffer(base64.b64decode(a["age"]), np.uint8)[: W * H].reshape(H, W)
    cov = age != 255
    b = max(1, int(block_m / cell))
    hb, wb = -(-H // b), -(-W // b)
    pc = np.zeros((hb * b, wb * b), bool)
    pc[:H, :W] = cov
    coarse = pc.reshape(hb, b, wb, b).any(axis=(1, 3))
    lab = np.zeros(coarse.shape, int)
    parts = []
    for r0, c0 in zip(*np.nonzero(coarse)):
        if lab[r0, c0]:
            continue
        n = len(parts) + 1
        lab[r0, c0] = n
        q, cells = deque([(r0, c0)]), []
        while q:
            r, c = q.popleft()
            cells.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < hb and 0 <= cc < wb and coarse[rr, cc] and not lab[rr, cc]:
                        lab[rr, cc] = n
                        q.append((rr, cc))
        rs, cs = [x[0] for x in cells], [x[1] for x in cells]
        parts.append((n, min(rs) * b, (max(rs) + 1) * b, min(cs) * b, (max(cs) + 1) * b))
    out = []
    for n, ra, rb, ca, cb in parts:
        mask = np.kron(lab == n, np.ones((b, b), bool))[:H, :W] & cov
        rr, cc = np.nonzero(mask)
        ra, rb = max(int(rr.min()) - pad, 0), min(int(rr.max()) + pad + 1, H)
        ca, cb = max(int(cc.min()) - pad, 0), min(int(cc.max()) + pad + 1, W)
        sub = np.where(mask[ra:rb, ca:cb], age[ra:rb, ca:cb], 255).astype(np.uint8)
        part = {"W": cb - ca, "H": rb - ra, "cell": cell, "age": base64.b64encode(sub.tobytes()).decode(),
                "area": round(float(mask.sum()) * cell * cell), "onlyTest": a.get("onlyTest", False)}
        if a.get("depth"):
            dep = np.frombuffer(base64.b64decode(a["depth"]), np.uint8)[: W * H].reshape(H, W)
            part["depth"] = base64.b64encode(np.ascontiguousarray(dep[ra:rb, ca:cb]).tobytes()).decode()
            part["depthSim"] = a.get("depthSim", False)
        out.append(part)
    out.sort(key=lambda p: -p["area"])
    return out[:max_parts]


def export_reports(fuel, folder, machine="", days=2, bounds=None):
    """Skriv rapporten (CSV) for dei siste prepareringsdøgna til mappa. Berre filer som er endra blir skrivne på nytt.
    Returnerer (talet på filer skrivne, filnamn)."""
    import re
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tag = re.sub(r"[^A-Za-z0-9ÆØÅæøå_-]+", "-", machine or "").strip("-")
    written, names = 0, []
    for date in fuel.days()[:days]:
        rep = fuel.report(date)
        if not rep["sessions"] and not rep["fuel"]:
            continue
        name = f"SNOWMAN-rapport-{date}" + (f"-{tag}" if tag else "") + ".csv"
        data = fuel.report_csv(date)
        f = folder / name
        names.append(name)
        try:
            if f.exists() and f.read_text("utf-8-sig") == data.lstrip("﻿"):
                continue
        except Exception:
            pass
        tmp = folder / (name + ".tmp")
        tmp.write_text(data, "utf-8")
        tmp.replace(f)
        written += 1
        # same rapport som PDF (kart, trasear, økter, drivstoff) – berre når CSV-en er endra
        try:
            import pdfrapport as PR
            pn = name[:-4] + ".pdf"
            (folder / (pn + ".tmp")).write_bytes(PR.build(fuel.report(date, maps=True), machine, bounds))
            (folder / (pn + ".tmp")).replace(folder / pn)
            names.append(pn)
        except Exception:
            pass
    return written, names
