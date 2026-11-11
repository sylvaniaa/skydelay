"""Build data/airports_lookup.csv (city, region, country, time zone per IATA code)
and data/route_times.csv (scheduled block time per route) for the flight finder.
Block times: median CRSElapsedTime from the raw BTS Jan 2023 file; routes not in
that file are estimated from distance with a linear fit (marked 'estimated')."""
import os

import airportsdata
import numpy as np
import pandas as pd
import pycountry

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW = os.path.join(DATASET, "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_2023_1.csv")

# ---------- airports ----------
rows = []
for code, a in airportsdata.load("IATA").items():
    c = pycountry.countries.get(alpha_2=a["country"])
    country = (getattr(c, "common_name", None) or c.name) if c else a["country"]
    name = a["name"].replace(" International Airport", " International").replace(" Airport", "")
    rows.append({"iata": code, "airport": name, "city": a["city"], "region": a["subd"],
                 "country": country, "country_code": a["country"], "tz": a["tz"],
                 "lat": a["lat"], "lon": a["lon"]})
lk = pd.DataFrame(rows)
lk.to_csv(os.path.join(DATA, "airports_lookup.csv"), index=False)

sch = pd.read_csv(os.path.join(DATA, "schedule.csv"))
codes = set(sch.origin) | set(sch.dest)
missing = sorted(codes - set(lk.iata))
print("airports_lookup.csv: %d airports | schedule airports covered: %d/%d" % (
    len(lk), len(codes) - len(missing), len(codes)))
if missing:
    print("  missing:", missing[:30])
print(lk[lk.iata.isin(["ORD", "JFK", "LAX", "CGK", "DPS"])][
    ["iata", "airport", "city", "region", "country", "tz"]].to_string(index=False))

# ---------- route block times ----------
raw = pd.read_csv(RAW, usecols=["Origin", "Dest", "CRSElapsedTime"], low_memory=False).dropna()
bts = raw.groupby(["Origin", "Dest"]).CRSElapsedTime.median().reset_index()
bts.columns = ["origin", "dest", "block_min"]

routes = sch.groupby(["origin", "dest"]).distance.median().reset_index()
rt = routes.merge(bts, on=["origin", "dest"], how="left")
known = rt.dropna(subset=["block_min"])
slope, icpt = np.polyfit(known.distance, known.block_min, 1)
rt["source"] = np.where(rt.block_min.isna(), "estimated", "BTS Jan 2023")
rt["block_min"] = rt.block_min.fillna(icpt + slope * rt.distance).round().astype(int)
rt.to_csv(os.path.join(DATA, "route_times.csv"), index=False)

print("\nroute_times.csv: %d routes | from BTS: %d | estimated: %d" % (
    len(rt), (rt.source == "BTS Jan 2023").sum(), (rt.source == "estimated").sum()))
print("distance fit: block_min = %.1f + %.4f x miles" % (icpt, slope))
ex = rt[rt.origin.isin(["ORD", "JFK"]) & rt.dest.isin(["LAX", "SFO"])]
print(ex.to_string(index=False))
