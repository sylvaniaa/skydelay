import json
import os
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CARRIERS = {
    "AA": "American Airlines", "DL": "Delta Air Lines", "UA": "United Airlines",
    "WN": "Southwest Airlines", "B6": "JetBlue", "AS": "Alaska Airlines",
    "NK": "Spirit Airlines", "F9": "Frontier Airlines", "G4": "Allegiant Air",
    "HA": "Hawaiian Airlines", "OO": "SkyWest Airlines", "YX": "Republic Airways",
    "MQ": "Envoy Air", "9E": "Endeavor Air", "OH": "PSA Airlines",
    "YV": "Mesa Airlines", "QX": "Horizon Air", "C5": "CommuteAir",
    "ZW": "Air Wisconsin", "G7": "GoJet Airlines", "EV": "ExpressJet",
}

# Representative delay (minutes) for each band, used for CO2-if-delayed.
# On time = 0; 15-60 and 60-120 = band midpoints; >120 assumed 150 (conservative).
BAND_MINUTES = [0.0, 37.5, 90.0, 150.0]
EMISSION_FACTOR = 3.16  # kg CO2 per kg jet fuel

# EUROCONTROL samples one month per quarter -> travel month uses the nearest sampled month
EU_MONTH_MAP = {1: 12, 2: 3, 3: 3, 4: 3, 5: 6, 6: 6, 7: 6, 8: 9, 9: 9, 10: 9, 11: 12, 12: 12}


def carrier_name(code):
    return CARRIERS.get(code, code)


@lru_cache(maxsize=1)
def _load():
    reg = joblib.load(os.path.join(DATA_DIR, "model_reg.joblib"))
    clf = joblib.load(os.path.join(DATA_DIR, "model_clf.joblib"))
    with open(os.path.join(DATA_DIR, "model_meta.json")) as fh:
        meta = json.load(fh)
    return reg, clf, meta


@lru_cache(maxsize=1)
def _load_bands():
    return joblib.load(os.path.join(DATA_DIR, "model_bands.joblib"))


@lru_cache(maxsize=1)
def _load_eu():
    clf = joblib.load(os.path.join(DATA_DIR, "model_bands_eu.joblib"))
    with open(os.path.join(DATA_DIR, "model_meta_eu.json")) as fh:
        meta = json.load(fh)
    return clf, meta


# ---------------- routes (used by the existing Check a flight page) ----------------
@lru_cache(maxsize=1)
def routes():
    return pd.read_csv(os.path.join(DATA_DIR, "routes.csv"))


def origins():
    r = routes()
    return list(r.groupby("Origin")["n"].sum().sort_values(ascending=False).index)


def destinations(origin):
    r = routes()
    r = r[r.Origin == origin]
    return list(r.groupby("Dest")["n"].sum().sort_values(ascending=False).index)


def airlines_for(origin, dest):
    r = routes()
    r = r[(r.Origin == origin) & (r.Dest == dest)].sort_values("n", ascending=False)
    return list(r.Reporting_Airline)


def route_distance(origin, dest):
    r = routes()
    r = r[(r.Origin == origin) & (r.Dest == dest)]
    return float(r.distance.median()) if not r.empty else None


def families():
    return _load()[2]["fam_list"]


RISK_MINUTES = (15, 30)   # expected delay = P(late) x typical delay if late. LOW < 15, MEDIUM 15-30, HIGH 30+ (Vani, 10 Nov 2026)


def risk_level(exp_minutes):
    """Risk label from expected delay in minutes (fixed thresholds, same meaning in every region)."""
    if exp_minutes < RISK_MINUTES[0]:
        return "Low"
    if exp_minutes < RISK_MINUTES[1]:
        return "Moderate"
    return "High"


