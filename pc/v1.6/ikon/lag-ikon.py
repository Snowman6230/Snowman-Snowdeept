#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Lagar SNOWMAN-ikona og logoen frå éi kjelde, så dei kan haldast like vidare i utviklinga.

Ikonet: kvite fjelltoppar (same form som logoen i førarskjermen) over ei preparert løype, og tråkkemaskina sett
ovanfrå (same teikning som på kartet: grått skjer med venger, belte, raudt førarhus, raud fres og gul finisher).
Små storleikar (16–32 px) får ei forenkla utgåve utan småting, så ikonet er tydeleg på skrivebordet og i oppgåvelinja.

Skriv:
  snowman.svg            hovudikon (512 × 512), kjeldefil
  snowman-enkel.svg      forenkla ikon for små storleikar
  snowman-logo.svg       logo med tekst (fjelltoppar + SNOWMAN + by Alpindata) til dokument, nettside o.l.
  snowman-256.png, snowman-512.png, snowman.ico (16–256 px)   – brukt av snarvegar på Windows og Linux
  ../vendor/snowman-icon.png (64 px)                           – ikonet i nettlesarfana

Bruk (berre ved utvikling – krev Playwright/Chromium og Pillow):  python3 lag-ikon.py
Fargar (sjå også docs/LOGO.md): natt #0b2a44 → #15507c, snø #ffffff/#dcecf7, maskin #d42c2c, skjer #8d9ba5,
belte #1a252d, finisher #f2c230, logo-tekst #ffffff og #8cc8f0.
"""
import asyncio, io, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Fjelltoppane frå logoen (viewBox 120 × 30) – same form som i førarskjermen
PEAKS = "M14 30 L46 2 L66 20 L74 13 L104 30 Z"
PEAK_CUT = "M33 14 L39 17 L46 11 L52 17 L57 14 M68 18 L74 16 L80 19"


def groomer(detail=True):
    """Tråkkemaskina ovanfrå, front opp, i eit felt på 200 × 330 (x 0–200)."""
    p = []
    # spor bak maskina (preparert løype)
    p.append('<rect x="22" y="250" width="156" height="90" fill="#cfe3f2"/>')
    if detail:
        p.append('<g stroke="#b3cfe4" stroke-width="3">' + "".join(f'<line x1="{x}" y1="252" x2="{x}" y2="340"/>' for x in range(34, 178, 12)) + "</g>")
    # skyvearmar
    p.append('<path d="M70 92 L60 60 M130 92 L140 60" stroke="#4a5862" stroke-width="10" stroke-linecap="round"/>')
    # skjer med venger
    p.append('<path d="M6 42 L44 18 L156 18 L194 42 L186 62 L150 44 L50 44 L14 62 Z" fill="#8d9ba5" stroke="#e6edf1" stroke-width="4" stroke-linejoin="round"/>')
    if detail:
        p.append('<g stroke="#62707a" stroke-width="3">' + "".join(f'<line x1="{x}" y1="22" x2="{x}" y2="41"/>' for x in range(60, 145, 14)) + "</g>")
    # belte
    for x in (24, 142):
        p.append(f'<rect x="{x}" y="82" width="34" height="150" rx="12" fill="#1a252d" stroke="#5d6f7b" stroke-width="3"/>')
        if detail:
            p.append('<g stroke="#5a6b76" stroke-width="4">' + "".join(f'<line x1="{x + 5}" y1="{y}" x2="{x + 29}" y2="{y}"/>' for y in range(94, 226, 11)) + "</g>")
    # karosseri og førarhus
    p.append('<path d="M66 76 H134 L144 92 V214 L132 230 H68 L56 214 V92 Z" fill="#d42c2c" stroke="#7a1010" stroke-width="4" stroke-linejoin="round"/>')
    p.append('<rect x="68" y="84" width="64" height="78" rx="10" fill="#ec5048"/>')
    p.append('<path d="M72 90 H128 L122 108 H78 Z" fill="#1d3a4f" stroke="#a8d4ee" stroke-width="2"/>')
    p.append('<rect x="80" y="116" width="40" height="38" rx="6" fill="#f47a72"/>')
    if detail:
        p.append('<g stroke="#8f1717" stroke-width="3">' + "".join(f'<line x1="76" y1="{y}" x2="124" y2="{y}"/>' for y in range(176, 218, 8)) + "</g>")
        p.append('<circle cx="100" cy="134" r="6" fill="#19e07a" stroke="#fff" stroke-width="2"/>')  # GPS-antenna
    # fresbom, fres og finisher
    p.append('<rect x="88" y="226" width="24" height="20" fill="#4a5862"/>')
    p.append('<rect x="14" y="242" width="172" height="30" rx="5" fill="#cc2424" stroke="#6e0d0d" stroke-width="3"/>')
    if detail:
        p.append('<g stroke="#8a1414" stroke-width="3">' + "".join(f'<line x1="{x}" y1="246" x2="{x}" y2="268"/>' for x in range(28, 180, 13)) + "</g>")
    p.append('<rect x="14" y="272" width="172" height="16" fill="#f2c230"/>')
    p.append('<rect x="8" y="244" width="8" height="44" rx="2" fill="#ffd33f"/><rect x="184" y="244" width="8" height="44" rx="2" fill="#ffd33f"/>')
    return "".join(p)


def icon_svg(detail=True):
    peaks = (
        f'<g transform="{"translate(46 74) scale(3.5)" if detail else "translate(40 40) scale(3.6)"}"><path d="{PEAKS}" fill="#ffffff"/>'
        + (f'<path d="{PEAK_CUT}" fill="none" stroke="#123c5c" stroke-width="2.2" stroke-linejoin="round"/>' if detail else "")
        + "</g>"
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="natt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b2a44"/><stop offset="1" stop-color="#15507c"/></linearGradient>
    <linearGradient id="sno" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#dcecf7"/></linearGradient>
    <clipPath id="ramme"><rect x="16" y="16" width="480" height="480" rx="108"/></clipPath>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="108" fill="url(#natt)"/>
  <g clip-path="url(#ramme)">
    {peaks}
    <path d="{"M0 196 C120 172 392 172 512 196 V512 H0 Z" if detail else "M0 168 C120 146 392 146 512 168 V512 H0 Z"}" fill="url(#sno)"/>
    <g transform="{"translate(171 212) scale(0.85)" if detail else "translate(126 150) scale(1.3)"}">{groomer(detail)}</g>
  </g>
  <rect x="16" y="16" width="480" height="480" rx="108" fill="none" stroke="#ffffff" stroke-opacity=".14" stroke-width="4"/>
</svg>"""


