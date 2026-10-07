# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""PROTOTYPE – IKKJE I BRUK. Testa 2026-10-07 mot PC v1.6.44 i ei eiga testkopi (sjå docs/VEGEN-VIDARE.md, kap. 7).

Legg trakka område frå Historikk og bakgrunnskartet oppå 3D-terrenget.
Bruk (berre på ei testkopi):  python3 3d-trakka-og-kart.py <kopi>/driver.html
Skal det inn i SNOWMAN, må det gjerast som ny versjon med test på Surface-en først.
"""
import sys
p=sys.argv[1]; s=open(p,encoding='utf-8').read()
def R(a,b):
    global s
    assert a in s,a[:60]; s=s.replace(a,b,1)
R('''          raf = null,
          lastFrame = 0;''','''          raf = null,
          lastFrame = 0,
          covCv = null, covB = null, tiles = {}, tileTimer = null;''')
# kart under kurvene
R('''          texCx.fillRect(0, 0, texCv.width, texCv.height);
          if (!bg) return;''','''          texCx.fillRect(0, 0, texCv.width, texCv.height);
          if (!bg) return;
          paintMap();''')
R('''        function repaint() {
          if (!patch) return;
          paintBase();''','''        // PROTOTYPE: bakgrunnskartet (same fliser som 2D-kartet) drapert over terrenget
        function tileXY(lat, lon, z) {
          let n = 2 ** z, r = (lat * Math.PI) / 180;
          return [((lon + 180) / 360) * n, ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n];
        }
        function tileLL(x, y, z) {
          let n = 2 ** z, lon = (x / n) * 360 - 180, lat = (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) * 180) / Math.PI;
          return [lat, lon];
        }
        function paintMap() {
          if (!baseLayer || !baseLayer._url || !map.hasLayer(baseLayer)) return;
          let z = Math.min(18, baseLayer.options.maxNativeZoom || 18),
            dLat = HALF / M_LAT, dLon = HALF / mLon(patch.lat0),
            [x0, y0] = tileXY(patch.lat0 + dLat, patch.lon0 - dLon, z),
            [x1, y1] = tileXY(patch.lat0 - dLat, patch.lon0 + dLon, z);
          texCx.globalAlpha = 0.85;
          for (let x = Math.floor(x0); x <= Math.floor(x1); x++)
            for (let y = Math.floor(y0); y <= Math.floor(y1); y++) {
              let key = z + "/" + x + "/" + y, im = tiles[key];
              if (!im) {
                im = tiles[key] = new Image();
                im.crossOrigin = "anonymous";
                im.onload = () => { clearTimeout(tileTimer); tileTimer = setTimeout(repaint, 150); };
                im.src = L.Util.template(baseLayer._url, { z, x, y, s: "a" });
                continue;
              }
              if (!im.complete || !im.naturalWidth) continue;
              let a = local(tileLL(x, y, z)), b = local(tileLL(x + 1, y + 1, z));
              texCx.drawImage(im, (a[0] + HALF) * PX, (HALF - a[1]) * PX, (b[0] - a[0]) * PX, (a[1] - b[1]) * PX);
            }
          texCx.globalAlpha = 1;
        }
        // PROTOTYPE: trakka område frå historikken (same bilete som 2D) lagt på terrenget
        function paintCov() {
          if (!covCv || !covB) return;
          let a = local(covB[0]), b = local(covB[1]);
          texCx.globalAlpha = 0.7;
          texCx.imageSmoothingEnabled = false;
          texCx.drawImage(covCv, (a[0] + HALF) * PX, (HALF - b[1]) * PX, (b[0] - a[0]) * PX, (b[1] - a[1]) * PX);
          texCx.imageSmoothingEnabled = true;
          texCx.globalAlpha = 1;
        }
        function repaint() {
          if (!patch) return;
          paintBase();
          paintCov();''')
R('''          addSeg(a, b, w, color) {''','''          setCoverage(cv, b) {
            covCv = cv; covB = b;
            if (patch && renderer) { repaint(); }
          },
          addSeg(a, b, w, color) {''')
# showCoverage: send bildet til 3D
R('''        L.imageOverlay(cv.toDataURL(), b, { interactive: false, className: "traUnprepImg" }).addTo(covGroup);''','''        L.imageOverlay(cv.toDataURL(), b, { interactive: false, className: "traUnprepImg" }).addTo(covGroup);
        T3D.setCoverage(cv, b);''')
open(p,'w',encoding='utf-8').write(s)
