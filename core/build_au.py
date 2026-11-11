"""Australia: BITRE domestic on-time performance (route x airline x month, data.gov.au, CC BY).
Auto-refresh: ensure_fresh() asks the data.gov.au API when the CSV was last modified and
re-downloads + rebuilds only when it changed (checked at most once per MAX_AGE_H).
Outputs: data/au_otp_raw.csv, data/au_otp_meta.json,
         data/au_routes.csv   route x airline x month (last 36 months)
         data/au_airports.csv per airport, last 12 months (flights/day, dep/arr on time, cancellations)
Notes: on time = within 15 min of schedule (same as BTS); no delay minutes are published.
       Only routes with >= 8,000 passengers/month and >= 2 competing airlines are reported."""
import json
import os
import time
import urllib.request

import pandas as pd

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(APP, "data")
RAW = os.path.join(DATA, "au_otp_raw.csv")
META = os.path.join(DATA, "au_otp_meta.json")
API = "https://data.gov.au/data/api/3/action/package_show?id=29128ebd-dbaa-4ff5-8b86-d9f30de56452"
MAX_AGE_H = 24

PORTS = {"Adelaide": "ADL", "Albury": "ABX", "Alice Springs": "ASP", "Armidale": "ARM", "Ayers Rock": "AYQ",
         "Ballina": "BNK", "Brisbane": "BNE", "Broome": "BME", "Bundaberg": "BDB", "Burnie": "BWT",
         "Cairns": "CNS", "Canberra": "CBR", "Coffs Harbour": "CFS", "Darwin": "DRW", "Devonport": "DPO",
         "Dubbo": "DBO", "Emerald": "EMD", "Geraldton": "GET", "Gladstone": "GLT", "Gold Coast": "OOL",
         "Hamilton Island": "HTI", "Hervey Bay": "HVB", "Hobart": "HBA", "Kalgoorlie": "KGI",
         "Karratha": "KTA", "Launceston": "LST", "Mackay": "MKY", "Melbourne": "MEL", "Mildura": "MQL",
         "Moranbah": "MOV", "Mount Isa": "ISA", "Newcastle": "NTL", "Newman": "ZNE", "Orange": "OAG",
         "Perth": "PER", "Port Hedland": "PHE", "Port Lincoln": "PLO", "Port Macquarie": "PQQ",
         "Proserpine": "PPP", "Rockhampton": "ROK", "Sunshine Coast": "MCY", "Sydney": "SYD",
         "Tamworth": "TMW", "Townsville": "TSV", "Wagga Wagga": "WGA"}
AIRLINES = {  # BITRE name -> (display name, IATA code of the seller on tickets)
    "Qantas": ("Qantas", "QF"), "QantasLink": ("QantasLink", "QF"), "Jetstar": ("Jetstar", "JQ"),
    "Virgin Australia": ("Virgin Australia", "VA"), "virgin Australia": ("Virgin Australia", "VA"),
    "Virgin Australia Regional Airlines": ("Virgin Australia Regional", "VA"),
    "Virgin Australia - ATR/F100 Operations": ("Virgin Australia Regional", "VA"),
    "Regional Express": ("Rex Airlines", "ZL"), "Rex Airlines": ("Rex Airlines", "ZL"),
    "Bonza": ("Bonza", "AB"), "Tigerair Australia": ("Tigerair Australia", "TT"),
    "Skytrans": ("Skytrans", "QN"), "Skytrans Australia": ("Skytrans", "QN"),
    "Hinterland": ("Hinterland Aviation", ""), "Skywest": ("Skywest", "XR"),
    "MacAir": ("MacAir", "CC"), "Macair": ("MacAir", "CC"), "Ozjet": ("Ozjet", "O7"),
    "SmartLynx Australia": ("SmartLynx Australia", ""), "All Airlines": ("All Airlines", "ALL"),
}


def _remote():
    with urllib.request.urlopen(API, timeout=20) as r:
        res = json.load(r)["result"]["resources"]
    csv = next(x for x in res if str(x.get("format")).upper() == "CSV")
    return csv["url"], csv.get("last_modified") or csv.get("created") or ""


