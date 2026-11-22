#!/usr/bin/env python3
"""Lagar dei tre nedlastingane frå repoet – éin for kvart program:

    dist/SNOWMAN-snodjupne.zip   til tråkkemaskinene (innhaldet i pc/, berre versjonsmapper som kan køyrast)
    dist/SNOWMAN-Base.zip        til Raspberry Pi-en ved antenna: berre korreksjonane (innhaldet i base/)
    dist/SNOWMAN-Kontor.zip      til kontor-PC-en på anlegget: kontorsida og anleggsdata (innhaldet i kontor/)

Alle programma ligg i same repo (felles testing av samspelet). Oppdateringa i kvart program hentar berre si
eiga mappe (pc/, base/ eller kontor/), så pakkane blir haldne oppdaterte kvar for seg.

Bruk:  python verktoy/lag-pakkar.py [utmappe]      (standard: dist/)
Køyrer òg automatisk på GitHub ved kvar push til main (.github/workflows/pakkar.yml).
"""
import re
import sys
import zipfile
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
HOPP_OVER = {"data", ".venv", "__pycache__", ".pytest_cache", "test"}
HOPP_OVER_FILER = {".DS_Store"}
HOPP_OVER_ENDINGAR = {".pyc", ".local.json"}


def _skal_med(rel: Path) -> bool:
    if HOPP_OVER & set(rel.parts):
        return False
    if rel.name in HOPP_OVER_FILER or any(rel.name.endswith(e) for e in HOPP_OVER_ENDINGAR):
        return False
    if rel.name == "config.json" or rel.name.startswith("ntrip-config"):
        return False  # lokale innloggingar skal aldri med
    return True


def _versjon(fil: Path, mønster: str) -> str:
    m = re.search(mønster, fil.read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def _skriv(z: zipfile.ZipFile, kjelde: Path, mål: str) -> int:
    n = 0
    for f in sorted(kjelde.rglob("*")):
        rel = f.relative_to(kjelde)
        if f.is_file() and _skal_med(rel):
            z.write(f, f"{mål}/{rel.as_posix()}")
            n += 1
    return n


def lag_snodjupne(ut: Path) -> Path:
    pc = ROT / "pc"
    appar = sorted(d.name for d in pc.iterdir() if (d / "start_snowman.py").exists())
    versjon = _versjon(pc / appar[-1] / "snowman_pc.py", r'VERSION\s*=\s*"([^"]+)"')
    namn = "SNOWMAN-snodjupne"
    zp = ut / f"{namn}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        n = 0
        for f in sorted(pc.iterdir()):
            if f.is_file() and _skal_med(Path(f.name)):
                z.write(f, f"{namn}/{f.name}")
                n += 1
        for a in appar:  # dei gamle prototypane (v1.2–v1.5) er ikkje med
            n += _skriv(z, pc / a, f"{namn}/{a}")
        z.write(ROT / "LICENSE", f"{namn}/LICENSE")
    print(f"{zp.name}: v{versjon}, {n + 1} filer")
    return zp


def lag_base(ut: Path) -> Path:
    base = ROT / "base"
    versjon = _versjon(base / "v1.0" / "konfig.py", r'VERSION\s*=\s*"([^"]+)"')
    namn = "SNOWMAN-Base"
    zp = ut / f"{namn}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        n = _skriv(z, base, namn)
        z.write(ROT / "LICENSE", f"{namn}/LICENSE")
        z.writestr(f"{namn}/LES-MEG.txt", (
            "SNOWMAN Base – RTK-base og NTRIP-caster (berre korreksjonane)\n\n"
            "Tilrådd: Raspberry Pi ved antenna:  bash v1.0/installasjon/installer-linux.sh\n"
            "Windows (fast drift):  pakk ut utanfor OneDrive, opne v1.0 og dobbeltklikk INSTALLER-WINDOWS.bat\n"
            "NAS (Docker):  sjå v1.0/LES-MEG.md, kapitlet «SNOWMAN Base på NAS»\n\n"
            "Statusside: http://localhost:8780   Oppsett: http://localhost:8780/oppsett/ (lag administrator første gong)\n"
            "Full rettleiing: v1.0/LES-MEG.md\n\n"
            "Kontorsida og anleggsdata er SNOWMAN Kontor (eiga nedlasting, på ein PC). Programmet til tråkkemaskinene\n"
            "heiter SNOWMAN snødjupne og er òg ei eiga nedlasting.\n"
        ))
    print(f"{zp.name}: v{versjon}, {n + 2} filer")
    return zp


def lag_kontor(ut: Path) -> Path:
    kontor = ROT / "kontor"
    versjon = _versjon(kontor / "v1.0" / "konfig.py", r'VERSION\s*=\s*"([^"]+)"')
    namn = "SNOWMAN-Kontor"
    zp = ut / f"{namn}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        n = _skriv(z, kontor, namn)
        z.write(ROT / "LICENSE", f"{namn}/LICENSE")
        z.writestr(f"{namn}/LES-MEG.txt", (
            "SNOWMAN Kontor – kontorsida og anleggsserveren (anleggspakkar, forslag, maskinoversikt, AI)\n\n"
            "Windows (fast drift):  pakk ut utanfor OneDrive (t.d. C:\\SNOWMAN-Kontor), opne v1.0 og dobbeltklikk\n"
            "                       INSTALLER-WINDOWS.bat\n"
            "Windows (prøve):  dobbeltklikk START-SNOWMAN-KONTOR.bat i v1.0\n\n"
            "Kontorsida: http://localhost:8790 (lag administrator og ein brukar for maskinene første gong)\n"
            "Maskinene: IP-adressa til PC-en, port 8790 – berre på nettet/wifi på anlegget\n"
            "Full rettleiing: v1.0/LES-MEG.md\n\n"
            "Korreksjonane (NTRIP) er SNOWMAN Base på Raspberry Pi-en – ei eiga nedlasting.\n"
        ))
    print(f"{zp.name}: v{versjon}, {n + 2} filer")
    return zp


def sjekk_bat() -> None:
    """Windows-filene må ha CRLF. Med berre LF les cmd.exe dei feil («'d' is not recognized …»)."""
    feil = []
    for f in list((ROT / "pc").rglob("*.bat")) + list((ROT / "base").rglob("*.bat")) + list((ROT / "kontor").rglob("*.bat")):
        data = f.read_bytes()
        if data.count(b"\n") != data.count(b"\r\n"):
            feil.append(str(f.relative_to(ROT)))
    if feil:
        sys.exit("Stoppa: desse .bat-filene manglar Windows-linjeskift (CRLF): " + ", ".join(feil))


def main() -> None:
    sjekk_bat()
    ut = Path(sys.argv[1]) if len(sys.argv) > 1 else ROT / "dist"
    ut.mkdir(parents=True, exist_ok=True)
    lag_snodjupne(ut)
    lag_base(ut)
    lag_kontor(ut)


if __name__ == "__main__":
    main()
