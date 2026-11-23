#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Lagar ikonet til SNOWMAN Office (snarvegen på skrivebordet) i same stil som ikonet til SNOWMAN Snowdeep.

Ikonet: same nattehimmel, fjelltoppar og snø som SNOWMAN Snowdeep (pc/v1.6/ikon/lag-ikon.py), men i staden for
tråkkemaskina ein skjerm med kartet: ei løype farga etter snødjupne og maskinene som prikkar – det Office viser.
Små storleikar (16–32 px) får ei forenkla utgåve.

Skriv: snowman-office.svg, snowman-office-enkel.svg, snowman-office-256.png, snowman-office.ico (16–256 px)
Bruk (berre ved utvikling – krev Playwright/Chromium og Pillow):  python3 lag-ikon.py
"""
import asyncio, io, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PEAKS = "M14 30 L46 2 L66 20 L74 13 L104 30 Z"            # same fjelltoppar som logoen og Snowdeep-ikonet
PEAK_CUT = "M33 14 L39 17 L46 11 L52 17 L57 14 M68 18 L74 16 L80 19"


def screen(detail=True):
    """Skjerm med kart i eit felt på 300 × 250 (x 0–300)."""
    p = ['<path d="M118 196 L182 196 L192 236 L108 236 Z" fill="#4a5862"/>',
         '<rect x="78" y="230" width="144" height="16" rx="8" fill="#5d6f7b"/>',
         '<rect x="0" y="0" width="300" height="200" rx="20" fill="#1a252d" stroke="#e6edf1" stroke-width="5"/>',
         '<rect x="16" y="16" width="268" height="168" rx="8" fill="#0e2a3b"/>']
    if detail:
        p.append('<g stroke="#1f4a63" stroke-width="2">' + "".join(f'<line x1="{x}" y1="16" x2="{x}" y2="184"/>' for x in range(52, 284, 36))
                 + "".join(f'<line x1="16" y1="{y}" x2="284" y2="{y}"/>' for y in range(52, 184, 36)) + "</g>")
    # løypa farga etter snødjupne (raud → gul → grøn → blå, same fargar som i kartet)
    w = 26 if detail else 38
    for d, c in (("M30 170 C70 150 80 120 110 112", "#ef3b2c"), ("M110 112 C140 104 150 84 172 74", "#f2c230"),
                 ("M172 74 C196 64 214 70 236 56", "#2fbf5a"), ("M236 56 C252 46 262 40 276 30", "#1f8fe0")):
        p.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>')
    # maskinene
    if detail:
        p.append('<circle cx="110" cy="112" r="13" fill="#5ee07a" stroke="#ffffff" stroke-width="4"/>')
        p.append('<circle cx="236" cy="56" r="13" fill="#5ee07a" stroke="#ffffff" stroke-width="4"/>')
    else:
        p.append('<circle cx="172" cy="74" r="20" fill="#5ee07a" stroke="#ffffff" stroke-width="6"/>')
    return "".join(p)


def icon_svg(detail=True):
    peaks = (f'<g transform="{"translate(46 74) scale(3.5)" if detail else "translate(40 40) scale(3.6)"}"><path d="{PEAKS}" fill="#ffffff"/>'
             + (f'<path d="{PEAK_CUT}" fill="none" stroke="#123c5c" stroke-width="2.2" stroke-linejoin="round"/>' if detail else "") + "</g>")
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
    <g transform="{"translate(106 218)" if detail else "translate(76 186) scale(1.2)"}">{screen(detail)}</g>
  </g>
  <rect x="16" y="16" width="480" height="480" rx="108" fill="none" stroke="#ffffff" stroke-opacity=".14" stroke-width="4"/>
</svg>"""


async def render(svg, size):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": size, "height": size})
        await pg.set_content('<html><body style="margin:0;background:transparent">'
                             + svg.replace('width="512" height="512"', f'width="{size}" height="{size}"', 1) + "</body></html>")
        png = await pg.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
        await b.close()
        return png


def main():
    from PIL import Image
    big, small = icon_svg(True), icon_svg(False)
    (HERE / "snowman-office.svg").write_text(big, "utf-8")
    (HERE / "snowman-office-enkel.svg").write_text(small, "utf-8")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = {s: Image.open(io.BytesIO(asyncio.run(render(small if s <= 32 else big, s)))).convert("RGBA") for s in sizes}
    imgs[256].save(HERE / "snowman-office-256.png")
    imgs[256].save(HERE / "snowman-office.ico", sizes=[(s, s) for s in sizes], append_images=[imgs[s] for s in sizes[:-1]])
    print("Laga: snowman-office.svg, snowman-office-enkel.svg, snowman-office-256.png, snowman-office.ico")


if __name__ == "__main__":
    sys.exit(main())
