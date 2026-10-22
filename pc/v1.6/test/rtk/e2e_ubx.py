# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Heile vegen gjennom SNOWMAN med u-blox UBX: falsk ZED-F9P (rover.ubx over TCP, i USB-bitar, sanntid 10× fort) og
falsk caster (base.rtcm3 utan 1019 – banene må kome frå SFRBX). Ingen SNOWMAN_RTK_REFTIME: PC-klokka er 21 år frå
dataa, så motoren må ta GPS-tida frå mottakaren.

Bruk:  python3 e2e_ubx.py            (startar kjeldene og ein eigen SNOWMAN i ei mellombels mappe, skriv resultatet)
"""
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from rtcm import _bits   # noqa: E402
from testubx import rtcm_frames, ubx_split   # noqa: E402

CASTER, RX, HTTP = 2297, 7797, 8797
os.chdir(HERE)
base = [f for f in rtcm_frames(open("base.rtcm3", "rb").read()) if _bits(f[3:], 0, 12) != 1019]
uf, _ = ubx_split(open("rover.ubx", "rb").read())
rover, cur = [], []
for f in uf:
    cur.append(f)
    if f[2:4] == b"\x02\x15":
        rover.append(b"".join(cur) + b"$GNGGA,000000.00,3509.65,N,13936.83,E,1,12,0.8,70.0,M,40.0,M,,*00\r\n")
        cur = []
bep, cur = [], []
for f in base:
    cur.append(f)
    if _bits(f[3:], 0, 12) == 1077:
        bep.append(b"".join(cur))
        cur = []
START = [None]
SPEED = 10.0       # 30 s mellom epokane i dataa → 3 s


def epoch_now():
    return int((time.time() - START[0]) * SPEED / 30.0) if START[0] else -1


def serve(port, pick, ntrip):
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(5)
    while True:
        c, _ = srv.accept()
        if ntrip:
            c.recv(4096)
            c.sendall(b"ICY 200 OK\r\n\r\n")
        sent = -1
        try:
            while True:
                if START[0] is None:
                    START[0] = time.time()
                k = epoch_now()
                if k != sent and k < len(rover):
                    blob = pick(k)
                    i = 0
                    while i < len(blob):                                  # bitar som frå USB/mobilnett
                        n = random.randint(1, 300)
                        c.sendall(blob[i:i + n])
                        i += n
                        time.sleep(0.002)
                    sent = k
                time.sleep(0.05)
        except Exception:
            c.close()


def main():
    work = tempfile.mkdtemp(prefix="snowman-e2e-ubx-")
    app = os.path.join(work, "v1.6")
    shutil.copytree(os.path.join(HERE, "..", ".."), app, ignore=shutil.ignore_patterns("data", ".venv", "test", "__pycache__"))
    os.makedirs(os.path.join(app, "data"))
    json.dump({"serial_port": f"socket://127.0.0.1:{RX}", "caster": "127.0.0.1", "caster_port": CASTER, "mountpoint": "TEST",
               "username": "", "password": "", "rtk_mode": "snowman"}, open(os.path.join(app, "snowman-config.local.json"), "w"))
    threading.Thread(target=serve, args=(CASTER, lambda k: bep[k] if k < len(bep) else b"", True), daemon=True).start()
    threading.Thread(target=serve, args=(RX, lambda k: rover[k], False), daemon=True).start()
    env = dict(os.environ)
    env.pop("SNOWMAN_RTK_REFTIME", None)
    env.pop("SNOWMAN_RTK_NAVFILE", None)
    p = subprocess.Popen([sys.executable, "snowman_pc.py", "--http-port", str(HTTP)], cwd=app, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    res, fixes, seen = None, 0, set()
    try:
        t_end = time.time() + 240
        while time.time() < t_end:
            time.sleep(1)
            try:
                st = json.load(urllib.request.urlopen(f"http://127.0.0.1:{HTTP}/api/status", timeout=3))
            except Exception:
                continue
            m = st.get("motor") or {}
            key = (st.get("last_gga") or "")[:20]
            if st.get("fix") == "RTK FIX" and key not in seen:
                fixes += 1
                seen.add(key)
            res = {"fix": st.get("fix"), "rover_fmt": m.get("rover_fmt"), "rover_obs": m.get("rover_obs"),
                   "base_obs": m.get("base_obs"), "eph_rover": m.get("eph_rover"), "eph": m.get("eph"),
                   "clock_off": m.get("clock_off"), "tdiff": m.get("tdiff"), "motor_fix": m.get("fix"),
                   "motor_float": m.get("float"), "types": m.get("rover_types"), "ubx_bad": m.get("ubx_bad"),
                   "hint": st.get("rtk_hint"), "gga": st.get("last_gga")}
            if (m.get("fix") or 0) >= 20:
                break
        sj = json.load(urllib.request.urlopen(f"http://127.0.0.1:{HTTP}/api/rtksjekk", timeout=10))
        res["feilsok"] = [f"{s.get('status')} {s.get('title')}: {s.get('detail')}" for s in sj.get("steps", [])
                          if s.get("id") in ("motor", "raw", "baseobs", "eph", "fix")]
    finally:
        p.terminate()
        out = p.communicate(timeout=10)[0]
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    errs = [x for x in out.splitlines() if "Traceback" in x or "Error" in x]
    print("Feil i SNOWMAN-loggen:", errs or "ingen")
    ok = res and res["motor_fix"] >= 20 and res["rover_fmt"] == "UBX RAWX" and res["eph_rover"] >= 20 and not errs
    print("E2E UBX:", "OK" if ok else "FEIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