# ---------------- aircraft types (EUROCONTROL uses ICAO type codes) ----------------
ICAO_FAMILY = {
    "A318": "A319", "A319": "A319", "A19N": "A319", "A320": "A320", "A20N": "A320",
    "A321": "A321", "A21N": "A321", "A332": "A330", "A333": "A330", "A338": "A330",
    "A339": "A330", "A359": "A350", "A35K": "A350", "A388": "A380",
    "B737": "737", "B738": "737", "B739": "737", "B37M": "737", "B38M": "737", "B39M": "737",
    "B752": "757", "B753": "757", "B762": "767", "B763": "767", "B764": "767",
    "B772": "777", "B773": "777", "B77L": "777", "B77W": "777", "B778": "777", "B779": "777",
    "B788": "787", "B789": "787", "B78X": "787", "B744": "747", "B748": "747", "B712": "717",
    "E170": "ERJ 170", "E175": "ERJ 170", "E75L": "ERJ 170", "E75S": "ERJ 170",
    "E190": "ERJ 190", "E195": "ERJ 190", "E290": "ERJ 190", "E295": "ERJ 190",
    "CRJ2": "CL", "CRJ7": "CL", "CRJ9": "CL", "CRJX": "CL", "BCS1": "BD", "BCS3": "BD",
}


def icao_family(ac_type):
    t = str(ac_type).strip().upper()
    return ICAO_FAMILY.get(t, t)


# ---------------- schedule (find your flight) ----------------
@lru_cache(maxsize=1)
def us_schedule():
    s = pd.read_csv(os.path.join(DATA_DIR, "schedule.csv"))
    s["region"] = "US"
    return s


def _hhmm_text(x):
    x = int(x)
    return f"{x // 100:02d}:{x % 100:02d}"


