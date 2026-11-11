import os
import pandas as pd

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)

print("Reading flights_final.csv ...")
df = pd.read_csv(
    os.path.join(DATASET, "flights_final.csv"),
    usecols=["Year", "Month", "Origin", "Dest", "CRSDepTime", "DepDelay", "ArrDelay"],
    dtype={"Origin": "category", "Dest": "category"},
)
before = len(df)
df = df.dropna(subset=["CRSDepTime", "DepDelay", "ArrDelay"])
print("rows:", len(df), "| dropped:", before - len(df))

# helper columns (NaN is skipped by mean(), so *_late = average of late flights only)
df["dep_ok"] = df.DepDelay <= 15
df["arr_ok"] = df.ArrDelay <= 15
df["dep_late"] = df.DepDelay.where(df.DepDelay > 0)
df["arr_late"] = df.ArrDelay.where(df.ArrDelay > 0)
df["hour"] = (df.CRSDepTime.astype(int) // 100) % 24

keys = ["Year", "Month"]

dep = (df.groupby(["Origin"] + keys, observed=True)
         .agg(n_dep=("DepDelay", "size"),
              avg_dep_delay=("DepDelay", "mean"),
              avg_dep_when_late=("dep_late", "mean"),
              pct_dep_ontime=("dep_ok", "mean"))
         .reset_index().rename(columns={"Origin": "airport"}))

arr = (df.groupby(["Dest"] + keys, observed=True)
         .agg(n_arr=("ArrDelay", "size"),
              avg_arr_delay=("ArrDelay", "mean"),
              avg_arr_when_late=("arr_late", "mean"),
              pct_arr_ontime=("arr_ok", "mean"))
         .reset_index().rename(columns={"Dest": "airport"}))

hourly = (df.groupby(["Origin"] + keys + ["hour"], observed=True)
            .agg(n=("DepDelay", "size"), avg_dep_delay=("DepDelay", "mean"))
            .reset_index().rename(columns={"Origin": "airport"}))

del df

print("Reading flights_emissions.csv ...")
em = pd.read_csv(
    os.path.join(DATASET, "flights_emissions.csv"),
    usecols=["Year", "Month", "Origin", "extra_co2_kg"],
    dtype={"Origin": "category"},
)
co2 = ((em.groupby(["Origin"] + keys, observed=True)["extra_co2_kg"].sum() / 1000)
         .reset_index(name="co2_tonnes").rename(columns={"Origin": "airport"}))

monthly = dep.merge(arr, on=["airport"] + keys, how="outer")
monthly = monthly.merge(co2, on=["airport"] + keys, how="left")
monthly["co2_tonnes"] = monthly["co2_tonnes"].fillna(0)

monthly.to_csv(os.path.join(OUT, "monthly.csv"), index=False)
hourly.to_csv(os.path.join(OUT, "hourly.csv"), index=False)

print("monthly rows:", len(monthly), "| hourly rows:", len(hourly))
print(monthly[(monthly.airport == "ORD") & (monthly.Year == 2024) & (monthly.Month == 9)].T)