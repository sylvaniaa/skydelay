"""Build the Europe schedule, flight history, airport lookup and model base from EUROCONTROL.

Input : dataset/Eurocontrol/eurocontrol_flights_final.csv (cleaned, EEDB-matched jets)
        data/ref/airports.csv + countries.csv (OurAirports), data/ref/airlines.dat (OpenFlights)
Output: data/eu_schedule.csv, data/eu_flight_history.csv.gz, data/eu_airports.csv,
        dataset/Eurocontrol/eu_model_base.csv.gz (for core/train_bands_eu.py)
Notes : EUROCONTROL times are UTC -> converted to local time at each airport.
        Delay = actual arrival vs FILED arrival (flight plan), not the airline timetable.
        No flight numbers: a "service" = airline + route + filed departure time (5-min rounded).
        Timetable per calendar month = latest sampled year (Mar/Jun 2024, Sep/Dec 2023).
"""
import os
import pandas as pd
from timezonefinder import TimezoneFinder

APP = os.path.expanduser("~/Documents/FYP/skydelay_app")
DS = os.path.expanduser("~/Documents/FYP/dataset/Eurocontrol")
SRC = os.path.join(DS, "eurocontrol_flights_clean.csv")   # all aircraft types (final = EEDB-matched only)
REF = os.path.join(APP, "data", "ref")
OUT = os.path.join(APP, "data")
MIN_OPS = 3  # same rule as the US schedule: >= 3 operations per weekday

# ---------- 1. flights ----------
print("Loading flights ...")
cols = ["ADEP", "ADES", "FILED OFF BLOCK TIME", "FILED ARRIVAL TIME", "AC Operator",
        "ICAO Flight Type", "Actual Distance Flown (nm)", "dep_delay_min", "arr_delay_min",
        "AC Type"]
cat = {c: "category" for c in ["ADEP", "ADES", "AC Operator", "ICAO Flight Type", "AC Type"]}
df = pd.read_csv(SRC, usecols=cols, dtype=cat)
df = df[(df["ICAO Flight Type"] == "S") & (df["AC Operator"] != "ZZZ")].drop(columns="ICAO Flight Type")
df = df.rename(columns={"AC Operator": "airline_icao", "Actual Distance Flown (nm)": "dist_nm",
                        "AC Type": "ac_type"})
for c in ["FILED OFF BLOCK TIME", "FILED ARRIVAL TIME"]:
    df[c] = pd.to_datetime(df[c], format="%Y-%m-%d %H:%M:%S", errors="coerce")
df = df.dropna(subset=["FILED OFF BLOCK TIME", "FILED ARRIVAL TIME", "arr_delay_min"])
print(f"  scheduled flights with a known airline: {len(df):,}")

# engine data for delay CO2: EEDB-matched types (from the final file); other jets borrow the
# closest matched type; turboprops and business jets are not in EEDB -> no CO2 estimate
FUEL = (pd.read_csv(os.path.join(DS, "eurocontrol_flights_final.csv"),
                    usecols=["AC_Type", "Fuel_Flow_Idle_kg_sec", "Engine_Count"])
        .drop_duplicates("AC_Type").set_index("AC_Type"))
NEAREST = {  # type: (matched type, engine count override)
    "B788": ("A359", None), "B789": ("A359", None), "B78X": ("A359", None),
    "A332": ("A339", None), "A333": ("A339", None), "A338": ("A339", None),
    "B762": ("A339", None), "B763": ("A339", None), "B764": ("A339", None),
    "B772": ("B77L", None), "B773": ("B77W", None),
    "A388": ("B748", 4), "B744": ("B748", 4),
    "A342": ("A343", None), "A345": ("A343", None), "A346": ("A343", None),
    "B752": ("A321", None), "B753": ("A321", None), "B736": ("B737", None), "A318": ("A319", None),
    "B37M": ("B38M", None), "B39M": ("B38M", None), "CRJ2": ("CRJ9", None), "CRJ7": ("CRJ9", None),
    "E290": ("E295", None),
}
_t = df["ac_type"].astype(str)
fmap = {}
for t in _t.unique():
    if t in FUEL.index:
        fmap[t] = (float(FUEL.at[t, "Fuel_Flow_Idle_kg_sec"]), float(FUEL.at[t, "Engine_Count"]))
    elif t in NEAREST and NEAREST[t][0] in FUEL.index:
        b, n = NEAREST[t]
        fmap[t] = (float(FUEL.at[b, "Fuel_Flow_Idle_kg_sec"]), float(n or FUEL.at[b, "Engine_Count"]))
