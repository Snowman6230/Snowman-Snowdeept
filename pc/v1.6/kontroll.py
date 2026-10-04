# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Kontroll av snødjupne og terrengmodell.

To typar kontroll:

1. Kontrollmåling: maskina står i ro med RTK FIX. Føraren legg inn kjend snødjupne der antenna står
   (snøsonde, eller 0 på barmark). SNOWMAN lagrar si utrekna snødjupne ved sida av, og avviket.
   Fleire målingar gir eit snittavvik (systematisk feil → høgdeoffset) og spreiing (tilfeldig feil).
   Avviket blir alltid rekna mot gjeldande kalibrering, så gamle målingar er gyldige etter justering.

2. Kontrollpunkt: kjend koordinat (UTM) og kjend terrenghøgd (NN2000), t.d. frå landmålar.
   Samanliknar terrengmodellen direkte med punktet – utan GNSS. Avslører feil i modellen
   (forskyving, feil høgdesystem, gammal modell).

Data blir lagra i data/kontroll.json og høyrer til anlegget.
"""
import json, math, threading, time, uuid
from pathlib import Path


class Kontroll:
    def __init__(self, path, terrain_lib, utm_inverse):
        self.path = Path(path)
        self.terr = terrain_lib
        self.utm_inverse = utm_inverse
        self.lock = threading.Lock()
        self.data = {"points": [], "checks": []}
        try:
            self.data.update(json.loads(self.path.read_text("utf-8")))
        except FileNotFoundError:
            pass
        except Exception as e:
            print("Kunne ikkje lese kontroll.json:", e)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)

    # --- kontrollmålingar ---
    @staticmethod
    def diff_now(c, cfg):
        """Avvik (SNOWMAN − kjend) rekna med gjeldande antennehøgd og høgdeoffset."""
        adj = c["raw"] - (float(cfg.get("antZ", 0)) - c["antZ"]) - (float(cfg.get("zOff", 0)) - c["zOff"])
        return adj - c["known"]

    def add_check(self, state, cfg, known, note="", sim_truth=None):
        if state.get("fix") != "RTK FIX":
            raise ValueError("Krev RTK FIX. Vent til fix er stabil.")
        det = state.get("depth_detail") or {}
        ter = state.get("terrain")
        if not ter or "raw" not in det:
            raise ValueError("Ingen terrengmodell eller utrekning her. Sjå status for snødjupne.")
        if not cfg.get("calibrated"):
            raise ValueError("Lagre kalibreringa først (Innst. › Kalibrering).")
        known = float(known)
        if not (0 <= known <= 15):
            raise ValueError("Kjend snødjupne må vere mellom 0 og 15 m.")
        c = {"id": uuid.uuid4().hex[:8], "t": time.strftime("%Y-%m-%d %H:%M"), "lat": state.get("lat"), "lon": state.get("lon"),
             "known": known, "raw": det["raw"], "H": det.get("H"), "terrain": det.get("terrain"),
             "antZ": float(cfg.get("antZ", 0)), "zOff": float(cfg.get("zOff", 0)),
             "layer": ter.get("layer"), "layerName": ter.get("name"), "note": str(note)[:120],
             "simulated": bool(state.get("simulated"))}
        if sim_truth is not None:
            c["simTruth"] = round(float(sim_truth), 3)
        with self.lock:
            self.data["checks"].append(c)
            self._save()
        return c

    def delete_check(self, cid):
        with self.lock:
            self.data["checks"] = [c for c in self.data["checks"] if c["id"] != cid]
            self._save()

    def stats(self, cfg):
        d = [self.diff_now(c, cfg) for c in self.data["checks"]]
        if not d:
            return {"n": 0}
        n = len(d); mean = sum(d) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1)) if n > 1 else None
        s = {"n": n, "mean": round(mean, 3), "sd": None if sd is None else round(sd, 3), "maxAbs": round(max(abs(x) for x in d), 3)}
        # Forslag om justering: minst 3 målingar, systematisk avvik over 3 cm og større enn spreiinga
        s["suggest"] = n >= 3 and abs(mean) >= 0.03 and (sd is None or abs(mean) > sd)
        return s

    def apply_offset(self, cfg):
        s = self.stats(cfg)
        if not s.get("suggest"):
            raise ValueError("For få eller for sprikande kontrollmålingar til å justere (krev minst 3, og at avviket er systematisk).")
        # Snødjupna er for stor med «mean» → auk høgdeoffset like mykje
        cfg["zOff"] = round(float(cfg.get("zOff", 0)) + s["mean"], 3)
        return cfg["zOff"], s["mean"]

    # --- kontrollpunkt ---
    def add_point(self, name, E, N, zone, h):
        name = (name or "").strip()[:60] or "Kontrollpunkt"
        E, N, zone, h = float(E), float(N), int(zone), float(h)
        if zone not in (32, 33, 35):
            raise ValueError("UTM-sone må vere 32, 33 eller 35.")
        if not (100000 < E < 900000 and 6000000 < N < 8000000):
            raise ValueError("Koordinatane ser ikkje ut som UTM i Noreg (austing ca. 100 000–900 000, nording ca. 6–8 mill.).")
        p = {"id": uuid.uuid4().hex[:8], "name": name, "E": E, "N": N, "zone": zone, "h": h, "created": time.strftime("%Y-%m-%d %H:%M")}
        with self.lock:
            self.data["points"].append(p)
            self._save()
        return p

    def delete_point(self, pid):
        with self.lock:
            self.data["points"] = [p for p in self.data["points"] if p["id"] != pid]
            self._save()

    def point_status(self, p, state=None):
        lat, lon = self.utm_inverse(p["E"], p["N"], p["zone"])
        m = self.terr.height(lat, lon) if self.terr else None
        out = dict(p, lat=lat, lon=lon, model=None, diff=None, layerName=None, dist=None)
        if m:
            out.update(model=round(m["h"], 3), diff=round(m["h"] - p["h"], 3), layerName=m["name"])
        if state and state.get("lat") is not None:
            mlat = 111320.0; mlon = mlat * math.cos(math.radians(lat))
            out["dist"] = round(math.hypot((state["lat"] - lat) * mlat, (state["lon"] - lon) * mlon), 1)
        return out

    def listing(self, cfg, state=None):
        with self.lock:
            checks = [dict(c, diff=round(self.diff_now(c, cfg), 3)) for c in self.data["checks"]]
            points = [self.point_status(p, state) for p in self.data["points"]]
        return {"checks": checks[::-1], "points": points, "stats": self.stats(cfg)}