@lru_cache(maxsize=1)
def eu_schedule():
    """EUROCONTROL services in the same columns as the US schedule.
    No flight numbers (flight_number = 0); airline = IATA code if known, else ICAO code."""
    p = os.path.join(DATA_DIR, "eu_schedule.csv")
    if not os.path.exists(p):
        return pd.DataFrame()
    s = pd.read_csv(p, keep_default_na=False, na_values=[""])
    s["airline"] = s.airline_iata.fillna(s.airline_icao)
    s["flight_number"] = 0
    s["dep_hhmm"] = (s.dep_min // 60) * 100 + s.dep_min % 60
    s["arr_hhmm"] = (s.arr_min // 60) * 100 + s.arr_min % 60
    s["dep_time"] = s.dep_hhmm.map(_hhmm_text)
    s["arr_time"] = s.arr_hhmm.map(_hhmm_text)
    s["block_min"] = s.block_min.round().astype(int)
    s["distance"] = s.dist_nm * 1.15078          # statute miles, like BTS
    s["family"] = s.ac_type.map(icao_family)
    s["n_flights"] = s.n_ops
    s["region"] = "EU"
    return s


@lru_cache(maxsize=1)
def schedule():
    return pd.concat([us_schedule(), eu_schedule()], ignore_index=True, sort=False)


def schedule_origins():
    s = schedule()
    return list(s.groupby("origin")["n_flights"].sum().sort_values(ascending=False).index)


def schedule_destinations(origin):
    s = schedule()
    s = s[s.origin == origin]
    return list(s.groupby("dest")["n_flights"].sum().sort_values(ascending=False).index)


def flights_on(origin, dest, flight_date):
    """Regular scheduled flights on a route that operate on this date's weekday.
    US: BTS timetable weekday mask. Europe: nearest sampled month + weekday."""
    s = schedule()
    s = s[s.origin == origin]
    if dest is not None:
        s = s[s.dest == dest]
    us = s[s.region == "US"]
    bit = 1 << (flight_date.isoweekday() - 1)   # Mon=1 ... Sun=64
    us = us[(us.dow_mask.astype(int) & bit) > 0]
    eu_all = s[s.region == "EU"]
    eu = eu_all[(eu_all.month == EU_MONTH_MAP[flight_date.month]) & (eu_all.weekday == flight_date.weekday())]
    if eu.empty and dest is not None and len(eu_all):
        # route not in the mapped sample month: use the nearest sample month that has it
        mo = flight_date.month
        for m in sorted(eu_all.month.dropna().unique(), key=lambda m: min(abs(m - mo), 12 - abs(m - mo))):
            x = eu_all[eu_all.month == m]
            y = x[x.weekday == flight_date.weekday()]
            eu = y if len(y) else x.drop_duplicates(["airline", "dep_hhmm"])
            if len(eu):
                break
    out = pd.concat([us, eu]).copy()
    if "airline_name" not in out.columns:
        out["airline_name"] = None
    out["airline_name"] = out.airline_name.where(out.region == "EU", out.airline.map(carrier_name))
    return out.sort_values("dep_hhmm").reset_index(drop=True)


# ---------------- model features ----------------
def _features(meta, origin, dest, airline, flight_date, hour, fams, distance):
    te = meta["te_tables"]
    gm = meta["global_mean"]
    air_list, fam_list = meta["air_list"], meta["fam_list"]
    airline_idx = air_list.index(airline) if airline in air_list else len(air_list)
    rows = []
    for fam in fams:
        fam_idx = fam_list.index(fam) if fam in fam_list else len(fam_list)
        rows.append({
            "Month": flight_date.month,
            "DayOfWeek": flight_date.isoweekday(),   # BTS: 1 = Monday ... 7 = Sunday
            "sched_hour": int(hour),
            "Distance": distance,
            "airline_idx": airline_idx,
            "family_idx": fam_idx,
            "origin_te": te["origin_te"].get(origin, gm),
            "dest_te": te["dest_te"].get(dest, gm),
            "route_te": te["route_te"].get(origin + "-" + dest, gm),
            "airline_te": te["airline_te"].get(airline, gm),
        })
    return pd.DataFrame(rows)[meta["features"]]


def predict(origin, dest, airline, flight_date, hour, family=None):
    """Delay risk for a scheduled flight. Uses only information known at scheduling time."""
    reg, clf, meta = _load()
    distance = route_distance(origin, dest)
    if distance is None:
        return None
    # no aircraft chosen -> average over the 5 most common aircraft families
    fams = [family] if family else meta["fam_list"][:5]
    X = _features(meta, origin, dest, airline, flight_date, hour, fams, distance)

    minutes = float(reg.predict(X).mean())
    prob = float(clf.predict_proba(X)[:, 1].mean())
    base = meta["metrics"]["delay15_base_rate_test"]
    ratio = prob / base
    return {
        "prob_delay15": prob,
        "expected_minutes": minutes,
        "base_rate": base,
        "ratio": ratio,
        "level": risk_level(minutes),
        "distance": distance,
    }


def predict_flight(origin, dest, airline, flight_date, dep_hhmm, family=None, distance=None):
    """Delay-band probabilities, expected minutes and CO2-if-delayed for one scheduled flight."""
    reg, _, meta = _load()
    bands = _load_bands()
    if distance is None:
        distance = route_distance(origin, dest)
    if distance is None:
        return None
    fams = [family] if family else meta["fam_list"][:5]
    hour = int(dep_hhmm) // 100
    X = _features(meta, origin, dest, airline, flight_date, hour, fams, float(distance))

    probs = [float(p) for p in bands.predict_proba(X).mean(axis=0)]
    prior = meta["bands"]["train_prior"]
    p_late = 1.0 - probs[0]
    base_late = 1.0 - prior[0]
    ratio = p_late / base_late
    co2_by_band = [delay_co2_kg(family, m) for m in band_minutes()]
    return {
        "labels": meta["bands"]["labels"],
        "probs": probs,
        "prior": prior,
        "p_late": p_late,
        "base_late": base_late,
        "ratio": ratio,
        "level": risk_level(p_late * typical_late_minutes(probs, "US")),
        "expected_minutes": float(reg.predict(X).mean()),
        "co2_by_band": co2_by_band,
        "expected_co2_kg": float(sum(p * c for p, c in zip(probs, co2_by_band))),
        "fuel_rate_kg_hr": fuel_rate(family),
        "distance": float(distance),
        "region": "US",
    }


def predict_flight_eu(r, flight_date):
    """Delay-band probabilities for one EUROCONTROL service (row of eu_schedule()).
    Delay = actual arrival vs FILED arrival (flight plan)."""
    clf, meta = _load_eu()
    te, gm = meta["te_tables"], meta["global_mean"]
    al, tl = meta["air_list"], meta["type_list"]
    row = {
        "month": EU_MONTH_MAP[flight_date.month],
        "weekday": flight_date.weekday(),              # 0 = Monday, like training
        "dep_hour": int(r.dep_hhmm) // 100,
        "dist_nm": float(r.dist_nm),
        "airline_idx": al.index(r.airline_icao) if r.airline_icao in al else len(al),
        "type_idx": tl.index(r.ac_type) if r.ac_type in tl else len(tl),
        "origin_te": te["origin_te"].get(r.origin_icao, gm),
        "dest_te": te["dest_te"].get(r.dest_icao, gm),
        "route_te": te["route_te"].get(r.origin_icao + "-" + r.dest_icao, gm),
        "airline_te": te["airline_te"].get(r.airline_icao, gm),
    }
    X = pd.DataFrame([row])[meta["features"]]
    probs = [float(p) for p in clf.predict_proba(X)[0]]
    prior = meta["bands"]["train_prior"]
    p_late, base_late = 1.0 - probs[0], 1.0 - prior[0]
    ratio = p_late / base_late
    return {"labels": meta["bands"]["labels"], "probs": probs, "prior": prior,
            "p_late": p_late, "base_late": base_late, "ratio": ratio,
            "level": risk_level(p_late * typical_late_minutes(probs, "EU")), "distance": float(r.distance), "region": "EU"}


# ---------------- CO2 ----------------
@lru_cache(maxsize=1)
def _fuel_by_family():
    df = pd.read_csv(os.path.join(DATA_DIR, "aircraft_fuel_rates_lookup.csv"))
    df["family"] = df["MODEL"].astype(str).str.strip().str.split("-").str[0].str.strip()
    return df.groupby("family")["fuel_rate_kg_hr"].median().to_dict()


def fuel_rate(family=None):
    table = _fuel_by_family()
    if family is not None and family in table:
        return float(table[family])
    if family is None:
        vals = [table[f] for f in _load()[2]["fam_list"][:5] if f in table]
        if vals:
            return float(sum(vals) / len(vals))
    return float(pd.Series(list(table.values())).median())


def delay_co2_kg(family, minutes):
    return fuel_rate(family) * (minutes / 60.0) * EMISSION_FACTOR


# ---------------- per-passenger CO2 range for a delay ----------------
# Typical seats per aircraft family (approximate two-class layouts).
SEATS = {"737": 170, "A320": 160, "A321": 190, "A319": 128, "757": 180, "717": 110,
         "767": 211, "777": 300, "787": 250, "A330": 250, "A350": 300, "747": 370, "A380": 500,
         "CL": 70, "ERJ 170": 76, "ERJ 190": 100, "EMB": 50, "BD": 130}
WIDEBODY = {"767", "777", "787", "A330", "A350", "747", "A380"}
REGIONAL = {"CL", "ERJ 170", "ERJ 190", "EMB"}
# Approximate APU fuel flow (kg/h) while parked at the gate with engines off.
APU_KG_HR = {"wide": 230.0, "narrow": 100.0, "regional": 60.0}
CAR_KG_PER_KM = 0.25   # average passenger car, ~400 g CO2 per mile (US EPA)


def seats(family):
    return SEATS.get(family, 150)


def apu_rate(family):
    if family in WIDEBODY:
        return APU_KG_HR["wide"]
    if family in REGIONAL:
        return APU_KG_HR["regional"]
    return APU_KG_HR["narrow"]


def delay_co2_range_pp(family, minutes):
    """(low, high) kg CO2 per passenger for a delay of `minutes`.
    low = at the gate on APU only; high = engines idling the whole delay (ICAO idle fuel flow)."""
    n = seats(family)
    high = delay_co2_kg(family, minutes) / n
    low = apu_rate(family) * (minutes / 60.0) * EMISSION_FACTOR / n
    return low, high


def delay_co2_range_pp_eu(ac_type, fuel_kg_s, engines, minutes):
    """Europe version: idle fuel flow from the EUROCONTROL-EEDB mapping (kg/s per engine x engines)."""
    fam = icao_family(ac_type)
    n = seats(fam)
    try:
        rate = float(fuel_kg_s) * 3600.0 * int(engines)
        if not rate > 0:
            raise ValueError
    except (TypeError, ValueError):
        rate = fuel_rate(fam)
    high = rate * (minutes / 60.0) * EMISSION_FACTOR / n
    low = apu_rate(fam) * (minutes / 60.0) * EMISSION_FACTOR / n
    return low, high


# ---------------- whole-flight CO2 ----------------
# US BTS gives aircraft families; map each to a representative ICAO type in the EEA table.
US_REP = {"737": "B738", "A320": "A320", "A321": "A321", "A319": "A319", "757": "B752", "717": "B712",
          "767": "B763", "777": "B77W", "787": "B789", "A330": "A333", "A350": "A359", "CL": "CRJ9",
          "ERJ 170": "E75L", "ERJ 190": "E190", "EMB": "E145", "BD": "BCS3"}


@lru_cache(maxsize=1)
def _trip_fuel():
    p = os.path.join(DATA_DIR, "trip_fuel.csv")
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


def trip_co2(ac_type, distance_mi):
    """Whole-flight fuel and CO2. EMEP/EEA Guidebook 2023, 1.A.3.a Annex 1 Master emissions calculator
    (EUROCONTROL): climb-cruise-descent fuel at the route distance (linear interpolation between
    standard stage lengths) + landing/take-off cycle. Per seat, cargo not separated."""
    t = _trip_fuel()
    if t.empty or not ac_type or not distance_mi:
        return None
    g = t[t.ac_type == ac_type].sort_values("ades_nm")
    if g.empty:
        return None
    nm = float(distance_mi) / 1.15078
    x, y = g.ades_nm.values.astype(float), g.ccd_fuel_kg.values
    ccd_kg = float(np.interp(nm, x, y)) if nm >= x[0] else float(y[0] * nm / x[0])
    lto_kg = float(g.lto_fuel_kg.iloc[0]) if pd.notna(g.lto_fuel_kg.iloc[0]) else 0.0
    fuel = ccd_kg + lto_kg
    n = seats(icao_family(ac_type))
    km = nm * 1.852
    return {"fuel_kg": fuel, "co2_kg": fuel * EMISSION_FACTOR, "co2_pp": fuel * EMISSION_FACTOR / n,
            "seats": n, "km": km, "fuel_per_km": fuel / km}


def band_minutes():
    """Average delay (min) inside each band, from BTS 2023-2024; falls back to midpoints."""
    return _load()[2]["bands"].get("band_mean_min", BAND_MINUTES)


def typical_late_minutes(probs, region="US"):
    """Median delay (min) if this flight is more than 15 min late: mixes the real delay
    distribution inside each band by the model's band probabilities.
    US: BTS 2023-2024. EU: EUROCONTROL 2023 (vs filed arrival)."""
    p_late = sum(probs[1:])
    if p_late <= 0:
        return 30.0
    if region == "EU":
        bq = _load_eu()[1]["bands"]["band_quantiles"]
        qs = [bq["1"], bq["2"], bq["3"]]
    else:
        qs = _load()[2]["bands"]["band_quantiles"]
    grid = np.arange(16, 721)
    cdf = sum((p / p_late) * np.searchsorted(np.array(q), grid, side="right") / len(q)
              for p, q in zip(probs[1:], qs))
    return float(grid[np.argmax(cdf >= 0.5)])


def predict_batch(df, flight_date):
    """Same results as predict_flight / predict_flight_eu for every schedule row in df, but with ONE model call
    per region. Tree ensembles cost almost the same for 1 row or 1,000, so per-flight calls were the bottleneck.
    Returns a list aligned with df rows (None where a row can't be predicted), or None if anything fails."""
    try:
        rows = list(df.itertuples(index=False))
        out = [None] * len(rows)
        us = [i for i, r in enumerate(rows) if getattr(r, "region", "US") != "EU"]
        eu = [i for i, r in enumerate(rows) if getattr(r, "region", "US") == "EU"]
        if us:
            reg, _, meta = _load()
            bands = _load_bands()
            Xs, spans, n = [], [], 0
            for i in us:
                r = rows[i]
                fam = r.family if isinstance(getattr(r, "family", None), str) else None
                dist = getattr(r, "distance", None)
                dist = float(dist) if dist is not None and dist == dist else route_distance(r.origin, r.dest)
                if dist is None:
                    continue
                fams = [fam] if fam else meta["fam_list"][:5]
                X = _features(meta, r.origin, r.dest, r.airline, flight_date, int(r.dep_hhmm) // 100, fams, float(dist))
                Xs.append(X)
                spans.append((i, n, n + len(X), fam, float(dist)))
                n += len(X)
            if Xs:
                XA = pd.concat(Xs, ignore_index=True)
                P, M = bands.predict_proba(XA), reg.predict(XA)
                prior = meta["bands"]["train_prior"]
                for i, a, b, fam, dist in spans:
                    probs = [float(x) for x in P[a:b].mean(axis=0)]
                    p_late, base_late = 1.0 - probs[0], 1.0 - prior[0]
                    co2_by_band = [delay_co2_kg(fam, m) for m in band_minutes()]
                    out[i] = {"labels": meta["bands"]["labels"], "probs": probs, "prior": prior, "p_late": p_late,
                              "base_late": base_late, "ratio": p_late / base_late,
                              "level": risk_level(p_late * typical_late_minutes(probs, "US")),
                              "expected_minutes": float(M[a:b].mean()), "co2_by_band": co2_by_band,
                              "expected_co2_kg": float(sum(x * c for x, c in zip(probs, co2_by_band))),
                              "fuel_rate_kg_hr": fuel_rate(fam), "distance": dist, "region": "US"}
        if eu:
            clf, meta = _load_eu()
            te, gm = meta["te_tables"], meta["global_mean"]
            al, tl = meta["air_list"], meta["type_list"]
            recs = []
            for i in eu:
                r = rows[i]
                recs.append({"month": EU_MONTH_MAP[flight_date.month], "weekday": flight_date.weekday(),
                             "dep_hour": int(r.dep_hhmm) // 100, "dist_nm": float(r.dist_nm),
                             "airline_idx": al.index(r.airline_icao) if r.airline_icao in al else len(al),
                             "type_idx": tl.index(r.ac_type) if r.ac_type in tl else len(tl),
                             "origin_te": te["origin_te"].get(r.origin_icao, gm), "dest_te": te["dest_te"].get(r.dest_icao, gm),
                             "route_te": te["route_te"].get(r.origin_icao + "-" + r.dest_icao, gm),
                             "airline_te": te["airline_te"].get(r.airline_icao, gm)})
            P = clf.predict_proba(pd.DataFrame(recs)[meta["features"]])
            prior = meta["bands"]["train_prior"]
            for k, i in enumerate(eu):
                probs = [float(x) for x in P[k]]
                p_late, base_late = 1.0 - probs[0], 1.0 - prior[0]
                out[i] = {"labels": meta["bands"]["labels"], "probs": probs, "prior": prior, "p_late": p_late,
                          "base_late": base_late, "ratio": p_late / base_late,
                          "level": risk_level(p_late * typical_late_minutes(probs, "EU")),
                          "distance": float(rows[i].distance), "region": "EU"}
        return out
    except Exception as e:
        print(f"[predict_batch] fell back to per-flight: {type(e).__name__} {e}")
        return None