df["Fuel_Flow_Idle_kg_sec"] = _t.map(lambda t: fmap.get(t, (None, None))[0]).astype(float)
df["Engine_Count"] = _t.map(lambda t: fmap.get(t, (None, None))[1]).astype(float)
print(f"  aircraft types: {_t.nunique()} | with engine data: {len(fmap)} | "
      f"flights with engine data: {df['Fuel_Flow_Idle_kg_sec'].notna().mean():.0%}")

# ---------- 2. airports + time zones ----------
ap = pd.read_csv(os.path.join(REF, "airports.csv"), keep_default_na=False, na_values=[""],
                 usecols=["ident", "name", "latitude_deg", "longitude_deg", "continent",
                          "iso_country", "municipality", "iata_code"])
ct = pd.read_csv(os.path.join(REF, "countries.csv"), keep_default_na=False, usecols=["code", "name"])
ap = ap.merge(ct.rename(columns={"code": "iso_country", "name": "country"}), on="iso_country", how="left")
codes = set(df["ADEP"].astype(str)) | set(df["ADES"].astype(str))
ap = ap[ap["ident"].isin(codes)].drop_duplicates("ident").set_index("ident")
tf = TimezoneFinder()
ap["tz"] = [tf.timezone_at(lng=lo, lat=la) or "UTC"
            for la, lo in zip(ap["latitude_deg"], ap["longitude_deg"])]
print(f"  airports matched: {len(ap):,} of {len(codes):,}")
df = df[df["ADEP"].astype(str).isin(ap.index) & df["ADES"].astype(str).isin(ap.index)]


def to_local(ts, icao):
    tz = icao.astype(str).map(ap["tz"])
    out = pd.Series(pd.NaT, index=ts.index, dtype="datetime64[ns]")
    for name, idx in tz.groupby(tz).groups.items():
        out.loc[idx] = ts.loc[idx].dt.tz_localize("UTC").dt.tz_convert(name).dt.tz_localize(None)
    return out


print("Converting UTC -> local times ...")
dep_l = to_local(df["FILED OFF BLOCK TIME"], df["ADEP"])
arr_l = to_local(df["FILED ARRIVAL TIME"], df["ADES"])
utc = df["FILED OFF BLOCK TIME"]
df["ym"] = utc.dt.year * 100 + utc.dt.month          # sample month (UTC, = source file)
df["month"] = utc.dt.month
df["weekday"] = dep_l.dt.dayofweek                    # 0 = Monday, local
df["date"] = dep_l.dt.strftime("%Y-%m-%d")
df["dep_hour"] = dep_l.dt.hour
df["dep_raw"] = (dep_l.dt.hour * 60 + dep_l.dt.minute).astype(int)
df["dep_min"] = (((dep_l.dt.hour * 60 + dep_l.dt.minute) / 5).round() * 5).astype(int) % 1440
df["arr_min"] = (arr_l.dt.hour * 60 + arr_l.dt.minute).astype(int)
df["block_min"] = (df["FILED ARRIVAL TIME"] - utc).dt.total_seconds() / 60
df["late"] = (df["arr_delay_min"] > 15).astype(float)
df = df.drop(columns=["FILED OFF BLOCK TIME", "FILED ARRIVAL TIME"])

# ---------- 3. schedule (latest year of each sampled month) ----------
latest = df.groupby("month")["ym"].max()
cur = df[df["ym"] == df["month"].map(latest)]
# one service = departures of the same airline/route/weekday within 30 min of each other
# (filed off-block times drift a few minutes day to day; exact-minute slots split them below MIN_OPS)
_g = ["month", "weekday", "airline_icao", "ADEP", "ADES"]
cur = cur.sort_values(_g + ["dep_raw"]).copy()
_gap = cur.groupby(_g, observed=True)["dep_raw"].diff()
cur["_slot"] = (_gap.isna() | (_gap > 30)).cumsum()
cur["dep_min"] = (cur.groupby("_slot")["dep_raw"].transform("median") / 5).round().mul(5).astype(int) % 1440
keys = ["month", "weekday", "airline_icao", "ADEP", "ADES", "dep_min"]
sched = (cur.groupby(keys, observed=True)
         .agg(n_ops=("arr_delay_min", "size"), arr_min=("arr_min", "first"),
              block_min=("block_min", "median"), dist_nm=("dist_nm", "median"),
              late_share=("late", "mean"), avg_delay=("arr_delay_min", "mean"))
         .reset_index())