def _meta():
    try:
        return json.load(open(META))
    except Exception:
        return {}


def build():
    d = pd.read_csv(RAW, encoding="latin-1")
    d = d[(d.Departing_Port != "All Ports") & (d.Arriving_Port != "All Ports")].copy()
    d["origin"], d["dest"] = d.Departing_Port.map(PORTS), d.Arriving_Port.map(PORTS)
    d = d.dropna(subset=["origin", "dest"])
    nm = d.Airline.map(lambda a: AIRLINES.get(a, (a, ""))[0])
    d["airline_name"], d["airline"] = nm, d.Airline.map(lambda a: AIRLINES.get(a, (a, ""))[1])
    d["ym"] = d.Year * 100 + d.Month_Num
    last = int(d.ym.max())
    keep = sorted(d.ym.unique())[-36:]
    num = ["Sectors_Scheduled", "Sectors_Flown", "Cancellations", "Departures_On_Time", "Arrivals_On_Time",
           "Departures_Delayed", "Arrivals_Delayed"]
    r = (d[d.ym.isin(keep)].groupby(["origin", "dest", "airline", "airline_name", "Year", "Month_Num", "ym"])[num]
           .sum().reset_index())
    r.to_csv(os.path.join(DATA, "au_routes.csv"), index=False)

    y12 = sorted(d.ym.unique())[-12:]
    a = d[d.ym.isin(y12) & (d.Airline == "All Airlines")]
    ap = a.groupby("origin")[num].sum()
    days = 365.0
    out = pd.DataFrame({
        "code": ap.index,
        "flights_day": (ap.Sectors_Flown / days).round(1).values,
        "dep_ontime": (ap.Departures_On_Time / ap.Sectors_Flown).round(4).values,
        "arr_ontime_in": (a.groupby("dest")[num].sum().reindex(ap.index).Arrivals_On_Time
                          / a.groupby("dest")[num].sum().reindex(ap.index).Sectors_Flown).round(4).values,
        "cancel_rate": (ap.Cancellations / ap.Sectors_Scheduled).round(4).values})
    out.to_csv(os.path.join(DATA, "au_airports.csv"), index=False)

    # same columns as data/monthly_eu.csv so the airport page can use it (no delay minutes in BITRE)
    al = d[d.Airline == "All Airlines"]
    dep = al.groupby(["origin", "Year", "Month_Num"])[["Sectors_Flown", "Departures_On_Time"]].sum()
    arr = al.groupby(["dest", "Year", "Month_Num"])[["Sectors_Flown", "Arrivals_On_Time"]].sum()
    dep.index.names = arr.index.names = ["airport", "Year", "Month"]
    mo = dep.join(arr, how="outer", lsuffix="_d", rsuffix="_a").reset_index()
    mo = pd.DataFrame({"airport": mo.airport, "Year": mo.Year, "Month": mo.Month,
                       "n_dep": mo.Sectors_Flown_d, "avg_dep_delay": float("nan"), "avg_dep_when_late": float("nan"),
                       "pct_dep_ontime": mo.Departures_On_Time / mo.Sectors_Flown_d,
                       "n_arr": mo.Sectors_Flown_a, "avg_arr_delay": float("nan"), "avg_arr_when_late": float("nan"),
                       "pct_arr_ontime": mo.Arrivals_On_Time / mo.Sectors_Flown_a, "co2_tonnes": float("nan")})
    mo = mo[mo.Year * 100 + mo.Month >= keep[0]]
    mo.to_csv(os.path.join(DATA, "monthly_au.csv"), index=False)
    return last, len(r), out


