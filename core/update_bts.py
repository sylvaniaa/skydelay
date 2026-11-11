"""Refresh SkyDelay's schedule and track records with the newest BTS months.
BTS publishes each month about 2-3 months late, so this finds the 2 newest months available,
downloads them into dataset/bts_recent (replacing the old ones), then rebuilds
schedule.csv, flight_history.csv and flight_days.csv.
Run any time:  python3 core/update_bts.py   (then restart Streamlit)"""
import glob
import os
import subprocess
import sys
from datetime import date

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
RECENT = os.path.join(DATASET, "bts_recent")
CORE = os.path.dirname(os.path.abspath(__file__))
URL = ("https://transtats.bts.gov/PREZIP/"
       "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip")
N_MONTHS = 2


def months_back(k):
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(k):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append((y, m))
    return out


def published(url):
    r = subprocess.run(["curl", "-sfL", "-A", "Mozilla/5.0", "-r", "0-0", "-o", "/dev/null", url])
    return r.returncode == 0


found = []
for y, m in months_back(10):
    if published(URL.format(y=y, m=m)):
        print("available:        %d-%02d" % (y, m))
        found.append((y, m))
        if len(found) == N_MONTHS:
            break
    else:
        print("not yet published: %d-%02d" % (y, m))
if len(found) < N_MONTHS:
    sys.exit("Could not find %d recent BTS months - check the internet connection." % N_MONTHS)

os.makedirs(RECENT, exist_ok=True)
wanted = set()
for y, m in found:
    csv = "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_%d_%d.csv" % (y, m)
    wanted.add(csv)
    if os.path.exists(os.path.join(RECENT, csv)):
        print("already have %d-%02d" % (y, m))
        continue
    zp = os.path.join(RECENT, "bts_%d_%d.zip" % (y, m))
    print("downloading %d-%02d ..." % (y, m))
    subprocess.run(["curl", "-fL", "-A", "Mozilla/5.0", "-o", zp, URL.format(y=y, m=m)], check=True)
    subprocess.run(["unzip", "-o", "-q", zp, "-d", RECENT], check=True)
    os.remove(zp)
for f in glob.glob(os.path.join(RECENT, "*")):
    if os.path.basename(f) not in wanted:
        os.remove(f)
        print("removed old file:", os.path.basename(f))

for script in ("build_schedule.py", "build_history.py", "build_flight_days.py", "build_home.py"):
    print("\n=== %s ===" % script)
    subprocess.run([sys.executable, os.path.join(CORE, script)], check=True)
print("\nDone. Restart Streamlit to load the new data.")
