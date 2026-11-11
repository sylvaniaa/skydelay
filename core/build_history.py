"""Build data/flight_history.csv: what actually happened to each scheduled flight
(airline + flight number + route) in the raw BTS files (Feb-Mar 2025):
operated, on time (<=15 min late), delayed, cancelled, diverted, median delay when late."""
import glob
import os

import pandas as pd

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
RAW_GLOB = os.path.join(DATASET, "bts_recent", "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_*.csv")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

cols = ["FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline", "Origin", "Dest",
        "ArrDelay", "Cancelled", "Diverted"]
df = pd.concat([pd.read_csv(f, usecols=cols, low_memory=False) for f in sorted(glob.glob(RAW_GLOB))],
               ignore_index=True)
df = df.rename(columns={"Reporting_Airline": "airline", "Flight_Number_Reporting_Airline": "flight_number",
                        "Origin": "origin", "Dest": "dest"})
df["flight_number"] = df.flight_number.astype(int)
df["cancelled"] = df.Cancelled.fillna(0).astype(int)
df["diverted"] = df.Diverted.fillna(0).astype(int)
flown = (df.cancelled == 0) & (df.diverted == 0) & df.ArrDelay.notna()
df["on_time"] = (flown & (df.ArrDelay <= 15)).astype(int)
df["delayed"] = (flown & (df.ArrDelay > 15)).astype(int)
df["late_min"] = df.ArrDelay.where(df.delayed == 1)

k = ["airline", "flight_number", "origin", "dest"]
h = df.groupby(k).agg(n=("FlightDate", "size"), on_time=("on_time", "sum"), delayed=("delayed", "sum"),
                      cancelled=("cancelled", "sum"), diverted=("diverted", "sum"),
                      median_late=("late_min", "median"), first=("FlightDate", "min"),
                      last=("FlightDate", "max")).reset_index()
h["median_late"] = h.median_late.round()
h.to_csv(os.path.join(DATA, "flight_history.csv"), index=False)

tot = h[["n", "on_time", "delayed", "cancelled", "diverted"]].sum()
print("flight_history.csv: %d flights | %d operations" % (len(h), tot.n))
print("overall: on time %.1f%% | delayed %.1f%% | cancelled %.1f%% | diverted %.1f%%" % tuple(
    100 * tot[c] / tot.n for c in ["on_time", "delayed", "cancelled", "diverted"]))
print("\nORD -> LAX examples:")
print(h[(h.origin == "ORD") & (h.dest == "LAX")].sort_values("n", ascending=False).head(6).to_string(index=False))