def logo_svg():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 150" width="360" height="150">
  <g transform="translate(108 2) scale(1.2)"><path d="{PEAKS}" fill="#ffffff"/><path d="{PEAK_CUT}" fill="none" stroke="#02141d" stroke-width="2.2" stroke-linejoin="round"/></g>
  <text x="180" y="100" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="64" letter-spacing="1" fill="#ffffff">SNOWMAN</text>
  <text x="180" y="136" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="28" fill="#8cc8f0">by Alpindata</text>
</svg>"""


async def render(svg, size):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": size, "height": size})
        sized = svg.replace('width="512" height="512"', f'width="{size}" height="{size}"', 1)
        await pg.set_content('<html><body style="margin:0;background:transparent">' + sized + "</body></html>")
        png = await pg.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
        await b.close()
        return png


def main():
    from PIL import Image
    big, small = icon_svg(True), icon_svg(False)
    (HERE / "snowman.svg").write_text(big, "utf-8")
    (HERE / "snowman-enkel.svg").write_text(small, "utf-8")
    (HERE / "snowman-logo.svg").write_text(logo_svg(), "utf-8")
    imgs = {}
    for s in (16, 24, 32, 48, 64, 128, 256, 512):
        imgs[s] = Image.open(io.BytesIO(asyncio.run(render(small if s <= 32 else big, s)))).convert("RGBA")
    imgs[512].save(HERE / "snowman-512.png")
    imgs[256].save(HERE / "snowman-256.png")
    imgs[64].save(HERE.parent / "vendor" / "snowman-icon.png")
    # ICO med eigne bilete for kvar storleik (dei små er den forenkla utgåva)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs[256].save(HERE / "snowman.ico", sizes=[(s, s) for s in sizes], append_images=[imgs[s] for s in sizes[:-1]])
    print("Laga:", ", ".join(["snowman.svg", "snowman-enkel.svg", "snowman-logo.svg", "snowman-512.png", "snowman-256.png", "snowman.ico", "../vendor/snowman-icon.png"]))


if __name__ == "__main__":
    sys.exit(main())
