"""Build data/home_airports.csv for the homepage map + airport panel.
US: newest BTS months in dataset/bts_recent (departures, arrivals, cancellations, traffic).
Europe: data/monthly_eu.csv (EUROCONTROL sample months).
India: data/india_routes.csv (DGCA passenger traffic per city; no airport-level delays).
busy_level 0-3 colours the map dots (US/EU by flights per day, India by passenger rank)."""
import calendar
import glob
import os

import airportsdata
import pandas as pd
import pycountry

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
IATA = airportsdata.load("IATA")
ICAO = airportsdata.load("ICAO")
INDIA_CITY = {"Delhi": "DEL", "Mumbai": "BOM", "Bengaluru": "BLR", "Bangalore": "BLR", "Kolkata": "CCU",
              "Chennai": "MAA", "Hyderabad": "HYD", "Goa": "GOI", "Kochi": "COK", "Cochin": "COK",
              "Pune": "PNQ", "Ahmedabad": "AMD", "Jaipur": "JAI", "Lucknow": "LKO", "Guwahati": "GAU",
              "Srinagar": "SXR", "Patna": "PAT", "Bhubaneswar": "BBI", "Thiruvananthapuram": "TRV",
              "Trivandrum": "TRV", "Chandigarh": "IXC", "Varanasi": "VNS", "Indore": "IDR", "Nagpur": "NAG",
              "Bagdogra": "IXB", "Coimbatore": "CJB", "Mangalore": "IXE", "Mangaluru": "IXE",
              "Visakhapatnam": "VTZ", "Ranchi": "IXR", "Raipur": "RPR", "Amritsar": "ATQ", "Port Blair": "IXZ",
              "Leh": "IXL", "Madurai": "IXM", "Tiruchirapalli": "TRZ", "Dehradun": "DED", "Udaipur": "UDR",
              "Vadodara": "BDQ", "Surat": "STV", "Kozhikode": "CCJ", "Calicut": "CCJ", "Imphal": "IMF",
              "Agartala": "IXA", "Jammu": "IXJ", "Dibrugarh": "DIB", "Silchar": "IXS", "Vijayawada": "VGA",
              "Tirupati": "TIR", "Rajkot": "RAJ", "Bhopal": "BHO", "Aurangabad": "IXU", "Gorakhpur": "GOP"}


def clean(n):
    return n.replace(" International Airport", " Intl.").replace(" International", " Intl.").replace(" Airport", "")


def country(cc):
    c = pycountry.countries.get(alpha_2=cc)
    return (getattr(c, "common_name", None) or c.name) if c else cc


def level(per_day):
    return 3 if per_day >= 600 else 2 if per_day >= 300 else 1 if per_day >= 100 else 0


rows = []

# ---------------- US: newest BTS months ----------------
files = sorted(glob.glob(os.path.join(DATASET, "bts_recent", "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_*.csv")))
cols = ["FlightDate", "Origin", "Dest", "DepDelay", "ArrDelay", "Cancelled", "Diverted"]
df = pd.concat([pd.read_csv(f, usecols=cols, low_memory=False) for f in files], ignore_index=True)
ndays = df.FlightDate.nunique()
d0, d1 = pd.to_datetime(df.FlightDate.min()), pd.to_datetime(df.FlightDate.max())
us_period = (d0.strftime("%b") + "–" + d1.strftime("%b %Y")) if d0.month != d1.month else d1.strftime("%b %Y")
canc = df.Cancelled.fillna(0)
div = df.Diverted.fillna(0)
dep = df.assign(ot=((df.DepDelay <= 15) & (canc == 0)).astype(int), cc=canc).groupby("Origin").agg(
    n=("FlightDate", "size"), dep_delay=("DepDelay", "mean"), dep_ontime=("ot", "mean"), dep_cancel=("cc", "mean"))
arr = df.assign(ot=((df.ArrDelay <= 15) & (canc == 0) & (div == 0)).astype(int)).groupby("Dest").agg(
    arr_delay=("ArrDelay", "mean"), arr_ontime=("ot", "mean"))
us = dep.join(arr, how="left")
for code, r in us.iterrows():
    a = IATA.get(code)
    per_day = r.n / ndays
    if not a or per_day < 5:
        continue
    rows.append({"region": "US", "code": code, "page": "airport:" + code, "name": clean(a["name"]),
                 "city": a["city"], "country": country(a["country"]), "lat": a["lat"], "lon": a["lon"],
                 "sort": per_day, "busy_level": level(per_day), "busy_txt": f"{per_day:.0f}/day",
                 "dep_delay": r.dep_delay, "dep_ontime": r.dep_ontime, "dep_cancel": r.dep_cancel,
                 "arr_delay": r.arr_delay, "arr_ontime": r.arr_ontime, "period": us_period + " · BTS"})

