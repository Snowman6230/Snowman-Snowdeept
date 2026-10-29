# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Automatisk portval for Bluetooth (v1.6.113) – utan ekte portar: portlista og lyttinga blir simulerte.
Køyr frå pc/v1.6:  python3 test/testautoport.py   Venta: «ALT OK»."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import snowman_pc as P
from rtcm import crc24q

def frame(payload):
    h = bytes([0xD3, len(payload) >> 8, len(payload) & 0xFF]) + payload
    return h + crc24q(h).to_bytes(3, "big")

ok = True
def check(name, cond):
    global ok
    print(("OK   " if cond else "FEIL ") + name)
    ok &= bool(cond)

rt = frame(bytes([0x3E, 0xC0]) + bytes(20))           # type 1004-liknande, gyldig CRC
check("RTCM-rammer blir talde", P._rtcm_frames(b"$GPGGA,x\r\n" + rt + b"\x00\xd3\x00" + rt) == 2)
check("øydelagd ramme blir ikkje talt", P._rtcm_frames(rt[:-1] + b"\x00") == 0)

saved = []
P.save_cfg = lambda: saved.append(dict(P.CFG))
P.bt_ports = lambda: [("COM3", "Standard Serial over Bluetooth link (COM3)", "BTHENUM\\X"),
                      ("COM6", "Standard Serial over Bluetooth link (COM6)", "BTHENUM\\Y"),
                      ("COM7", "Standard Serial over Bluetooth link (COM7)", "BTHENUM\\Z"),
                      ("COM1", "Kommunikasjonsport (COM1)", "ACPI\\PNP0501")]
probe = {"COM3": (0, 0, 0), "COM6": (25, 0, 9000), "COM7": (0, 12, 800)}
tried = []
def fake_probe(d, sek=5.0):
    tried.append(d); return probe.get(d)
P._probe_port = fake_probe
P.CFG["rtk_mode"] = "snowman"

P.CFG["serial_port"] = "COM4"; P.AUTOPORT["last_try"] = 0
r = P.autoport_try("COM4 finst ikkje")
check("COM4 borte → byter til COM6 (RTCM) når RTK blir rekna i SNOWMAN", r == "COM6" and P.CFG["serial_port"] == "COM6")
check("ikkje-Bluetooth-port (COM1) blir ikkje prøvd", "COM1" not in tried)
check("nytt val blir lagra", saved and saved[-1]["serial_port"] == "COM6")
check("bytet står i STATE til feilsøkaren", P.STATE.get("serial_autoport", {}).get("til") == "COM6")

check("ikkje ny leiting før det har gått 45 s", P.autoport_try("igjen") is None)

P.CFG["rtk_mode"] = "mottakar_sjolv"; P.CFG["serial_port"] = "COM9"; P.AUTOPORT["last_try"] = 0
check("mottakaren reknar sjølv → vel porten med NMEA (COM7)", P.autoport_try("test") == "COM7")

P.CFG["rtk_mode"] = "snowman"; P.CFG["serial_port"] = "COM1"; P.AUTOPORT["last_try"] = 0
check("vald port er kabel/USB → ingen leiting", P.autoport_try("test") is None and P.CFG["serial_port"] == "COM1")

P.CFG["serial_port"] = "socket://127.0.0.1:7777"; P.AUTOPORT["last_try"] = 0
check("simulator → ingen leiting", P.autoport_try("test") is None)

P.CFG["serial_port"] = "COM4"; P.CFG["auto_port"] = False; P.AUTOPORT["last_try"] = 0
check("auto_port av → ingen leiting", P.autoport_try("test") is None and P.CFG["serial_port"] == "COM4")
P.CFG["auto_port"] = True

probe = {"COM3": (0, 0, 0), "COM6": (0, 0, 0), "COM7": None}; P.AUTOPORT["last_try"] = 0
check("ingen port sender → blir verande", P.autoport_try("test") is None and P.CFG["serial_port"] == "COM4")

print("ALT OK" if ok else "FEIL")
sys.exit(0 if ok else 1)
