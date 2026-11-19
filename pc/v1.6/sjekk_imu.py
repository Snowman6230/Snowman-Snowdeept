#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Sjekk IMU og meldingar frå mottakaren (t.d. UM981) – roleg, éi linje i sekundet.

Les porten berre (sender aldri noko til mottakaren), som SNOWMAN. Lukk SNOWMAN og UPrecise først –
berre eitt program kan bruke COM-porten om gongen.

Bruk:  SJEKK-IMU.bat            (porten frå SNOWMAN-innstillingane)
       SJEKK-IMU.bat COM3       (vel port sjølv)
       python sjekk_imu.py COM3 [baud]

Kvar linje viser kor mange meldingar som kom det siste sekundet (RTCM, GGA, INSPVAXA) og den siste hellinga frå IMU-en.
Stopp med Ctrl+C.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from helling import crc32_novatel  # noqa: E402

STATUS = {
    "INS_INACTIVE": "ikkje aktiv",
    "INS_ALIGNING": "rettar seg inn – køyr litt",
    "INS_HIGH_VARIANCE": "OK (kursen usikker)",
    "INS_SOLUTION_GOOD": "OK",
    "INS_SOLUTION_FREE": "OK (utan GNSS)",
    "INS_ALIGNMENT_COMPLETE": "OK (køyr litt for full nøyaktigheit)",
}


def oppsett():
    port, baud = None, 115200
    try:
        c = json.loads((HERE / "snowman-config.local.json").read_text("utf-8"))
        port, baud = c.get("serial_port") or None, int(c.get("baud") or 115200)
    except Exception:
        pass
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baud = int(sys.argv[2])
    return port, baud


def les_inspvax(line):
    """(status, roll, pitch, asimut, crc_ok) frå ei #INSPVAXA-linje, eller None."""
    if "*" not in line or ";" not in line:
        return None
    body, crc = line[1:].rsplit("*", 1)
    try:
        ok = int(crc.strip()[:8], 16) == crc32_novatel(body.encode("ascii", "ignore"))
    except ValueError:
        ok = False
    p = body.split(";", 1)[1].split(",")
    if len(p) < 12:
        return None
    f = lambda x: float(x) if x not in ("", None) else None
    try:
        return p[0], f(p[9]), f(p[10]), f(p[11]), ok
    except ValueError:
        return p[0], None, None, None, ok


def main():
    try:
        import serial
    except ImportError:
        print("Manglar pyserial. Køyr INSTALLER-WINDOWS.bat først (eller: pip install pyserial).")
        return 1
    port, baud = oppsett()
    if not port:
        print("Ingen port. Skriv til dømes:  SJEKK-IMU.bat COM3")
        return 1
    sp = serial.serial_for_url(port, baudrate=baud, timeout=0.2, do_not_open=True)
    for k in ("rtscts", "xonxoff", "dsrdtr", "dtr", "rts"):
        try:
            setattr(sp, k, False)
        except Exception:
            pass
    try:
        sp.open()
    except Exception as e:
        print(f"Får ikkje opna {port}: {e}")
        print("Er SNOWMAN eller UPrecise open? Lukk dei og prøv igjen.")
        return 1
    print(f"Les {port} @ {baud} – berre lesing. Stopp med Ctrl+C.\n")
    buf = b""
    n = {"rtcm": 0, "gga": 0, "ins": 0, "crc": 0}
    siste = None
    t0 = start = time.time()
    sett_ins = False
    try:
        while True:
            b = sp.read(4096)
            if b:
                n["rtcm"] += sum(b.count(bytes([0xD3, k])) for k in range(4))  # grovt tal på RTCM-rammer
                buf += b
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("ascii", "ignore").strip()
                    i = line.find("#INSPVAXA")
                    if i >= 0:
                        r = les_inspvax(line[i:])
                        if r:
                            n["ins"] += 1
                            sett_ins = True
                            if not r[4]:
                                n["crc"] += 1
                            siste = r
                    elif "GGA" in line and "$" in line:
                        n["gga"] += 1
                    elif "$command" in line:
                        print("  svar frå kortet:", line[line.find("$command"):][:100])
            if time.time() - t0 >= 1.0:
                t0 = time.time()
                txt = f"{time.strftime('%H:%M:%S')}  RTCM {n['rtcm']:2d}  GGA {n['gga']:2d}  INSPVAXA {n['ins']:2d}"
                if siste:
                    st, roll, pitch, az, ok = siste
                    v = lambda x: "–" if x is None else f"{x:+6.1f}°"
                    txt += (f"  |  IMU: {STATUS.get(st, st)}  fram/bak {v(pitch)}  side {v(roll)}  kurs "
                            f"{'–' if az is None else f'{az % 360:5.1f}°'}" + ("" if ok else "  (CRC-FEIL)"))
                elif time.time() - start > 5 and not sett_ins:
                    txt += "  |  ingen INSPVAXA – skriv «INSPVAXA 1» og «SAVECONFIG» i UPrecise"
                print(txt, flush=True)
                n = {k: 0 for k in n}
    except KeyboardInterrupt:
        print("\nStoppa.")
    finally:
        sp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
