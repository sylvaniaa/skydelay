import os
import re

import pandas as pd

BASE = os.path.expanduser("~/Documents/FYP/dataset/Eurocontrol")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)

print("Reading eurocontrol_flights_clean.csv ...")
cols = ["ADEP", "ADES", "FILED OFF BLOCK TIME", "source_file", "dep_delay_min", "arr_delay_min"]
df = pd.read_csv(os.path.join(BASE, "eurocontrol_flights_clean.csv"), usecols=cols,
                 dtype={"ADEP": "category", "ADES": "category", "source_file": "category"})
df = df.dropna(subset=["dep_delay_min", "arr_delay_min", "FILED OFF BLOCK TIME"])
print("rows:", len(df))

# year / month from the source file name (Flights_YYYYMMDD_...)
parsed = {c: tuple(int(x) for x in re.match(r"Flights_(\d{4})(\d{2})", c).groups())
          for c in df.source_file.cat.categories}
df["Year"] = df.source_file.map({c: v[0] for c, v in parsed.items()}).astype(int)
df["Month"] = df.source_file.map({c: v[1] for c, v in parsed.items()}).astype(int)
print("months:", sorted(set(parsed.values())))

# "Europe" = ICAO prefixes E*, L* (and BI* Iceland)
def european(codes):
    return {c for c in codes if c[0] in "EL" or c.startswith("BI")}

eu_dep = european(df.ADEP.cat.categories)
eu_arr = european(df.ADES.cat.categories)

df["dep_ok"] = df.dep_delay_min <= 15
df["arr_ok"] = df.arr_delay_min <= 15
df["dep_late"] = df.dep_delay_min.where(df.dep_delay_min > 0)
df["arr_late"] = df.arr_delay_min.where(df.arr_delay_min > 0)
keys = ["Year", "Month"]

d = df[df.ADEP.isin(eu_dep)]
dep = (d.groupby(["ADEP"] + keys, observed=True)
         .agg(n_dep=("dep_delay_min", "size"),
              avg_dep_delay=("dep_delay_min", "mean"),
              avg_dep_when_late=("dep_late", "mean"),
              pct_dep_ontime=("dep_ok", "mean"))
         .reset_index().rename(columns={"ADEP": "airport"}))

a = df[df.ADES.isin(eu_arr)]
arr = (a.groupby(["ADES"] + keys, observed=True)
         .agg(n_arr=("arr_delay_min", "size"),
              avg_arr_delay=("arr_delay_min", "mean"),
              avg_arr_when_late=("arr_late", "mean"),
              pct_arr_ontime=("arr_ok", "mean"))
         .reset_index().rename(columns={"ADES": "airport"}))

d = d.assign(hour=pd.to_datetime(d["FILED OFF BLOCK TIME"]).dt.hour)   # UTC
hourly = (d.groupby(["ADEP"] + keys + ["hour"], observed=True)
            .agg(n=("dep_delay_min", "size"), avg_dep_delay=("dep_delay_min", "mean"))
            .reset_index().rename(columns={"ADEP": "airport"}))
del df, d, a

print("Reading eurocontrol_flights_emissions.csv ...")
em = pd.read_csv(os.path.join(BASE, "eurocontrol_flights_emissions.csv"),
                 usecols=["ADEP", "source_file", "extra_co2_kg"],
                 dtype={"ADEP": "category", "source_file": "category"})
p2 = {c: tuple(int(x) for x in re.match(r"Flights_(\d{4})(\d{2})", c).groups())
      for c in em.source_file.cat.categories}
em["Year"] = em.source_file.map({c: v[0] for c, v in p2.items()}).astype(int)
em["Month"] = em.source_file.map({c: v[1] for c, v in p2.items()}).astype(int)
co2 = ((em.groupby(["ADEP"] + keys, observed=True)["extra_co2_kg"].sum() / 1000)
         .reset_index(name="co2_tonnes").rename(columns={"ADEP": "airport"}))

monthly = dep.merge(arr, on=["airport"] + keys, how="outer")
monthly = monthly.merge(co2, on=["airport"] + keys, how="left")
monthly["co2_tonnes"] = monthly["co2_tonnes"].fillna(0)

monthly.to_csv(os.path.join(OUT, "monthly_eu.csv"), index=False)
hourly.to_csv(os.path.join(OUT, "hourly_eu.csv"), index=False)

print("monthly rows:", len(monthly), "| hourly rows:", len(hourly), "| airports:", monthly.airport.nunique())
top = monthly.groupby("airport")["n_dep"].sum().sort_values(ascending=False).head(10)
print(top)
print(monthly[(monthly.airport == "EGLL") & (monthly.Year == 2023) & (monthly.Month == 9)].T)