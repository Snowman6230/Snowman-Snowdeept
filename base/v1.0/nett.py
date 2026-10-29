# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""HTTPS frå SNOWMAN Base (oppdatering, satellittbaner, AI) med sertifikatkontroll som fungerer på Windows.

Python 3.13 krev strengare sertifikat (VERIFY_X509_STRICT). Antivirus, brannmurar og proxyar som les HTTPS
(t.d. på skule- og bedriftsnett) set inn eigne rotsertifikat som ofte manglar felt (Authority Key Identifier), og
då feilar Python med «CERTIFICATE_VERIFY_FAILED», sjølv om nettlesaren godtek sida.
Løysing – same som i SNOWMAN snødjupne (pc/v1.6/nett.py): truststore (MIT, vendor/truststore) lèt operativsystemet
sjølv kontrollere sertifikatet, akkurat som nettlesaren. Utan truststore blir berre den strenge tilleggsregelen
slått av. Sertifikatkontrollen blir aldri slått av.
"""
import ssl
import sys
import urllib.request
from pathlib import Path

_VENDOR = str(Path(__file__).resolve().parent / "vendor")
_CTX, CERTS = None, "Python (standard)"


def context():
    global _CTX, CERTS
    if _CTX is None:
        try:
            if _VENDOR not in sys.path:
                sys.path.append(_VENDOR)
            import truststore
            _CTX = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            CERTS = "systemet (truststore)"
        except Exception as e:
            _CTX = ssl.create_default_context()
            if hasattr(ssl, "VERIFY_X509_STRICT"):
                _CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT
            CERTS = f"Python (standard, utan streng X509 – truststore: {str(e)[:80]})"
    return _CTX


def urlopen(req, timeout=10):
    """urllib.request.urlopen med sertifikatkontroll frå systemet."""
    return urllib.request.urlopen(req, timeout=timeout, context=context())


def forklar(e):
    """Kort forklaring på norsk av ein nettverksfeil."""
    s = str(getattr(e, "reason", "") or e)
    low = s.lower()
    if "certificate" in low or "ssl" in low:
        return ("Sertifikatfeil: PC-en godtek ikkje sertifikatet. Sjekk at klokka er rett. Eit antivirus eller ein "
                "brannmur som les HTTPS, kan også vere årsaka. (" + s[:120] + ")")
    if "getaddrinfo" in low or "name or service" in low or "11001" in low or "11002" in low:
        return "Finn ikkje adressa: maskina har ikkje nett, eller DNS svarar ikkje."
    if "timed out" in low:
        return "Tidsavbrot: nettet er for tregt eller stengt."
    return s[:200]
