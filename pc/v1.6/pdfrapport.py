# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Rapporten for eitt prepareringsdøgn som PDF: samandrag, kart (per trasé, eller heile området), trasear, økter og
drivstoff. Skriven utan tilleggspakkar (berre numpy, som SNOWMAN alt brukar), så det fungerer offline på alle PC-ar.

Bruk: pdf_bytes = build(rep, machine="Trakkemaskin 1")   – rep frå Drivstoff.report(date, maps=True)
"""
import base64, time, zlib

import numpy as np

A4 = (595.28, 841.89)
M = 42  # marg (pt)
NAVY = (0.04, 0.17, 0.27)
GREY = (0.42, 0.47, 0.52)
ORANGE = (0.85, 0.50, 0.08)


def _t(s):
    """Tekst til PDF (WinAnsi): escape og byt ut teikn som ikkje finst i Helvetica."""
    s = str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    for a, b in (("✓", "OK"), ("⚠", "!"), ("−", "-"), ("≈", "ca. "), ("▾", ""), ("▸", "")):
        s = s.replace(a, b)
    return s.encode("cp1252", "replace")


class Pdf:
    def __init__(self):
        self.pages = []
        self.images = []
        self.new_page()

    def new_page(self):
        self.ops = []
        self.pages.append(self.ops)
        self.y = A4[1] - M

    def text(self, x, y, s, size=10, bold=False, color=(0, 0, 0)):
        self.ops.append(b"BT /%s %.1f Tf %.3f %.3f %.3f rg %.2f %.2f Td (" % (b"F2" if bold else b"F1", size, *color, x, y) + _t(s) + b") Tj ET")

    def rect(self, x, y, w, h, fill=None, stroke=None, lw=0.6):
        ops = b""
        if fill:
            ops += b"%.3f %.3f %.3f rg " % fill
        if stroke:
            ops += b"%.3f %.3f %.3f RG %.2f w " % (*stroke, lw)
        ops += b"%.2f %.2f %.2f %.2f re %s" % (x, y, w, h, b"B" if fill and stroke else b"f" if fill else b"S")
        self.ops.append(ops)

    def line(self, x1, y1, x2, y2, color=(0.75, 0.78, 0.8), lw=0.5):
        self.ops.append(b"%.3f %.3f %.3f RG %.2f w %.2f %.2f m %.2f %.2f l S" % (*color, lw, x1, y1, x2, y2))

    def image(self, rgb, x, y, w, h):
        """rgb: numpy (H, W, 3) uint8. Teikna utan utjamning, så rutene blir skarpe."""
        n = len(self.images)
        self.images.append(rgb)
        self.ops.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /Im%d Do Q" % (w, h, x, y, n))

    def need(self, h):
        if self.y - h < M + 20:
            self.new_page()

    def bytes(self, footer):
        objs = []

        def add(b):
            objs.append(b)
            return len(objs)

        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        imgs = []
        for im in self.images:
            h, w = im.shape[:2]
            data = zlib.compress(np.ascontiguousarray(im, dtype=np.uint8).tobytes(), 6)
            imgs.append(add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % (w, h, len(data)) + data + b"\nendstream"))
        pages_id = len(objs) + 1 + 2 * len(self.pages)
        kids = []
        for i, ops in enumerate(self.pages):
            ops = ops + [b"BT /F1 8 Tf 0.45 0.5 0.55 rg %.2f %.2f Td (" % (M, 22) + _t(footer + f"  ·  side {i + 1} av {len(self.pages)}") + b") Tj ET"]
            content = zlib.compress(b"\n".join(ops))
            c = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content) + content + b"\nendstream")
            xo = b" ".join(b"/Im%d %d 0 R" % (j, o) for j, o in enumerate(imgs))
            kids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> /XObject << %s >> >> >>" % (pages_id, A4[0], A4[1], c, f1, f2, xo)))
        assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))) == pages_id
        cat = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
        out = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offs = []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
        out += b"trailer\n<< /Size %d /Root %d 0 R /Info << /Title (SNOWMAN rapport) /Producer (SNOWMAN by Alpindata) >> >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, cat, xref)
        return out


# Snødjupne-fargane frå førarskjermen (raud = lite snø … blå = mykje), og «preparert, ikkje målt»
COLORS = [(237, 32, 36), (255, 148, 18), (233, 237, 22), (39, 216, 77), (8, 203, 234), (7, 93, 229)]
NEUTRAL = (127, 178, 214)


def _depth(m, n):
    """Snødjupne-rutenettet (m) frå rapporten, nan = ikkje målt."""
    if not m.get("depth"):
        return None
    v = np.frombuffer(base64.b64decode(m["depth"]), np.uint8)[:n].astype(float)
    v[v == 255] = np.nan
    return v / 50.0


def _paint_depth(img, mask, d, bounds):
    """Farg trakka ruter etter snødjupna (klassar som i førarskjermen); trakka utan måling blir lyseblå."""
    img[mask] = NEUTRAL
    if d is None:
        return False
    ok = mask & np.isfinite(d)
    if not ok.any():
        return False
    cls = np.digitize(d[ok], bounds)
    img[ok] = np.array(COLORS, np.uint8)[np.clip(cls, 0, 5)]
    return True


def _bits(b64, n):
    return np.unpackbits(np.frombuffer(base64.b64decode(b64 or ""), np.uint8))[:n].astype(bool)


def _trase_rgb(m, bounds):
    W, H = m["W"], m["H"]
    ins, cov, alls = (_bits(m.get(k), W * H).reshape(H, W) for k in ("ins", "cov", "covAll"))
    d = _depth(m, W * H)
    d = None if d is None else d.reshape(H, W)
    img = np.full((H, W, 3), 255, np.uint8)
    img[ins] = (214, 222, 228)
    trakka = ins & (alls if m.get("depthSim") else cov)
    has = _paint_depth(img, trakka, d, bounds)
    return np.flipud(img), has  # rad 0 er sørkanten – nord skal vere opp


def _area_rgb(a, bounds):
    W, H = a["W"], a["H"]
    age = np.frombuffer(base64.b64decode(a["age"]), np.uint8)[: W * H].reshape(H, W)
    d = _depth(a, W * H)
    d = None if d is None else d.reshape(H, W)
    img = np.full((H, W, 3), 255, np.uint8)
    has = _paint_depth(img, age != 255, d, bounds)
    return np.flipud(img), has


def _crop(img, cell, pad=6):
    """Skjer bort tomt område rundt (kvite ruter), så kartet blir stort nok å lese."""
    m = (img != 255).any(axis=2)
    if not m.any():
        return img, cell
    r, c = np.where(m)
    r0, r1, c0, c1 = max(r.min() - pad, 0), min(r.max() + pad + 1, img.shape[0]), max(c.min() - pad, 0), min(c.max() + pad + 1, img.shape[1])
    return img[r0:r1, c0:c1], cell


def _scale(pdf, bounds, sim, has):
    """Fargeskala for snødjupna under kartet."""
    x, y = M, pdf.y - 4
    labels = [f"< {bounds[0]:g}"] + [f"{bounds[i]:g}–{bounds[i + 1]:g}" for i in range(4)] + [f"> {bounds[4]:g}"]
    pdf.text(x, y - 9, "Snødjupne (m):", 8, True, NAVY)
    x += 64
    for c, l in zip(COLORS, labels):
        pdf.rect(x, y - 11, 10, 10, fill=tuple(v / 255 for v in c))
        pdf.text(x + 13, y - 9, l, 8)
        x += 52
    pdf.rect(x, y - 11, 10, 10, fill=tuple(v / 255 for v in NEUTRAL))
    pdf.text(x + 13, y - 9, "trakka, ikkje målt", 8)
    pdf.y -= 18
    if sim:
        pdf.text(M, pdf.y - 6, "SIMULERT SNØ (TEST) – ikkje ekte måling.", 8, True, ORANGE)
        pdf.y -= 12
    elif not has:
        pdf.text(M, pdf.y - 6, "Ingen målt snødjupne her (krev RTK FIX, kalibrering og terrengmodell).", 8, False, GREY)
        pdf.y -= 12


def _map(pdf, img, cell, title, legend):
    img, cell = _crop(img, cell)
    H, W = img.shape[:2]
    maxw, maxh = A4[0] - 2 * M, 300.0
    k = min(maxw / W, maxh / H)
    w, h = W * k, H * k
    pdf.need(h + 40)
    pdf.text(M, pdf.y - 12, title, 11, True, NAVY)
    pdf.text(M, pdf.y - 25, legend, 8, False, GREY)
    y = pdf.y - 32 - h
    pdf.image(img, M, y, w, h)
    pdf.rect(M, y, w, h, stroke=(0.6, 0.65, 0.7))
    # målestokk og nord
    mpp = cell / k
    L = next((v for v in (10, 20, 50, 100, 200, 500, 1000, 2000) if v / mpp > 40), 2000)
    pdf.rect(M + 6, y + 6, L / mpp, 3, fill=(0.1, 0.1, 0.1))
    pdf.text(M + 6, y + 12, f"{L} m", 8, True)
    pdf.text(M + w - 24, y + h - 14, "N ^", 9, True)
    pdf.y = y - 6


def _table(pdf, cols, rows, widths, colors=None):
    """Enkel tabell. cols: overskrifter, rows: lister med tekst, colors: farge per rad (eller None)."""
    x = [M]
    for wd in widths[:-1]:
        x.append(x[-1] + wd)
    pdf.need(30)
    for i, c in enumerate(cols):
        pdf.text(x[i], pdf.y - 11, c, 8.5, True, NAVY)
    pdf.line(M, pdf.y - 15, A4[0] - M, pdf.y - 15, NAVY, 0.8)
    pdf.y -= 17
    for j, r in enumerate(rows):
        pdf.need(16)
        for i, v in enumerate(r):
            s = str(v)
            mx = int(widths[i] / 4.6)
            pdf.text(x[i], pdf.y - 11, s if len(s) <= mx else s[: mx - 1] + "…", 8.5, False, (colors[j] if colors and colors[j] else (0, 0, 0)))
        pdf.line(M, pdf.y - 15, A4[0] - M, pdf.y - 15)
        pdf.y -= 16
    pdf.y -= 8


def _h(pdf, s):
    pdf.need(40)
    pdf.y -= 10
    pdf.text(M, pdf.y - 14, s, 13, True, NAVY)
    pdf.y -= 22


def build(rep, machine="", bounds=None, note=None):
    """note: tydeleg merknad øvst og i botnen av kvar side (t.d. «EKSEMPEL – oppdikta data»)."""
    bounds = list(bounds or [0.3, 0.5, 0.8, 1.2, 1.6])[:5]
    n = lambda v, d=1: "–" if v is None else (f"{v:.{d}f}").replace(".", ",")
    hm = lambda ms: time.strftime("%H:%M", time.localtime(ms / 1000)) if ms else "–"
    mins = lambda m: f"{int(m) // 60} t {int(m) % 60:02d} min"
    sm = lambda m: f"{int(m)} min" if int(m) < 60 else f"{int(m) // 60} t {int(m) % 60:02d} min"
    date = rep["date"]
    d = time.strftime("%d.%m.%Y", time.strptime(date, "%Y-%m-%d"))
    nxt = time.strftime("%d.%m.%Y", time.localtime(time.mktime(time.strptime(date, "%Y-%m-%d")) + 86400))
    pdf = Pdf()
    # Topp
    pdf.rect(0, A4[1] - 78, A4[0], 78, fill=NAVY)
    pdf.text(M, A4[1] - 40, "SNOWMAN", 22, True, (1, 1, 1))
    pdf.text(M, A4[1] - 58, "by Alpindata", 10, True, (0.55, 0.78, 0.94))
    pdf.text(200, A4[1] - 38, f"Rapport – prepareringsdøgn {d} kl. 12 til {nxt} kl. 12", 12, True, (1, 1, 1))
    pdf.text(200, A4[1] - 56, (machine + " · " if machine else "") + "laga " + time.strftime("%d.%m.%Y %H:%M"), 9, False, (0.8, 0.88, 0.94))
    pdf.y = A4[1] - 100
    if note:
        pdf.rect(M, pdf.y - 24, A4[0] - 2 * M, 22, fill=(1.0, 0.93, 0.80), stroke=ORANGE)
        pdf.text(M + 8, pdf.y - 17, note, 10, True, ORANGE)
        pdf.y -= 30
    T = rep["total"]
    _h(pdf, "Samla")
    for s in (
        f"Tid med prep: {mins(T['prepMin'])}   ·   Køyrd: {n(T['km'], 1)} km   ·   Areal køyrt: {n(T['areaDaa'], 1)} daa   ·   Drivstoff fylt: {n(T['litres'], 0)} l",
        f"Snødjupne målt: snitt {n(T['depthAvg'], 2)} m, minst {n(T['depthMin'], 2)} m" if T.get("depthAvg") is not None else "Snødjupne: ikkje målt (krev RTK FIX, kalibrering og terrengmodell)",
    ):
        pdf.text(M, pdf.y - 11, s, 9.5)
        pdf.y -= 15
    if rep["test"]["n"]:
        pdf.text(M, pdf.y - 11, f"TEST/demo: {rep['test']['n']} økt(er), {mins(rep['test']['prepMin'])} – ikkje med i summen. Simulert snø er aldri ekte måling.", 9, True, ORANGE)
        pdf.y -= 15
    # Trasear
    tr = rep.get("trasear") or []
    if tr:
        _h(pdf, f"Trasear ({len(tr)})")
        _table(
            pdf,
            ["Trasé", "Areal", "Preparert", "Tid i traseen", "Sist", "Snødjupne snitt / minst", "Mål"],
            [[t["name"], n(t["areaDaa"]) + " daa", n(t["pct"], 0) + " %" + (f" ({n(t['pctTest'], 0)} % m/TEST)" if t["pctTest"] > t["pct"] else ""),
              sm(t.get("min") or 0) + (f" ({sm(t['minTest'])} TEST)" if (t.get("minTest") or 0) > (t.get("min") or 0) else ""), hm(t["last"]), (n(t["depthAvg"], 2) + " / " + n(t["depthMin"], 2) + " m") if t["depthAvg"] is not None else "–",
              (n(t["target"], 2) + " m") if t.get("target") is not None else "–"] for t in tr],
            [105, 46, 82, 100, 32, 100, 46],
        )
    # Kart
    maps = [t for t in tr if t.get("map")]
    if maps:
        _h(pdf, "Kart per trasé – kvar det er trakka")
        for t in maps:
            img, has = _trase_rgb(t["map"], bounds)
            _map(pdf, img, t["map"]["cell"], f"{t['name']} · {n(t['pct'], 0)} % preparert · {mins(t.get('min') or 0)}",
                 "Farga etter snødjupne der det er trakka · grått: ikkje trakka · nord er opp")
            _scale(pdf, bounds, t["map"].get("depthSim"), has)
    elif rep.get("area") and not rep["area"].get("empty"):
        a = rep["area"]
        _h(pdf, "Kart – trakka område")
        parts = a.get("parts") or [a]
        for i, part in enumerate(parts):
            img, has = _area_rgb(part, bounds)
            _map(pdf, img, part["cell"],
                 (f"Område {i + 1} av {len(parts)} · " if len(parts) > 1 else "Heile området som er køyrt · ") + f"{n(part['area'] / 1000, 1)} daa" + (" · TEST" if a.get("onlyTest") else ""),
                 ("Ingen trasear er lagde inn, så kartet viser alt som er køyrt i fresbreidda. " if i == 0 else "")
                 + ("Berre demo/test – ikkje ekte preparering. " if a.get("onlyTest") else "") + "Farga etter snødjupne. Nord er opp.")
            _scale(pdf, bounds, part.get("depthSim"), has)
    # Økter
    ses = rep.get("sessions") or []
    _h(pdf, f"Økter ({len(ses)})")
    if ses:
        _table(pdf, ["Tid", "Maskin", "Prep", "Køyrd", "Fresbreidd", "Areal", "Snødjupne snitt / minst", "Merknad"],
               [[hm(s["start"]) + "–" + hm(s["end"]), s.get("machine") or "", f"{s['prepMin']} min", n(s["km"], 2) + " km", n(s["width"], 1) + " m",
                 n(s["areaDaa"]) + " daa", (n(s["depthAvg"], 2) + " / " + n(s["depthMin"], 2) + " m") if s["depthAvg"] is not None else "–",
                 "TEST" if s["test"] else ""] for s in ses],
               [62, 82, 44, 54, 56, 50, 100, 63], [ORANGE if s["test"] else None for s in ses])
    else:
        pdf.text(M, pdf.y - 11, "Ingen økter dette døgnet.", 9.5)
        pdf.y -= 16
    # Drivstoff
    fu = rep.get("fuel") or []
    _h(pdf, f"Drivstoff ({len(fu)} fylling{'' if len(fu) == 1 else 'ar'})")
    if fu:
        _table(pdf, ["Tid", "Liter", "Full tank", "Motortimar", "Forbruk l/time", "Forbruk l/daa"],
               [[hm(f["t"]), n(f["litres"]), "ja" if f.get("full") else "nei", n(f.get("hours"), 1) if f.get("hours") is not None else "–",
                 n(f.get("lph"), 1), n(f.get("lpdaa"), 2)] for f in fu],
               [70, 70, 70, 80, 100, 100])
    else:
        pdf.text(M, pdf.y - 11, "Ingen fyllingar registrerte dette døgnet.", 9.5)
        pdf.y -= 16
    return pdf.bytes(f"SNOWMAN by Alpindata – rapport {d}" + (f" – {machine}" if machine else "") + (f"  ·  {note}" if note else ""))