# ---------------- Europe: EUROCONTROL sample months ----------------
eu = pd.read_csv(os.path.join(DATA, "monthly_eu.csv"))
eu["days"] = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(eu.Year, eu.Month)]
for c in ("avg_dep_delay", "pct_dep_ontime"):
    eu[c + "_w"] = eu[c] * eu.n_dep
for c in ("avg_arr_delay", "pct_arr_ontime"):
    eu[c + "_w"] = eu[c] * eu.n_arr
g = eu.groupby("airport").sum(numeric_only=True)
for code, r in g.iterrows():
    a = ICAO.get(code)
    per_day = r.n_dep / r.days if r.days else 0
    if not a or per_day < 20:
        continue
    rows.append({"region": "EU", "code": a.get("iata") or code, "page": "airport:" + code, "name": clean(a["name"]),
                 "city": a["city"], "country": country(a["country"]), "lat": a["lat"], "lon": a["lon"],
                 "sort": per_day, "busy_level": level(per_day), "busy_txt": f"{per_day:.0f}/day",
                 "dep_delay": r.avg_dep_delay_w / r.n_dep, "dep_ontime": r.pct_dep_ontime_w / r.n_dep, "dep_cancel": None,
                 "arr_delay": (r.avg_arr_delay_w / r.n_arr) if r.n_arr else None,
                 "arr_ontime": (r.pct_arr_ontime_w / r.n_arr) if r.n_arr else None,
                 "period": "2023–24 sample months · EUROCONTROL"})

# ---------------- India: DGCA passenger traffic per city ----------------
ir = pd.read_csv(os.path.join(DATA, "india_routes.csv"))
pax = pd.concat([ir[["city1", "pax"]].rename(columns={"city1": "city"}),
                 ir[["city2", "pax"]].rename(columns={"city2": "city"})]).groupby("city").pax.sum()
im = pd.read_csv(os.path.join(DATA, "india_monthly.csv")).drop_duplicates(["Airline", "Year", "Month"])
iym = im.Year * 12 + im.Month
rec = im[iym > iym.max() - 12]
otp_nat = (rec.otp_pct * rec.departures).sum() / rec.departures.sum() / 100
lng = pd.concat([ir[["city1", "pax", "mult"]].rename(columns={"city1": "city"}),
                 ir[["city2", "pax", "mult"]].rename(columns={"city2": "city"})])
cm = lng.assign(w=lng.pax * lng.mult).groupby("city").agg(w=("w", "sum"), p=("pax", "sum"))
city_ot = {c: max(0.0, min(1.0, 1 - (1 - otp_nat) * m)) for c, m in (cm.w / cm.p).items()}
print("India national on-time (last 12 months, DGCA): %.1f%%" % (100 * otp_nat))
india_codes = {c: a for c, a in IATA.items() if a["country"] == "IN"}
missing = []
ind = []
for city_name, p in pax.items():
    code = INDIA_CITY.get(city_name)
    if not code:
        hits = [c for c, a in india_codes.items() if a["city"].lower() == str(city_name).lower()]
        code = sorted(hits, key=lambda c: "International" not in india_codes[c]["name"])[0] if hits else None
    a = IATA.get(code) if code else None
    if not a:
        missing.append(city_name)
        continue
    ind.append({"region": "IN", "code": code, "page": "city:" + str(city_name), "name": clean(a["name"]),
                "city": str(city_name), "country": "India", "lat": a["lat"], "lon": a["lon"], "sort": p / 1e5,
                "busy_level": 0, "busy_txt": f"{p / 1e6:.1f}M pax", "dep_delay": None, "dep_ontime": city_ot.get(city_name),
                "dep_cancel": None, "arr_delay": None, "arr_ontime": None, "period": "DGCA passenger traffic"})
ind = pd.DataFrame(ind).sort_values("sort", ascending=False).drop_duplicates("code")
q = ind["sort"].rank(pct=True)
ind["busy_level"] = [3 if v > .9 else 2 if v > .7 else 1 if v > .4 else 0 for v in q]

# ---------------- Australia: BITRE route x airline on-time (reported routes only) ----------------
au = pd.read_csv(os.path.join(DATA, "au_routes.csv"))
au = au[au.airline == "ALL"]
y12 = sorted(au.ym.unique())[-12:]
au = au[au.ym.isin(y12)]
first, last = min(y12), max(y12)
au_period = f"{calendar.month_abbr[first % 100]} {first // 100}–{calendar.month_abbr[last % 100]} {last // 100} · BITRE"
dep_g = au.groupby("origin")[["Sectors_Scheduled", "Sectors_Flown", "Cancellations", "Departures_On_Time"]].sum()
arr_g = au.groupby("dest")[["Sectors_Flown", "Arrivals_On_Time"]].sum()
aus = []
for code, r in dep_g.iterrows():
    a = IATA.get(code)
    if not a or not r.Sectors_Flown:
        continue
    per_day = r.Sectors_Flown / 365.0
    ar = arr_g.loc[code] if code in arr_g.index else None
    aus.append({"region": "AU", "code": code, "page": "airport:" + code, "name": clean(a["name"]),
                "city": a["city"], "country": "Australia", "lat": a["lat"], "lon": a["lon"],
                "sort": per_day, "busy_level": 0, "busy_txt": f"{per_day:.0f}/day",
                "dep_delay": None, "dep_ontime": r.Departures_On_Time / r.Sectors_Flown,
                "dep_cancel": r.Cancellations / max(1, r.Sectors_Scheduled), "arr_delay": None,
                "arr_ontime": (ar.Arrivals_On_Time / ar.Sectors_Flown) if ar is not None and ar.Sectors_Flown else None,
                "period": au_period})
