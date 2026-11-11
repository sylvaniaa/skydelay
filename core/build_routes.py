import os

import pandas as pd

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)

print("Reading flights_final.csv ...")
df = pd.read_csv(
    os.path.join(DATASET, "flights_final.csv"),
    usecols=["Origin", "Dest", "Reporting_Airline", "Distance"],
    dtype={"Origin": "category", "Dest": "category", "Reporting_Airline": "category"},
)

g = (df.groupby(["Origin", "Dest", "Reporting_Airline"], observed=True)
       .agg(n=("Distance", "size"), distance=("Distance", "median"))
       .reset_index())
g = g[g.n >= 30]   # drop one-off / charter-like routes
g.to_csv(os.path.join(OUT, "routes.csv"), index=False)

print("route-airline rows:", len(g))
print("unique routes:", len(g[["Origin", "Dest"]].drop_duplicates()))
print(g[(g.Origin == "ORD") & (g.Dest == "LAX")])