sched = sched[sched["n_ops"] >= MIN_OPS]
mode = (cur.groupby(keys + ["ac_type"], observed=True).size().rename("c").reset_index()
        .sort_values("c").drop_duplicates(keys, keep="last").drop(columns="c"))
for k in keys + ["ac_type"]:
    if str(mode[k].dtype) == "category":
        mode[k] = mode[k].astype(str)
for k in keys:
    if str(sched[k].dtype) == "category":
        sched[k] = sched[k].astype(str)
sched = sched.merge(mode, on=keys, how="left")
fuel = (cur.assign(ac_type=cur["ac_type"].astype(str)).drop_duplicates("ac_type")
        .set_index("ac_type")[["Fuel_Flow_Idle_kg_sec", "Engine_Count"]])
sched = sched.join(fuel, on="ac_type")

al = pd.read_csv(os.path.join(REF, "airlines.dat"), header=None, keep_default_na=False,
                 na_values=["\\N", "-", ""],
                 names=["id", "name", "alias", "iata", "icao", "callsign", "country", "active"])
al = al.dropna(subset=["icao"])
al["score"] = (al["active"] == "Y").astype(int) * 2 + al["iata"].notna().astype(int)
al = al.sort_values("score").drop_duplicates("icao", keep="last").set_index("icao")
sched["airline_name"] = sched["airline_icao"].map(al["name"]).fillna(sched["airline_icao"])
sched["airline_iata"] = sched["airline_icao"].map(al["iata"])

sched["origin"] = sched["ADEP"].map(ap["iata_code"])
sched["dest"] = sched["ADES"].map(ap["iata_code"])
sched = sched.dropna(subset=["origin", "dest"]).rename(columns={"ADEP": "origin_icao", "ADES": "dest_icao"})
hhmm = lambda m: (m // 60).astype(int).astype(str).str.zfill(2) + (m % 60).astype(int).astype(str).str.zfill(2)
sched["dep_hhmm"] = hhmm(sched["dep_min"])
sched["arr_hhmm"] = hhmm(sched["arr_min"])
sched = sched.sort_values(["origin", "dest", "month", "weekday", "dep_min"])
sched.to_csv(os.path.join(OUT, "eu_schedule.csv"), index=False)

# ---------- 4. flight history (track record) for scheduled services ----------
svc = sched[["airline_icao", "origin_icao", "dest_icao", "dep_min", "weekday"]].drop_duplicates()
h = df[["airline_icao", "ADEP", "ADES", "dep_min", "weekday", "date", "ym",
        "arr_delay_min", "dep_delay_min"]].copy()
for c in ["airline_icao", "ADEP", "ADES"]:
    h[c] = h[c].astype(str)
h = h.rename(columns={"ADEP": "origin_icao", "ADES": "dest_icao"}).merge(svc, on=list(svc.columns))
h.to_csv(os.path.join(OUT, "eu_flight_history.csv.gz"), index=False)

# ---------- 5. airports used ----------
used = pd.unique(pd.concat([sched["origin_icao"], sched["dest_icao"]]))
apo = (ap.loc[used].reset_index()
       .rename(columns={"ident": "icao", "iata_code": "iata", "municipality": "city",
                        "latitude_deg": "lat", "longitude_deg": "lon"}))
apo.to_csv(os.path.join(OUT, "eu_airports.csv"), index=False)

# ---------- 6. model base for training ----------
print("Writing model base ...")
df[["ym", "month", "weekday", "dep_hour", "dist_nm", "ADEP", "ADES", "airline_icao", "ac_type",
    "arr_delay_min"]].to_csv(os.path.join(DS, "eu_model_base.csv.gz"), index=False)

# ---------- summary ----------
print(f"\nservices (month x weekday rows): {len(sched):,}")
print(f"unique services: {len(svc):,} | airports: {len(apo):,} | airlines: {sched['airline_icao'].nunique()}")
print(f"history rows: {len(h):,} | model base rows: {len(df):,}")
print("timetable months used:", dict(latest))
print("airlines without IATA code (no logo):", sched.loc[sched['airline_iata'].isna(), 'airline_icao'].nunique())
print("\nCheck JFK -> LHR:")
chk = sched[(sched["origin"] == "JFK") & (sched["dest"] == "LHR") & (sched["weekday"] == 0)]
print(chk[["month", "airline_name", "dep_hhmm", "arr_hhmm", "ac_type", "n_ops", "late_share"]].to_string(index=False))
