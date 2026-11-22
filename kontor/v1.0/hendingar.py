# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Hendingar (kontorsida og data/hendingar.log) og ledig diskplass."""
import collections
import os
import shutil
import threading
import time
from pathlib import Path


class Events:
    MAKS_BYTE = 5_000_000            # hendingar.log blir rotert til hendingar.log.1 ved 5 MB

    def __init__(self, folder=None, n=300):
        self.items = collections.deque(maxlen=n)
        self.lock = threading.Lock()
        self.file = Path(folder) / "hendingar.log" if folder else None
        self._n = 0

    def add(self, text, level="info"):
        e = {"t": time.time(), "tekst": text, "niva": level}
        with self.lock:
            self.items.append(e)
            if self.file:
                try:
                    self._n += 1
                    if self._n % 200 == 1 and self.file.exists() and self.file.stat().st_size > self.MAKS_BYTE:
                        os.replace(self.file, self.file.with_suffix(".log.1"))
                    with open(self.file, "a", encoding="utf-8") as f:
                        f.write(time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime(e["t"])) + f"[{level}] {text}\n")
                except OSError:
                    pass

    def latest(self, n=100):
        with self.lock:
            return list(self.items)[-n:][::-1]


def disk_free(folder):
    try:
        return round(shutil.disk_usage(folder).free / 1e9, 1)
    except OSError:
        return None
