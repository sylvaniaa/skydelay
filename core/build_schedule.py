"""Build data/schedule.csv from the raw BTS monthly files (Feb-Mar 2025) with real flight
numbers and exact scheduled times. For each flight (airline + number + route) and weekday,
the LATEST timetable in the period is kept; weekdays with identical times are merged into a
weekday mask. Aircraft family comes from tail number -> MODEL (same mapping as training)."""
import glob
import os
import time

import pandas as pd

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
RAW_GLOB = os.path.join(DATASET, "bts_recent", "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_*.csv")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MIN_PER_WEEKDAY = 3   # flight must operate on that weekday at least 3 times in the period
t0 = time.time()

cols = ["FlightDate", "DayOfWeek", "Reporting_Airline", "Tail_Number", "Flight_Number_Reporting_Airline",
        "Origin", "Dest", "CRSDepTime", "CRSArrTime", "CRSElapsedTime", "Distance"]
files = sorted(glob.glob(RAW_GLOB))
print("Reading", len(files), "BTS files ...")
df = pd.concat([pd.read_csv(f, usecols=cols, low_memory=False) for f in files], ignore_index=True)
df = df.dropna(subset=["CRSDepTime", "CRSArrTime", "CRSElapsedTime"])
df = df.rename(columns={"Reporting_Airline": "airline", "Flight_Number_Reporting_Airline": "flight_number",
                        "Origin": "origin", "Dest": "dest", "Distance": "distance"})
for c in ("CRSDepTime", "CRSArrTime", "flight_number", "DayOfWeek"):
    df[c] = df[c].astype(int)
period = "%s to %s" % (df.FlightDate.min(), df.FlightDate.max())
print("rows: %d | %s | %.0fs" % (len(df), period, time.time() - t0))

# ---- aircraft family from tail number (same MODEL mapping as flights_final / training) ----
print("Mapping tail numbers to aircraft ...")
ff = pd.read_csv(os.path.join(DATASET, "flights_final.csv"), usecols=["Year", "Tail_Number", "MODEL"],
                 dtype={"Tail_Number": "category", "MODEL": "category"})
ff = ff[ff.Year >= 2024].dropna(subset=["Tail_Number", "MODEL"])
tail_model = ff.drop_duplicates("Tail_Number", keep="last").set_index("Tail_Number").MODEL.astype(str)
del ff
df["family"] = df.Tail_Number.map(tail_model).astype("object")
df["family"] = df.family.where(df.family.isna(), df.family.astype(str).str.split("-").str[0].str.strip())
print("tail matched: %.1f%% | %.0fs" % (100 * df.family.notna().mean(), time.time() - t0))

flight = ["airline", "flight_number", "origin", "dest"]
fam = (df.dropna(subset=["family"]).groupby(flight + ["family"]).size().reset_index(name="c")
         .sort_values("c").drop_duplicates(flight, keep="last")[flight + ["family"]])

# ---- latest timetable per flight and weekday ----
k = flight + ["DayOfWeek"]
n_wd = df.groupby(k).size().reset_index(name="n_wd")
latest = df.sort_values("FlightDate").drop_duplicates(k, keep="last")[
    k + ["CRSDepTime", "CRSArrTime", "CRSElapsedTime", "distance"]]
wd = latest.merge(n_wd, on=k)
wd = wd[wd.n_wd >= MIN_PER_WEEKDAY].copy()
wd["bit"] = 2 ** (wd.DayOfWeek - 1)            # Mon=1 ... Sun=64

g = flight + ["CRSDepTime", "CRSArrTime"]
sch = wd.groupby(g).agg(dow_mask=("bit", "sum"), n_days=("n_wd", "sum"),
                        block_min=("CRSElapsedTime", "median"), distance=("distance", "median")).reset_index()
sch = sch.merge(fam, on=flight, how="left")
sch = sch.rename(columns={"CRSDepTime": "dep_hhmm", "CRSArrTime": "arr_hhmm"})
sch["dep_hhmm"] = sch.dep_hhmm % 2400
sch["arr_hhmm"] = sch.arr_hhmm % 2400
sch["dep_time"] = sch.dep_hhmm.map(lambda v: "%02d:%02d" % (v // 100, v % 100))
sch["arr_time"] = sch.arr_hhmm.map(lambda v: "%02d:%02d" % (v // 100, v % 100))
sch["block_min"] = sch.block_min.round().astype(int)
sch["n_flights"] = sch.n_days
sch["period"] = period
out_cols = ["origin", "dest", "airline", "flight_number", "dep_hhmm", "dep_time", "arr_hhmm", "arr_time",
            "block_min", "distance", "family", "n_flights", "n_days", "dow_mask", "period"]
sch = sch[out_cols].sort_values(["origin", "dest", "dep_hhmm", "airline"])
sch.to_csv(os.path.join(DATA, "schedule.csv"), index=False)

print("\nSaved schedule.csv | %d flights | %d routes | %d airports | %.0fs" % (
    len(sch), sch[["origin", "dest"]].drop_duplicates().shape[0],
    len(set(sch.origin) | set(sch.dest)), time.time() - t0))
thu = sch[(sch.origin == "ORD") & (sch.dest == "LAX") & ((sch.dow_mask & 8) > 0)]
print("\nORD -> LAX on a Thursday: %d flights" % len(thu))
print(thu[["airline", "flight_number", "dep_time", "arr_time", "block_min", "family", "dow_mask"]].to_string(index=False))
