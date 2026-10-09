# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""RTK-feilsøkar: går gjennom heile kjeda frå PC til RTK FIX, steg for steg, og seier kvar det stoppar og kva føraren
skal gjere. Vist på sida /feilsok (Innst. › GNSS › FEILSØK RTK og GNSS-panelet).

Kjeda:  mottakarport → data frå mottakaren → satellittar → mottakarmodus
        → internett → caster → innlogging/mountpoint → korreksjonar → basen → avstand
        → korreksjonar til mottakaren → mottakaren godtek dei → mottakaren brukar dei → RTK FIX → snødjupne

Kvart steg: {"id","title","status": ok|warn|fail|wait|skip, "detail" (tal), "action" (kva gjere)}.
Leverandøruavhengig: tips for bestemte mottakarar (t.d. GeoMax Zenith) står som døme, ikkje som krav.
Ingen hemmelegheiter i rapporten: passord og brukarnamn blir aldri tekne med.
"""
import re
import socket
import time

OK, WARN, FAIL, WAIT, SKIP = "ok", "warn", "fail", "wait", "skip"
QUAL = {"NO DATA": 0, "NO FIX": 0, "GPS": 1, "DGPS": 2, "PPS": 3, "RTK FIX": 4, "RTK FLOAT": 5, "DR": 6,
        "MANUELL": 7, "SIMULERT": 8, "SBAS": 9}
OBS_TYPES = {1001, 1002, 1003, 1004, 1009, 1010, 1011, 1012} | set(range(1071, 1138))   # observasjonar (eldre + MSM)

_NET = {"t": 0, "key": None, "res": None}


def net_check(host, port, timeout=3.0):
    """DNS og TCP-samband til casteren. Mellomlagra i 15 s, så sida kan oppdaterast ofte utan å lage trafikk."""
    key = (host, port)
    if _NET["key"] == key and time.time() - _NET["t"] < 15:
        return _NET["res"]
    res = {"dns": None, "tcp": None, "ip": None, "ms": None, "err": ""}
    if host:
        try:
            res["ip"] = socket.getaddrinfo(host, int(port or 2101), proto=socket.IPPROTO_TCP)[0][4][0]
            res["dns"] = True
        except Exception as e:
            res["dns"], res["err"] = False, str(e)[:160]
        if res["dns"]:
            t0 = time.time()
            try:
                with socket.create_connection((host, int(port or 2101)), timeout=timeout):
                    res["tcp"], res["ms"] = True, int((time.time() - t0) * 1000)
            except Exception as e:
                res["tcp"], res["err"] = False, str(e)[:160]
    _NET.update(t=time.time(), key=key, res=res)
    return res


def _step(steps, sid, title, status, detail="", action=""):
    steps.append({"id": sid, "title": title, "status": status, "detail": detail, "action": action})
    return status


def check(st, cfg, ports=None, net=None, now=None):
    """Vurder alle stega. st = STATE, cfg = CFG (utan å lese passordet), ports = [{"port","desc"}], net = net_check()."""
    now = now or time.time()
    S = []
    port = str(cfg.get("serial_port") or "")
    ports = ports or []
    fix = st.get("fix") or "NO DATA"
    q = QUAL.get(fix, -1)
    gga_age = (now - st["gga_time"]) if st.get("gga_time") else None
    err = str(st.get("last_error") or "")
    sim = bool(st.get("simulated"))

    # ---------- 1. Mottakarporten ----------
    pdesc = next((p.get("desc", "") for p in ports if str(p.get("port", "")).upper() == port.upper()), None)
    if not port:
        _step(S, "port", "Mottakarport vald", FAIL, "Ingen COM-port er vald.",
              "Innst. › GNSS: vel porten til mottakaren (Bluetooth: den UTGÅANDE porten under Windows › Bluetooth › COM-portar).")
    elif port.startswith("socket://") or port.startswith("/dev/") or sim:
        _step(S, "port", "Mottakarport vald", OK, f"{port}" + (" (simulator)" if sim else ""))
    elif ports and pdesc is None:
        _step(S, "port", "Mottakarport vald", FAIL, f"{port} finst ikkje på PC-en. Portar no: " +
              (", ".join(p["port"] for p in ports) or "ingen"),
              "Par mottakaren på nytt i Windows › Bluetooth (eller sett i kabelen), og vel porten som finst.")
    else:
        bt = "bluetooth" in (pdesc or "").lower()
        _step(S, "port", "Mottakarport vald", OK, f"{port}" + (f" – {pdesc}" if pdesc else "") +
              (" (Bluetooth: skal vere den UTGÅANDE porten)" if bt else ""))

    # ---------- 2. Porten open ----------
    if st.get("serial_connected"):
        _step(S, "open", "Porten er open", OK, f"{st.get('port') or port} @ {st.get('baud') or cfg.get('baud')}" +
              (f" · opna på nytt {st['serial_reopens']} gong(er)" if st.get("serial_reopens") else ""))
    else:
        why = err if err.startswith("Serial") else "Porten er ikkje open."
        _step(S, "open", "Porten er open", FAIL, why[:300],
              "Bluetooth: sjå at mottakaren er på og at lampa blir blå (tilkopla). Kople frå alt anna som brukar "
              "mottakaren (Landnova, telefon, anna program) – han tek berre éi tilkopling. Hjelper ikkje det: slå "
              "Bluetooth av/på på PC-en, start mottakaren på nytt, eller par på nytt. SNOWMAN prøver sjølv kvart 2. s.")

    # ---------- 3. Data frå mottakaren ----------
    if not st.get("serial_connected"):
        _step(S, "data", "Posisjon (GGA) frå mottakaren", SKIP, "Ventar på at porten blir open.")
    elif gga_age is None:
        _step(S, "data", "Posisjon (GGA) frå mottakaren", FAIL, "Porten er open, men det har ikkje kome posisjon (GGA).",
              "Slå på GGA-utgang i mottakaren (t.d. Zenith: Settings › Sensor Settings › NMEA Streaming › GGA 1–5 Hz). "
              "Sjekk baud (kabel: same som i mottakaren, t.d. 115200).")
    elif gga_age > 5:
        _step(S, "data", "Posisjon (GGA) frå mottakaren", FAIL, f"Siste posisjon for {gga_age:.0f} s sidan.",
              "Sambandet er truleg brote. SNOWMAN opnar porten på nytt etter 15 s utan data. Start mottakaren på nytt om det varer.")
    else:
        bad = st.get("nmea_bad") or 0
        _step(S, "data", "Posisjon (GGA) frå mottakaren", WARN if bad > 20 else OK,
              f"Ny posisjon for {gga_age:.1f} s sidan" + (f" · {bad} NMEA-linjer med feil sjekksum" if bad else ""),
              "Mange sjekksumfeil: dårleg Bluetooth-samband (avstand/støy) eller feil baud." if bad > 20 else "")

    have_pos = st.get("serial_connected") and gga_age is not None and gga_age <= 5

    # ---------- 4. Satellittar ----------
    sats, hdop = st.get("satellites") or 0, st.get("hdop")
    if not have_pos:
        _step(S, "sats", "Satellittar og sikt", SKIP, "Ventar på posisjon.")
    elif sats < 8 or (hdop is not None and hdop > 2.0):
        _step(S, "sats", "Satellittar og sikt", WARN if sats >= 5 else FAIL, f"{sats} satellittar · HDOP {hdop}",
              "For få satellittar for sikker RTK. Antenna må ha fri sikt mot himmelen (ikkje inne i bil/under tak, "
              "unngå bygningar og tre). Slå på fleire satellittsystem i mottakaren (GPS + GLONASS + Galileo + BeiDou).")
    else:
        _step(S, "sats", "Satellittar og sikt", OK, f"{sats} satellittar · HDOP {hdop}")

    # ---------- 5. Mottakarmodus ----------
    if not have_pos:
        _step(S, "mode", "Mottakaren er rover", SKIP, "Ventar på posisjon.")
    elif fix == "MANUELL":
        _step(S, "mode", "Mottakaren er rover", FAIL, "Mottakaren melder MANUELL (fast/innlagd posisjon) – han står som base eller Static.",
              "Set Working Mode = RTK Rover på mottakaren (t.d. Zenith: 192.168.10.1 › Settings), Save Settings og start han på nytt. "
              "Basen er den faste stasjonen hjå casteren – mottakaren på maskina skal aldri vere base.")
    elif q in (0, -1):
        _step(S, "mode", "Mottakaren er rover", WAIT, f"Status {fix} – mottakaren har ikkje posisjon endå.", "Vent til han har funne satellittar.")
    else:
        _step(S, "mode", "Mottakaren er rover", OK, f"Status {fix}")

    # ---------- 6. Internett og caster ----------
    caster, cport = str(cfg.get("caster") or ""), cfg.get("caster_port") or 2101
    direct = not caster and fix in ("RTK FIX", "RTK FLOAT", "SIMULERT")   # mottakaren hentar korreksjonane sjølv (GSM/radio)
    if direct:
        _step(S, "net", "Internett og caster", SKIP, f"Ingen caster i SNOWMAN – mottakaren har {fix}, så korreksjonane kjem "
              "direkte til han (t.d. GSM/SIM eller radio). Stega for korreksjonar via SNOWMAN gjeld ikkje.")
    elif not caster:
        _step(S, "net", "Internett og caster", FAIL, "Ingen caster er lagt inn.",
              "Innst. › GNSS: legg inn caster, port, mountpoint, brukarnamn og passord (eller la mottakaren hente korreksjonane sjølv).")
    elif st.get("ntrip_connected"):
        _step(S, "net", "Internett og caster", OK, f"{caster}:{cport} – tilkopla" + (f" ({st.get('ntrip_proto')})" if st.get("ntrip_proto") else ""))
    elif net is None:
        _step(S, "net", "Internett og caster", WAIT, f"{caster}:{cport} – testar …")
    elif net.get("dns") is False:
        _step(S, "net", "Internett og caster", FAIL, f"Finn ikkje {caster}: {net.get('err')}",
              "PC-en har ikkje nett, eller casteradressa er feilstava. Sjekk mobil-ruter/Wi-Fi. NB: er PC-en kopla til Wi-Fi-en "
              "til mottakaren (t.d. 192.168.10.x), har han ofte ikkje internett – bruk mobil-ruter eller kabel i tillegg.")
    elif net.get("tcp") is False:
        _step(S, "net", "Internett og caster", FAIL, f"{caster} ({net.get('ip')}) svarar ikkje på port {cport}: {net.get('err')}",
              "Sjekk portnummeret, eller om casteren er nede. Ein brannmur kan stengje porten.")
    else:
        _step(S, "net", "Internett og caster", WARN, f"{caster}:{cport} svarar ({net.get('ms')} ms), men NTRIP er ikkje tilkopla.",
              "Sjå neste steg (innlogging/mountpoint).")

    # ---------- 7. Innlogging og mountpoint ----------
    if not caster:
        _step(S, "auth", "Innlogging og mountpoint", SKIP)
    elif st.get("ntrip_connected"):
        _step(S, "auth", "Innlogging og mountpoint", OK, f"Mountpoint {cfg.get('mountpoint')}")
    elif err.startswith("NTRIP"):
        low = err.lower()
        act = ("Feil brukarnamn/passord, eller kontoen er i bruk på ei anna eining samtidig." if "401" in low or "passord" in low
               else "Mountpointet finst ikkje – bruk HENT MOUNTPOINTS og vel frå lista." if "mount" in low or "404" in low or "kjeldetabell" in low
               else "Sjå feilmeldinga. SNOWMAN prøver igjen av seg sjølv.")
        _step(S, "auth", "Innlogging og mountpoint", FAIL, err[:300], act)
    else:
        _step(S, "auth", "Innlogging og mountpoint", WAIT, "Koplar til …")

    # ---------- 8. Korreksjonar frå casteren ----------
    r = st.get("rtcm") or {}
    types = {int(t) for t in (r.get("types") or {}) if str(t).isdigit()}
    if not st.get("ntrip_connected"):
        _step(S, "rtcm", "Korreksjonar frå basen", SKIP, "Ventar på NTRIP.")
    elif not r.get("frames"):
        _step(S, "rtcm", "Korreksjonar frå basen", WAIT if (st.get("ntrip_wait") or 0) < 15 else FAIL,
              f"Ingen gyldige RTCM-meldingar endå ({st.get('bytes_rtcm', 0)} byte motteke).",
              "Er det framleis 0 etter 30 s: feil mountpoint eller format (må vere RTCM 3).")
    elif r.get("age") is not None and r["age"] > 10:
        _step(S, "rtcm", "Korreksjonar frå basen", FAIL, f"Siste korreksjon for {r['age']:.0f} s sidan.",
              "Mobilnettet heng eller basen har stoppa. SNOWMAN koplar til på nytt automatisk.")
    else:
        ce = r.get("crcErr") or 0
        _step(S, "rtcm", "Korreksjonar frå basen", WARN if ce > 10 else OK,
              f"{r.get('frames')} gyldige meldingar · {ce} CRC-feil · typar {', '.join(sorted(r.get('types') or {}))}",
              "Mange CRC-feil: ustabilt mobilnett." if ce > 10 else "")

    # ---------- 9. Basen sender det som trengst ----------
    if not r.get("frames"):
        _step(S, "base", "Basen: observasjonar og posisjon", SKIP)
    else:
        miss = []
        if not (types & OBS_TYPES):
            miss.append("observasjonar (1004/1012 eller MSM)")
        if r.get("station") is None:
            miss.append("baseposisjon (1005/1006)")
        if miss:
            _step(S, "base", "Basen: observasjonar og posisjon", FAIL, "Manglar: " + ", ".join(miss),
                  "Basen sender ikkje nok til RTK. Vel eit anna mountpoint, eller kontakt den som driv basen.")
        else:
            _step(S, "base", "Basen: observasjonar og posisjon", OK,
                  f"Satellittsystem: {', '.join(r.get('systems') or []) or '?'} · stasjon {r.get('station')}")

    # ---------- 10. Avstand til basen ----------
    km = r.get("baseKm")
    if km is None:
        _step(S, "dist", "Avstand til basen", SKIP, "Kjem når både posisjon og baseposisjon er kjende.")
    elif km > 35:
        _step(S, "dist", "Avstand til basen", FAIL, f"{km} km", "For langt for sikker RTK FIX. Vel ein nærare base eller nettverks-RTK (t.d. CPOS).")
    elif km > 20:
        _step(S, "dist", "Avstand til basen", WARN, f"{km} km", "Langt – FIX kan ta tid og vere ustabil. Under 20 km er best.")
    else:
        _step(S, "dist", "Avstand til basen", OK, f"{km} km")

    # ---------- 11. Korreksjonar til mottakaren ----------
    out, ot = st.get("bytes_rtcm_out") or 0, st.get("rtcm_out_time")
    if not (st.get("serial_connected") and r.get("frames")):
        _step(S, "send", "Korreksjonar sende til mottakaren", SKIP)
    elif not out or (ot and now - ot > 10):
        _step(S, "send", "Korreksjonar sende til mottakaren", FAIL,
              f"{out} byte sendt" + (f", siste for {now - ot:.0f} s sidan" if ot else "") + (f" · {err}" if "send" in err.lower() else ""),
              "SNOWMAN får ikkje skrive til porten. Sambandet er truleg dødt – SNOWMAN opnar porten på nytt; start mottakaren på nytt om det varer.")
    else:
        dr = r.get("dropped") or {}
        _step(S, "send", "Korreksjonar sende til mottakaren", OK, f"{out // 1024} kB sendt" +
              (" · halde tilbake: " + ", ".join(f"{k} ({v})" for k, v in dr.items()) if dr else ""))

    # ---------- 12. Mottakaren godtek korreksjonane ----------
    rx, rxt = str(st.get("rx_text") or ""), st.get("rx_time") or 0
    recent = rxt and now - rxt < 60
    if not (st.get("serial_connected") and out):
        _step(S, "accept", "Mottakaren godtek korreksjonane", SKIP)
    elif recent and re.search(r"ANTENNA,ERROR", rx) and not re.search(r"1033", str(cfg.get("rtcm_drop") or "")):
        _step(S, "accept", "Mottakaren godtek korreksjonane", FAIL, f"Mottakaren svarar «{rx[:70]}» (for {now - rxt:.0f} s sidan).",
              "Han godtek ikkje antennenamnet til basen. Innst. › GNSS: skriv 1008,1033 i «Ikkje send desse RTCM-typane til mottakaren», "
              "LAGRE / KOPLE TIL, og vent 1–2 min.")
    elif recent and "ERROR" in rx.upper():
        _step(S, "accept", "Mottakaren godtek korreksjonane", WARN, f"Mottakaren svarar «{rx[:70]}» (for {now - rxt:.0f} s sidan).",
              "Mottakaren avviser noko av det han får. Sjekk at korreksjonsinngangen hans er rett (t.d. RTK Data Source = Bluetooth/External).")
    else:
        _step(S, "accept", "Mottakaren godtek korreksjonane", OK, "Ingen feilsvar frå mottakaren." + (f" Siste svar: «{rx[:50]}»" if rx else ""))

    # ---------- 13. Mottakaren brukar korreksjonane ----------
    bid = str(st.get("base_id") or "").strip()
    try:
        bidn = int(bid)
    except ValueError:
        bidn = None
    if not have_pos or not out:
        _step(S, "use", "Mottakaren brukar korreksjonane", SKIP)
    elif fix in ("RTK FIX", "RTK FLOAT"):
        _step(S, "use", "Mottakaren brukar korreksjonane", OK, f"Korreksjonsalder {st.get('corr_age')} s · base-ID {bid or '?'}")
    elif bidn is not None and 120 <= bidn <= 158:
        _step(S, "use", "Mottakaren brukar korreksjonane", FAIL,
              f"Mottakaren brukar SBAS-satellitt {bidn} i staden for basen (status {fix}).",
              "Mottakaren les ikkje korreksjonane som korreksjonar. Sjekk på mottakaren: RTK Data Source = same veg som SNOWMAN "
              "(Bluetooth/External), Working Mode = RTK Rover, og «Datalink Status» (t.d. Zenith: Status Info). Sjå òg steget over.")
    elif st.get("corr_age") is None:
        _step(S, "use", "Mottakaren brukar korreksjonane", FAIL, f"Status {fix}, tomt korreksjonsfelt i GGA.",
              "Mottakaren brukar ikkje korreksjonane. Sjekk korreksjonsinngangen på mottakaren (RTK Data Source), og steget over. "
              "Alternativ: la mottakaren hente korreksjonane sjølv (GSM/SIM), eller bruk kabel (External).")
    else:
        _step(S, "use", "Mottakaren brukar korreksjonane", WARN, f"Status {fix} · korreksjonsalder {st.get('corr_age')} s · base-ID {bid}",
              "Mottakaren brukar korreksjonar, men berre som DGPS. Vent, og sjekk sikta.")

    # ---------- 14. RTK-løysing ----------
    if fix == "RTK FIX" or fix == "SIMULERT":
        _step(S, "rtk", "RTK FIX", OK, fix)
    elif fix == "RTK FLOAT":
        _step(S, "rtk", "RTK FIX", WAIT, "RTK FLOAT – mottakaren reknar seg fram mot FIX.",
              "Vent 1–3 min med fri sikt. Varer det: betre sikt, fleire satellittsystem, eller nærare base.")
    else:
        _step(S, "rtk", "RTK FIX", SKIP if not have_pos else FAIL, f"Status {fix}")

    # ---------- 15. Snødjupne ----------
    ds = st.get("depth_status")
    if fix not in ("RTK FIX", "SIMULERT"):
        _step(S, "depth", "Snødjupne", SKIP, "Krev RTK FIX.")
    elif ds == "OK":
        _step(S, "depth", "Snødjupne", OK, f"{st.get('depth')} m")
    else:
        txt = {"OUTSIDE": "Maskina er utanfor terrengmodellen.", "NO_CAL": "Kalibrering manglar.", "NO_ENGINE": "Terrengmotoren manglar.",
               "NEGATIVE": "Negativ snødjupne – sjekk høgdesystem og kalibrering.", "NO_GEOID": "Geoidehøgd manglar.", "NO_HEIGHT": "Inga GNSS-høgd."}
        _step(S, "depth", "Snødjupne", WARN, txt.get(ds, str(ds)), "Innst. › Terreng og Kalibrering.")

    first = next((s for s in S if s["status"] == FAIL), None) or next((s for s in S if s["status"] in (WARN, WAIT)), None)
    return {"steps": S, "first": first["id"] if first else None, "ok": first is None, "fix": fix, "time": time.strftime("%Y-%m-%d %H:%M:%S")}


def report(res, version=""):
    """Rapport som tekst (til å kopiere og sende) – utan passord eller brukarnamn."""
    sym = {OK: "✓", WARN: "!", FAIL: "✗", WAIT: "…", SKIP: "–"}
    lines = [f"SNOWMAN {version} – RTK-feilsøking {res['time']} – status {res['fix']}"]
    for s in res["steps"]:
        lines.append(f"{sym.get(s['status'], '?')} {s['title']}: {s['detail']}".rstrip(": "))
        if s["status"] in (FAIL, WARN) and s["action"]:
            lines.append(f"   → {s['action']}")
    return "\n".join(lines)


if __name__ == "__main__":     # sjølvtest: python3 rtksjekk.py
    now = time.time()
    base = {"serial_connected": True, "port": "COM4", "baud": 115200, "gga_time": now - 0.5, "fix": "GPS", "satellites": 27, "hdop": 0.5,
            "ntrip_connected": True, "ntrip_proto": "NTRIP 1", "bytes_rtcm": 1480730, "bytes_rtcm_out": 911683, "rtcm_out_time": now - 1,
            "rtcm": {"frames": 11580, "crcErr": 0, "types": {"1004": 1, "1006": 1, "1008": 1, "1012": 1, "1033": 1}, "systems": ["GLONASS", "GPS"],
                     "station": 0, "baseKm": 11.25, "age": 0.2},
            "rx_text": "@GNSS,ADVNULLANTENNA,ERROR,1*33", "rx_time": now - 10, "corr_age": None, "base_id": None}
    cfg = {"serial_port": "COM4", "baud": 115200, "caster": "gpsbase.dyndns.org", "caster_port": 2101, "mountpoint": "TH", "rtcm_drop": ""}
    ports = [{"port": "COM3", "desc": "Standard Serial over Bluetooth link (COM3)"}, {"port": "COM4", "desc": "Standard Serial over Bluetooth link (COM4)"}]
    r = check(base, cfg, ports, None, now)
    print(report(r, "test"))
    assert r["first"] == "accept", r["first"]
    r = check(dict(base, fix="RTK FIX", corr_age=1.0, base_id="0000", rx_text="", depth_status="OK", depth=0.9), dict(cfg, rtcm_drop="1008,1033"), ports, None, now)
    assert r["ok"], [s for s in r["steps"] if s["status"] != OK]
    r = check(dict(base, serial_connected=False, last_error="Serial: could not open port 'COM4': FileNotFoundError(2, ...)"), cfg, ports, None, now)
    assert r["first"] == "open", r["first"]
    r = check(dict(base, fix="MANUELL"), cfg, ports, None, now)
    assert r["first"] == "mode"
    r = check(dict(base, ntrip_connected=False, rtcm={}), cfg, ports, {"dns": False, "err": "getaddrinfo failed"}, now)
    assert r["first"] == "net"
    r = check(dict(base, rx_text="", base_id="0121"), dict(cfg, rtcm_drop="1008,1033"), ports, None, now)
    assert r["first"] == "use", r["first"]
    r = check(dict(base, fix="RTK FIX", ntrip_connected=False, rtcm={}, bytes_rtcm_out=0, rx_text="", depth_status="OK", depth=1.0),
              dict(cfg, caster=""), ports, None, now)
    assert r["ok"], [(s["id"], s["status"]) for s in r["steps"] if s["status"] not in (OK, SKIP)]
    print("OK")
