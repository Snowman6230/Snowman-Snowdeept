# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Opningstider for skianlegget – brukt av AI-en (tidspunkt å preparere: ferdig før neste opning).

Standard (kan endrast i AI › Opningstider):
  * Laurdag og søndag kl. 10–16.
  * Kveldskøyring tysdag, onsdag og fredag kl. 18–21 (varierer mellom anlegg – endre manuelt).
  * Skoleferiar og heilagdagar: ope kl. 10–16 (i tillegg til kveldskøyring):
      - juleferie: 21. desember – 1. januar (julaftan og 1. juledag stengt som standard)
      - vinterferie: veke 8 og veke 9 (fylka og kommunane har ulike veker – anlegga får gjester frå begge;
        sjå skoleruta i fylket/kommunen og endre om det trengst)
      - påskeferie: laurdag før palmesøndag – 2. påskedag
      - heilagdagar (norsk kalender, rekna ut lokalt): 1. nyttårsdag, skjærtorsdag, langfredag, påskedag,
        2. påskedag, 1. mai, Kristi himmelfart, 17. mai, pinsedag, 2. pinsedag, 1. og 2. juledag
  * Berre innanfor sesongen (standard 1. desember – 30. april).
  * Manuelle unntak per dato (ekstra opning, andre tider eller stengt) går framfor alt anna.
Heilagdagane blir rekna ut i programmet (påskeformelen), så dette fungerer utan nett og i heile Noreg.
Data: data/opningstid.json (høyrer til anlegget, ikkje i git).
"""
import datetime as dt
import json
from pathlib import Path

DAYS = ["man", "tys", "ons", "tor", "fre", "lau", "sun"]
DAYNAME = ["måndag", "tysdag", "onsdag", "torsdag", "fredag", "laurdag", "søndag"]
DEFAULT = {
    "weekly": {"man": [], "tys": [["18:00", "21:00"]], "ons": [["18:00", "21:00"]], "tor": [],
               "fre": [["18:00", "21:00"]], "lau": [["10:00", "16:00"]], "sun": [["10:00", "16:00"]]},
    "holidayHours": [["10:00", "16:00"]],
    "season": ["12-01", "04-30"],
    "juleferie": True, "vinterferie": True, "vinterferieWeeks": [8, 9], "paskeferie": True, "heilagdagar": True,
    "closed": ["12-24", "12-25"],
    "exceptions": [],          # [{"date": "2027-02-14", "open": [["10:00","16:00"]], "note": "…"}]  open: [] = stengt
}


def easter(y):
    """Påskedag (gregoriansk, Meeus/Jones/Butcher)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31
    return dt.date(y, mo, (h + l - 7 * m + 114) % 31 + 1)


def holidays(y):
    """Norske heilagdagar for året: dato → namn."""
    p = easter(y)
    D = lambda n: p + dt.timedelta(days=n)
    return {dt.date(y, 1, 1): "1. nyttårsdag", D(-3): "skjærtorsdag", D(-2): "langfredag", p: "påskedag", D(1): "2. påskedag",
            dt.date(y, 5, 1): "1. mai", D(39): "Kristi himmelfartsdag", dt.date(y, 5, 17): "17. mai", D(49): "pinsedag",
            D(50): "2. pinsedag", dt.date(y, 12, 25): "1. juledag", dt.date(y, 12, 26): "2. juledag"}


def _md(d):
    return f"{d.month:02d}-{d.day:02d}"


