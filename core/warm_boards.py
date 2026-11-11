"""Pre-compute the departures-board forecasts (today + tomorrow) for the busiest US/EU airports into
data/board_cache, so the board and the ticker open instantly. Run: /usr/bin/python3 core/warm_boards.py [N]"""
import os
import sys
import time
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from views.airport import board_predictions  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(n=40):
    ap = pd.read_csv(os.path.join(BASE, "data", "home_airports.csv"))
    ap = ap[ap.region.isin(["US", "EU"])].sort_values("sort", ascending=False).drop_duplicates("code").head(n)
    t_all = time.time()
    for k, code in enumerate(ap.code, 1):
        t0, cnt = time.time(), 0
        for d in (date.today(), date.today() + timedelta(days=1)):
            try:
                cnt += len(board_predictions(code, d.isoformat(), 0, 24))
            except Exception as e:
                print(f"  {code} {d}: {type(e).__name__} {e}")
        print(f"[warm] {k:>2}/{len(ap)} {code}: {cnt} flights in {time.time() - t0:.1f}s", flush=True)
    print(f"[warm] done in {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