def ensure_fresh(force=False):
    """Download + rebuild when data.gov.au has a newer CSV. Never raises; keeps the local copy offline."""
    m = _meta()
    if not force and m.get("checked") and time.time() - m["checked"] < MAX_AGE_H * 3600 \
            and os.path.exists(os.path.join(DATA, "au_routes.csv")):
        return m
    try:
        url, mod = _remote()
        if force or mod != m.get("last_modified") or not os.path.exists(RAW):
            urllib.request.urlretrieve(url, RAW + ".tmp")
            os.replace(RAW + ".tmp", RAW)
            last, n, _ = build()
            m.update({"last_modified": mod, "latest_month": last, "rows": n})
            print(f"[au] updated: data.gov.au {mod}, latest month {last}, {n} route-airline-month rows")
            try:
                import subprocess, sys
                root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                r = subprocess.run([sys.executable, os.path.join("core", "build_home.py")], cwd=root,
                                   capture_output=True, text=True, timeout=600)
                print("[au] Explore airports rebuilt" if r.returncode == 0
                      else f"[au] build_home failed: {r.stderr[-300:]}")
            except Exception as e:
                print(f"[au] build_home skipped ({type(e).__name__}: {e})")
        m["checked"] = time.time()
        json.dump(m, open(META, "w"), indent=1)
    except Exception as e:
        print(f"[au] refresh skipped ({type(e).__name__}: {e}); using local copy")
    return m


if __name__ == "__main__":
    m = ensure_fresh(force=True)
    print(m)
    r = pd.read_csv(os.path.join(DATA, "au_routes.csv"))
    print("airlines (last 36 months):", r.groupby(["airline_name", "airline"]).Sectors_Flown.sum()
          .sort_values(ascending=False).to_dict())
    x = r[(r.origin == "SYD") & (r.dest == "MEL") & (r.ym == r.ym.max())]
    x = x.assign(arr_late=1 - x.Arrivals_On_Time / x.Sectors_Flown, cancel=x.Cancellations / x.Sectors_Scheduled)
    print("\nSYD-MEL latest month:\n", x[["airline_name", "Sectors_Flown", "arr_late", "cancel"]].round(3).to_string(index=False))
    print("\nTop airports:\n", pd.read_csv(os.path.join(DATA, "au_airports.csv"))
          .sort_values("flights_day", ascending=False).head(8).to_string(index=False))


# ---------------- forecast for one Australian domestic leg (used by core/ignav.py) ----------------
from functools import lru_cache as _lru


@_lru(maxsize=1)
def _tables():
    r = pd.read_csv(os.path.join(DATA, "au_routes.csv"))
    yms = sorted(r.ym.unique())
    return r, set(yms[-12:])


def is_au(code):
    return code in PORTS.values()


@_lru(maxsize=4096)
def forecast(o, d, airline, month):
    """Route x airline arrival-delay share from BITRE: same calendar month (last 3 years) blended
    with the last 12 months; falls back to all airlines on the route. Returns dict or None."""
    try:
        r, y12 = _tables()
    except Exception:
        return None
    route = r[(r.origin == o) & (r.dest == d)]
    if route.empty:
        return None

    def rates(x):
        f = x.Sectors_Flown.sum()
        return (None, 0, None) if f <= 0 else (1 - x.Arrivals_On_Time.sum() / f, f,
                                              x.Cancellations.sum() / max(1, x.Sectors_Scheduled.sum()))
    used = airline
    sel = route[route.airline == airline]
    if sel.empty or sel.Sectors_Flown.sum() <= 0:
        sel, used = route[route.airline == "ALL"], "ALL"
    p12, n12, c12 = rates(sel[sel.ym.isin(y12)])
    pm, nm, _ = rates(sel[sel.Month_Num == month])
    if p12 is None and pm is None:
        return None
    if p12 is None:
        p = pm
    elif pm is None:
        p = p12
    else:
        p = (nm * pm + 300 * p12) / (nm + 300)          # month evidence shrunk toward the last 12 months
    allr = r[(r.airline == "ALL") & r.ym.isin(y12)]
    nat = 1 - allr.Arrivals_On_Time.sum() / allr.Sectors_Flown.sum()
    return {"p_late": float(p), "national": float(nat), "cancel": float(c12 or 0),
            "n": int(n12 + nm), "airline_used": used}
