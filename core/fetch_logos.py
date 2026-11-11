"""Download missing airline logos into data/logos/<IATA>.png.
Codes = every airline the app can show: US/EU schedules, Australia (BITRE), all Ignav cached itineraries,
plus major world carriers. Sources: Google Flights logo CDN, then Aviasales CDN."""
import glob
import json
import os
import urllib.request

import pandas as pd

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(APP, "data")
LOGOS = os.path.join(DATA, "logos")
SOURCES = ["https://www.gstatic.com/flights/airline_logos/70px/{c}.png",
           "https://pics.avs.io/200/200/{c}.png"]
MAJOR = ("QF JQ VA ZL QN EK QR EY SQ TR CX KA NH JL KE OZ CI BR MH AK D7 GA ID QZ JT TG FD VN VJ PR 5J "
         "AI 6E SG UK IX QP TK LH LX OS SN LO AY SK DY D8 FR U2 W6 VY IB AZ TP EI BA VS AF KL "
         "AC WS TS PD AM Y4 VB LA JJ AV CM AR G3 AD ET KQ MS SA AT RJ GF WY SV XY FZ G9 J9 "
         "UL KU MU CA CZ HU FM 3U ZH MF HO 9C NZ FJ NF").split()


def codes():
    out = set(MAJOR)
    for f, col in [("schedule.csv", "airline"), ("eu_schedule.csv", "airline_iata"), ("au_routes.csv", "airline")]:
        try:
            out |= set(pd.read_csv(os.path.join(DATA, f), usecols=[col])[col].dropna().astype(str))
        except Exception:
            pass
    for p in glob.glob(os.path.join(DATA, "ignav_cache", "*.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        for it in (d.get("itineraries") or []):
            for s in (it.get("outbound") or {}).get("segments", []):
                for k in ("marketing_carrier_code", "operating_carrier_code"):
                    if s.get(k):
                        out.add(str(s[k]))
    return {c for c in out if len(c) == 2 and c.isalnum() and c != "ALL"}


def fetch(code):
    """Download one logo; True when saved."""
    os.makedirs(LOGOS, exist_ok=True)
    for src in SOURCES:
        try:
            req = urllib.request.Request(src.format(c=code), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                b = r.read()
            if len(b) > 300 and b[:8] == b"\x89PNG\r\n\x1a\n":
                open(os.path.join(LOGOS, code + ".png"), "wb").write(b)
                return True
        except Exception:
            continue
    return False


if __name__ == "__main__":
    need = sorted(c for c in codes() if not os.path.exists(os.path.join(LOGOS, c + ".png")))
    print(f"airline codes: {len(codes())} | missing logos: {len(need)}")
    ok, fail = [], []
    for c in need:
        (ok if fetch(c) else fail).append(c)
    print(f"downloaded {len(ok)}: {' '.join(ok)}")
    print(f"not found {len(fail)}: {' '.join(fail)}")
