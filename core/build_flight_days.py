"""Build data/flight_days.csv: the last 20 operations of each scheduled flight
(airline + flight number + route) from the raw BTS files (Feb-Mar 2025),
for the track-record timeline on the flight page."""
import glob
import os

import pandas as pd

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
RAW_GLOB = os.path.join(DATASET, "bts_recent", "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_*.csv")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
KEEP = 20

cols = ["FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline", "Origin", "Dest",
        "ArrDelay", "Cancelled", "Diverted"]
df = pd.concat([pd.read_csv(f, usecols=cols, low_memory=False) for f in sorted(glob.glob(RAW_GLOB))],
               ignore_index=True)
df = df.rename(columns={"FlightDate": "date", "Reporting_Airline": "airline",
                        "Flight_Number_Reporting_Airline": "flight_number", "Origin": "origin",
                        "Dest": "dest", "ArrDelay": "arr_delay"})
df["flight_number"] = df.flight_number.astype(int)
df["cancelled"] = df.Cancelled.fillna(0).astype(int)
df["diverted"] = df.Diverted.fillna(0).astype(int)
df = df.drop(columns=["Cancelled", "Diverted"])
k = ["airline", "flight_number", "origin", "dest"]
df = df.sort_values(k + ["date"]).groupby(k).tail(KEEP)
df["arr_delay"] = df.arr_delay.round()
df.to_csv(os.path.join(DATA, "flight_days.csv"), index=False)
print("flight_days.csv: %d rows | %.1f MB" % (len(df), os.path.getsize(os.path.join(DATA, "flight_days.csv")) / 1e6))
print(df[(df.airline == "UA") & (df.flight_number == 2449) & (df.origin == "ORD")].tail(5).to_string(index=False))