aus = pd.DataFrame(aus)
qa = aus["sort"].rank(pct=True)
aus["busy_level"] = [3 if v > .9 else 2 if v > .7 else 1 if v > .4 else 0 for v in qa]

out = pd.concat([pd.DataFrame(rows), ind, aus], ignore_index=True)

def _t100_per_day():
    """US airports: scheduled passenger departures/day, domestic + international, all carriers (BTS T-100 Segment), latest 12 months."""
    import glob, zipfile
    fs = sorted(glob.glob(os.path.join(DATA, "raw", "t100", "*.zip")))
    if not fs:
        return {}
    fr = []
    for f in fs:
        z = zipfile.ZipFile(f)
        fr.append(pd.read_csv(z.open(z.namelist()[0]), usecols=["DEPARTURES_PERFORMED", "ORIGIN", "YEAR", "MONTH", "CLASS"]))
    t = pd.concat(fr)
    t = t[t.CLASS == "F"]
    ym = sorted(set(zip(t.YEAR, t.MONTH)))[-12:]
    keep = set(ym)
    t = t[[k in keep for k in zip(t.YEAR, t.MONTH)]]
    d0 = pd.Timestamp(year=int(ym[0][0]), month=int(ym[0][1]), day=1)
    d1 = pd.Timestamp(year=int(ym[-1][0]), month=int(ym[-1][1]), day=1) + pd.offsets.MonthEnd(0)
    days = (d1 - d0).days + 1
    print("[t100] %d-%02d to %d-%02d, %d days" % (ym[0][0], ym[0][1], ym[-1][0], ym[-1][1], days))
    return (t.groupby("ORIGIN").DEPARTURES_PERFORMED.sum() / days).to_dict()


def _au_intl_per_day():
    """AU airports: international departures/day (BITRE International airline activity, Table 4 outbound aircraft movements), latest 12 months."""
    p = os.path.join(DATA, "raw", "bitre_intl", "au_intl_departures.csv")
    if not os.path.exists(p):
        return {}
    t = pd.read_csv(p)
    ms = sorted(t.month.unique())[-12:]
    t = t[t.month.isin(ms)]
    days = sum(pd.Period(m, "M").days_in_month for m in ms)
    print("[au intl] %s to %s, %d days" % (ms[0], ms[-1], days))
    return (t.groupby("iata").intl_departures.sum() / days).to_dict()


T100 = _t100_per_day()
if T100:
    mu = (out.region == "US") & out.code.isin(list(T100))
    out.loc[mu, "sort"] = out.loc[mu, "code"].map(T100)
    out.loc[mu, "busy_level"] = out.loc[mu, "sort"].map(level)
    out.loc[mu, "busy_txt"] = out.loc[mu, "sort"].map(lambda v: f"{v:.0f}/day")
    print("[t100] US airports updated:", int(mu.sum()))

AUI = _au_intl_per_day()
if AUI:
    ma = (out.region == "AU") & out.code.isin(list(AUI))
    out.loc[ma, "sort"] = out.loc[ma, "sort"] + out.loc[ma, "code"].map(AUI)
    ra = out.region == "AU"
    qa = out.loc[ra, "sort"].rank(pct=True)
    out.loc[ra, "busy_level"] = [3 if v > .9 else 2 if v > .7 else 1 if v > .4 else 0 for v in qa]
    out.loc[ra, "busy_txt"] = out.loc[ra, "sort"].map(lambda v: f"{v:.0f}/day")
    print("[au intl] AU airports updated:", int(ma.sum()))

out.to_csv(os.path.join(DATA, "home_airports.csv"), index=False)
print("home_airports.csv: %d airports" % len(out))
for reg in ("US", "EU", "IN", "AU"):
    s = out[out.region == reg].sort_values("sort", ascending=False)
    print("\n%s: %d airports | busy levels %s" % (reg, len(s), s.busy_level.value_counts().sort_index().to_dict()))
    print(s[["code", "name", "city", "busy_txt", "dep_delay", "dep_ontime"]].head(5).to_string(index=False))
if missing:
    print("\nIndia cities without an airport match (%d): %s" % (len(missing), ", ".join(map(str, missing[:25]))))
