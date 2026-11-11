"""Whole-flight fuel per aircraft type and distance, from the EMEP/EEA Air Pollutant Emission Inventory
Guidebook 2023, 1.A.3.a Aviation, Annex 1 Master emissions calculator (EUROCONTROL, baseline 2022).
  CCD = climb, cruise and descent at standard stage lengths (ADES, nautical miles)
  LTO = landing and take-off cycle (incl. taxi), once per flight
Whole flight = CCD(distance, linear interpolation) + LTO.
Output: data/trip_fuel.csv (ac_type, ades_nm, ccd_fuel_kg, lto_fuel_kg)"""
import glob
import os
import sys

import numpy as np
import pandas as pd

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
from core import predict as pr  # noqa: E402

DS = os.path.expanduser("~/Documents/FYP/dataset")
f = glob.glob(os.path.join(DS, "*Master emissions calculator*.xlsx"))[0]
print("Reading", os.path.basename(f))
db = pd.read_excel(f, sheet_name="database", header=1)
db.columns = [str(c).strip() for c in db.columns]
fuel_col = next(c for c in db.columns if "FUEL BURNT" in c)
db = db[db["Engine Type"].astype(str).str.strip().str.upper() == "JET"].copy()
db["ac_type"] = db["IMPACT ACFT ID"].astype(str).str.strip()
kind = db["LTO or CCD"].astype(str).str.strip().str.upper()

ccd = (db[kind == "CCD"].groupby(["ac_type", "ADES"])[fuel_col].mean()
       .reset_index().rename(columns={"ADES": "ades_nm", fuel_col: "ccd_fuel_kg"}))
lto = db[kind == "LTO"].groupby("ac_type")[fuel_col].mean().rename("lto_fuel_kg")
print(f"CCD rows: {len(ccd)} | aircraft with CCD: {ccd.ac_type.nunique()} | with LTO: {len(lto)}")
out = ccd.merge(lto, left_on="ac_type", right_index=True, how="left")
out.to_csv(os.path.join(APP, "data", "trip_fuel.csv"), index=False)


def trip_co2_pp(ac, nm):
    g = out[out.ac_type == ac].sort_values("ades_nm")
    if g.empty:
        return None
    x, y = g.ades_nm.values.astype(float), g.ccd_fuel_kg.values
    ccd_kg = float(np.interp(nm, x, y)) if nm >= x[0] else float(y[0] * nm / x[0])
    fuel = ccd_kg + float(g.lto_fuel_kg.iloc[0] if pd.notna(g.lto_fuel_kg.iloc[0]) else 0)
    seats = pr.seats(pr.icao_family(ac))
    return fuel, fuel * 3.16, fuel * 3.16 / seats, seats


print("\nExamples (whole flight):")
for label, ac, nm in [("ORD-LAX  A321", "A321", 1515), ("ORD-LAX  B738", "B738", 1515),
                      ("JFK-LHR  B77W", "B77W", 2999), ("LHR-JFK  A21N", "A21N", 2999),
                      ("BCN-PMI  A320", "A320", 111), ("LHR-DXB  A388", "A388", 2967)]:
    r = trip_co2_pp(ac, nm)
    if r is None:
        print(f"  {label}: type not in EEA table")
        continue
    fuel, co2, pp, seats = r
    print(f"  {label} {nm:5d} NM: fuel {fuel:8,.0f} kg | CO2 {co2 / 1000:6.1f} t | "
          f"{pp:5.0f} kg per seat ({seats} seats) | {fuel / (nm * 1.852):.1f} kg fuel/km")

US_REP = {"737": "B738", "A320": "A320", "A321": "A321", "A319": "A319", "757": "B752", "717": "B712",
          "767": "B763", "777": "B77W", "787": "B789", "A330": "A333", "A350": "A359", "CL": "CRJ9",
          "ERJ 170": "E75L", "ERJ 190": "E190", "EMB": "E145", "BD": "BCS3"}
have = set(out.ac_type)
print("\nUS family -> EEA type:", {k: (v if v in have else f"{v} MISSING") for k, v in US_REP.items()})
eu_types = set(pr.eu_schedule().ac_type.astype(str))
missing = sorted(eu_types - have)
print(f"EU schedule aircraft types: {len(eu_types)} | missing in EEA table: {missing}")
print("\nSaved data/trip_fuel.csv")
