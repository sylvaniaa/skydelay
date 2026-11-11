"""Build data/marketing_map.csv: operating flight (carrier, number, origin, dest) -> marketing carrier
and flight number, from BTS Marketing Carrier On-Time Performance (dataset/bts_marketing/*.csv)."""
import glob
import os

import pandas as pd

SRC = os.path.expanduser("~/Documents/FYP/dataset/bts_marketing")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "marketing_map.csv")
COLS = ["IATA_Code_Marketing_Airline", "Flight_Number_Marketing_Airline", "IATA_Code_Operating_Airline",
        "Flight_Number_Operating_Airline", "Origin", "Dest"]

df = pd.concat([pd.read_csv(f, usecols=COLS, low_memory=False) for f in sorted(glob.glob(os.path.join(SRC, "*.csv")))])
df = df.dropna()
df.columns = ["mkt", "mkt_fn", "op", "op_fn", "origin", "dest"]
df["mkt_fn"] = df.mkt_fn.astype(int)
df["op_fn"] = df.op_fn.astype(int)
m = (df.groupby(["op", "op_fn", "origin", "dest", "mkt", "mkt_fn"]).size().reset_index(name="n")
       .sort_values("n", ascending=False).drop_duplicates(["op", "op_fn", "origin", "dest"]))
m.drop(columns="n").to_csv(OUT, index=False)
print(f"{len(m):,} flights mapped; {(m.op != m.mkt).sum():,} sold by another airline")
print(m[m.op != m.mkt].head(8).to_string(index=False))
