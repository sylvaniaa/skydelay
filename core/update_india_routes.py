"""Rebuild data/india_routes.csv passenger counts from the latest 12 months of DGCA city-pair files
(dataset/dgca_raw/*CITYPAIR*.xlsx), so 'pax' = passengers per year. Keeps mult and ratio from the old file."""
import glob
import os
import re

import pandas as pd

RAW = os.path.expanduser("~/Documents/FYP/dataset/dgca_raw")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "india_routes.csv")
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def ym(path):
    name = os.path.basename(path).upper()
    y = re.findall(r"20\d\d", name)
    toks = [t for t in re.split(r"[^A-Z]+", name) if t]
    m = next((i + 1 for t in toks for i, k in enumerate(MON) if t.startswith(k)), None)
    return (int(y[-1]), m) if y and m else None


files = {}
for f in glob.glob(os.path.join(RAW, "*CITYPAIR*.xlsx")):
    k = ym(f)
    if k:
        files[k] = f
last = sorted(files)[-12:]
print("Months used:", ", ".join(f"{MON[m - 1].title()} {y}" for y, m in last))

old = pd.read_csv(OUT)
known = set(old.city1) | set(old.city2)


def city(x):
    x = str(x).strip()
    m = re.match(r"^(.*?)\s*\((.*?)\)\s*$", x)
    if not m:
        return x
    a, b = m.group(1).strip(), m.group(2).strip()
    return a if a in known else b if b in known else a


def read(f):
    x = pd.read_excel(f, header=None)
    hdr = next(i for i in range(10) if any(str(v).strip().upper() == "CITY 1" for v in x.iloc[i]))
    cols = [re.sub(r"\s+", " ", str(v)).strip().upper() for v in x.iloc[hdr]]
    x = x.iloc[hdr + 1:].copy()
    x.columns = cols
    to = next(c for c in cols if c.startswith("PASSENGERS") and " TO " in f" {c} ")
    fr = next(c for c in cols if c.startswith("PASSENGERS") and "FROM" in c)
    x = x[x["CITY 1"].notna() & x["CITY 2"].notna()]
    x = x[~x["CITY 1"].astype(str).str.upper().str.contains("TOTAL")]
    p = pd.to_numeric(x[to], errors="coerce").fillna(0) + pd.to_numeric(x[fr], errors="coerce").fillna(0)
    c1, c2 = x["CITY 1"].map(city), x["CITY 2"].map(city)
    return pd.DataFrame({"city1": [min(u, v) for u, v in zip(c1, c2)],
                         "city2": [max(u, v) for u, v in zip(c1, c2)], "pax": p.values})


new = pd.concat([read(files[k]) for k in last]).groupby(["city1", "city2"], as_index=False).pax.sum()
new = new[(new.city1 != new.city2) & (new.pax > 0)]

o = old.copy()
o["k1"] = [min(a, b) for a, b in zip(o.city1, o.city2)]
o["k2"] = [max(a, b) for a, b in zip(o.city1, o.city2)]
o = o.groupby(["k1", "k2"], as_index=False).agg(ratio=("ratio", "first"), mult=("mult", "first"))
new = new.merge(o, left_on=["city1", "city2"], right_on=["k1", "k2"], how="left").drop(columns=["k1", "k2"])
new["mult"] = new.mult.fillna(1.0)

tot = new.pax.sum()
print(f"Total domestic passengers, 12 months: {tot / 1e6:,.1f} M")
if not 80e6 < tot < 300e6:
    raise SystemExit("ABORT: total looks wrong, india_routes.csv NOT changed")
new.sort_values("pax", ascending=False)[["city1", "city2", "pax", "ratio", "mult"]].to_csv(OUT, index=False)

d = new[(new.city1 == "Delhi") | (new.city2 == "Delhi")]
print(f"Delhi: {d.pax.sum() / 1e6:,.1f} M passengers/yr, {len(d)} routes")
print(new.sort_values("pax", ascending=False).head(5).to_string(index=False))
print(f"Pairs: {len(new)} (old file: {len(old)}); pairs without old mult: {new.ratio.isna().sum()}")
