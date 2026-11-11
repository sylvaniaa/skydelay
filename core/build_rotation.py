"""Aircraft rotation for US flights: which flight of the day this is for its aircraft (tail number),
and how many flights that aircraft flies that day.
Sources: BTS Marketing Carrier On-Time Performance Jun-Jul 2026 (main; marketing + operating codes),
         BTS Reporting Carrier On-Time Performance Feb-Mar 2025 (only for flights not in the 2026 data).
Outputs: data/rotation_us.csv       per flight (airline, flight_number, origin, dest, dep_hhmm, leg, legs_day, n)
         data/rotation_us_hour.csv  per airline + origin + hour: most common position and its share (in 10)
Legs are ordered by local scheduled departure within the local departure date (approximation across time zones)."""
import glob
import os
import time

import pandas as pd

DS = os.path.expanduser("~/Documents/FYP/dataset")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MIN_SEEN, MIN_HOUR = 3, 20
t0 = time.time()


def legs(df):
    df = df.dropna(subset=["Tail_Number", "dep_hhmm"]).drop_duplicates(["Tail_Number", "FlightDate", "origin", "dep_hhmm"])
    df = df.sort_values(["Tail_Number", "FlightDate", "dep_hhmm"])
    g = df.groupby(["Tail_Number", "FlightDate"], sort=False)
    df["leg"] = g.cumcount() + 1
    df["legs_day"] = g["dep_hhmm"].transform("size")
    return df


def per_flight(df, airline_col, fn_col):
    key = [airline_col, fn_col, "origin", "dest", "dep_hhmm"]
    r = (df.groupby(key).agg(leg=("leg", "median"), legs_day=("legs_day", "median"), n=("leg", "size"))
           .reset_index().rename(columns={airline_col: "airline", fn_col: "flight_number"}))
    return r[r.n >= MIN_SEEN]


# ---- 2026 marketing-carrier files (main) ----
mk_cols = ["FlightDate", "IATA_Code_Marketing_Airline", "Flight_Number_Marketing_Airline",
           "IATA_Code_Operating_Airline", "Flight_Number_Operating_Airline", "Tail_Number",
           "Origin", "Dest", "CRSDepTime"]
files = sorted(glob.glob(os.path.join(DS, "bts_marketing", "*.csv")))
print("Reading", len(files), "BTS 2026 files ...")
new = pd.concat([pd.read_csv(f, usecols=mk_cols, low_memory=False) for f in files], ignore_index=True)
new = new.rename(columns={"Origin": "origin", "Dest": "dest", "CRSDepTime": "dep_hhmm"}).dropna(subset=["dep_hhmm"])
for c in ("Flight_Number_Marketing_Airline", "Flight_Number_Operating_Airline", "dep_hhmm"):
    new[c] = new[c].astype(int)
new = legs(new)
print("2026 rows with tail number: %d | %.0fs" % (len(new), time.time() - t0))
rot_new = pd.concat([per_flight(new, "IATA_Code_Marketing_Airline", "Flight_Number_Marketing_Airline"),
                     per_flight(new, "IATA_Code_Operating_Airline", "Flight_Number_Operating_Airline")])
rot_new = rot_new.drop_duplicates(["airline", "flight_number", "origin", "dest", "dep_hhmm"])

# ---- 2025 reporting-carrier files (fallback for flights missing in 2026) ----
old_cols = ["FlightDate", "Reporting_Airline", "Tail_Number", "Flight_Number_Reporting_Airline", "Origin", "Dest", "CRSDepTime"]
ofiles = sorted(glob.glob(os.path.join(DS, "bts_recent", "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_*.csv")))
old = pd.concat([pd.read_csv(f, usecols=old_cols, low_memory=False) for f in ofiles], ignore_index=True)
old = old.rename(columns={"Origin": "origin", "Dest": "dest", "CRSDepTime": "dep_hhmm"}).dropna(subset=["dep_hhmm"])
old["Flight_Number_Reporting_Airline"] = old.Flight_Number_Reporting_Airline.astype(int)
old["dep_hhmm"] = old.dep_hhmm.astype(int)
rot_old = per_flight(legs(old), "Reporting_Airline", "Flight_Number_Reporting_Airline")

key = ["airline", "flight_number", "origin", "dest", "dep_hhmm"]
rot = pd.concat([rot_new.assign(src="2026"), rot_old.assign(src="2025")]).drop_duplicates(key, keep="first")
rot["leg"] = rot.leg.round().astype(int)
rot["legs_day"] = rot.legs_day.round().astype(int)
rot.to_csv(os.path.join(DATA, "rotation_us.csv"), index=False)
print("flights with rotation: %d (2026: %d, 2025 only: %d)" % (len(rot), (rot.src == "2026").sum(), (rot.src == "2025").sum()))

# ---- fallback: airline + origin + hour (marketing and operating codes) ----
rows = []
for a_col in ("IATA_Code_Marketing_Airline", "IATA_Code_Operating_Airline"):
    x = new.assign(hour=new.dep_hhmm // 100)
    for (a, o, h), grp in x.groupby([a_col, "origin", "hour"]):
        if len(grp) < MIN_HOUR:
            continue
        vc = grp.leg.value_counts()
        rows.append({"airline": a, "origin": o, "hour": int(h), "leg": int(vc.index[0]),
                     "share10": int(round(10 * vc.iloc[0] / len(grp))), "n": len(grp)})
hr = pd.DataFrame(rows).drop_duplicates(["airline", "origin", "hour"])
hr.to_csv(os.path.join(DATA, "rotation_us_hour.csv"), index=False)
print("airline-airport-hour groups: %d | %.0fs" % (len(hr), time.time() - t0))
print(hr[(hr.airline == "AA") & (hr.origin == "ORD")].sort_values("hour").to_string(index=False))