class Opningstid:
    def __init__(self, path):
        self.path = Path(path)
        self.cfg = json.loads(json.dumps(DEFAULT))
        try:
            self.cfg.update(json.loads(self.path.read_text("utf-8")))
        except Exception:
            pass

    def save(self, d):
        c = json.loads(json.dumps(DEFAULT))
        c.update({k: v for k, v in (d or {}).items() if k in DEFAULT})
        # enkel validering av tider
        for day in DAYS:
            c["weekly"][day] = [iv for iv in c["weekly"].get(day, []) if _ok(iv)]
        c["holidayHours"] = [iv for iv in c["holidayHours"] if _ok(iv)]
        c["exceptions"] = [e for e in c["exceptions"] if _date(e.get("date")) and all(_ok(iv) for iv in e.get("open", []))]
        c["vinterferieWeeks"] = sorted({int(w) for w in c["vinterferieWeeks"] if 1 <= int(w) <= 53})
        self.cfg = c
        tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1), "utf-8"); tmp.replace(self.path)
        return c

    def in_season(self, d):
        a, b = self.cfg["season"]
        m = _md(d)
        return (a <= m <= b) if a <= b else (m >= a or m <= b)

    def day(self, d):
        """Opningstider for ein dato: (intervall, kvifor)."""
        c = self.cfg
        for e in c["exceptions"]:
            if e.get("date") == d.isoformat():
                return [tuple(x) for x in e.get("open", [])], ["manuelt: " + (e.get("note") or ("stengt" if not e.get("open") else "eigne tider"))]
        if not self.in_season(d):
            return [], ["utanfor sesongen"]
        if _md(d) in c["closed"]:
            return [], ["stengt (" + _md(d) + ")"]
        why, iv = [], [tuple(x) for x in c["weekly"].get(DAYS[d.weekday()], [])]
        if iv:
            why.append(DAYNAME[d.weekday()])
        hol = []
        h = holidays(d.year).get(d)
        if h and c["heilagdagar"]:
            hol.append(h)
        if c["juleferie"] and ((d.month == 12 and d.day >= 21) or (d.month == 1 and d.day <= 1)):
            hol.append("juleferie")
        if c["vinterferie"] and d.isocalendar()[1] in c["vinterferieWeeks"] and d.month in (2, 3):
            hol.append(f"vinterferie veke {d.isocalendar()[1]}")
        p = easter(d.year)
        if c["paskeferie"] and p - dt.timedelta(days=8) <= d <= p + dt.timedelta(days=1):
            hol.append("påskeferie")
        if hol:
            iv = sorted(set(iv) | {tuple(x) for x in c["holidayHours"]})
            why += hol
        return iv, why

    def upcoming(self, now=None, days=14):
        """Liste med dagar framover: dato, intervall, kvifor."""
        now = now or dt.datetime.now()
        out = []
        for i in range(days):
            d = (now + dt.timedelta(days=i)).date()
            iv, why = self.day(d)
            out.append({"date": d.isoformat(), "wd": DAYNAME[d.weekday()], "open": [list(x) for x in iv], "why": why})
        return out

    def next_opening(self, now=None, days=14):
        """Neste opning etter `now` (datetime): (start, slutt, kvifor) eller None."""
        now = now or dt.datetime.now()
        for i in range(days):
            d = (now + dt.timedelta(days=i)).date()
            iv, why = self.day(d)
            for a, b in iv:
                s = dt.datetime.combine(d, _t(a)); e = dt.datetime.combine(d, _t(b))
                if e > now:
                    return s, e, why
        return None


def _t(s):
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def _ok(iv):
    try:
        return len(iv) == 2 and _t(iv[0]) < _t(iv[1])
    except Exception:
        return False


def _date(s):
    try:
        dt.date.fromisoformat(s)
        return True
    except Exception:
        return False


if __name__ == "__main__":     # sjølvtest: python3 opningstid.py
    assert easter(2027) == dt.date(2027, 3, 28) and easter(2026) == dt.date(2026, 4, 5)
    import tempfile
    O = Opningstid(Path(tempfile.mkdtemp()) / "o.json")
    chk = {"2027-01-09": [("10:00", "16:00")],                          # laurdag
           "2027-01-12": [("18:00", "21:00")],                          # tysdag kveld
           "2027-01-14": [],                                            # torsdag – stengt
           "2027-02-24": [("10:00", "16:00"), ("18:00", "21:00")],      # onsdag i vinterferie veke 8
           "2027-03-04": [("10:00", "16:00")],                          # torsdag i vinterferie veke 9
           "2027-03-25": [("10:00", "16:00")],                          # skjærtorsdag
           "2026-12-24": [],                                            # julaftan stengt
           "2026-12-28": [("10:00", "16:00")],                          # juleferie måndag
           "2027-06-05": []}                                            # utanfor sesongen
    for d, want in chk.items():
        got, why = O.day(dt.date.fromisoformat(d))
        print(d, got, why)
        assert got == want, (d, got, want)
    print("neste:", O.next_opening(dt.datetime(2027, 1, 13, 22, 0)))
    print("OK")
