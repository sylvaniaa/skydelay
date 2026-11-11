"""Real sold itineraries from the Ignav fare API (cached per route and date), with SkyDelay's delay
forecast for each leg and the chance of missing each connection."""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from functools import lru_cache

from core import predict as pr
from core.connections import p_late_over

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "data", "ignav_cache")
MCT_DOM, MCT_INTL = 45, 90


MAX_AGE_DAYS = 30   # refresh cached schedules after a month
REUSE_DAYS = 28     # reuse a cached search from the same weekday up to 4 weeks away


def _load(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def fetch(origin, dest, day, tries=3):
    """Returns (data, shift_days). Uses the cache for the same date, else the same weekday
    within REUSE_DAYS (shifting dates), else calls the API once."""
    os.makedirs(CACHE, exist_ok=True)
    now = time.time()

    def p_of(dd):
        return os.path.join(CACHE, f"{origin}_{dest}_{dd.isoformat()}.json")

    def fresh(p):
        return os.path.exists(p) and now - os.path.getmtime(p) < MAX_AGE_DAYS * 86400

    path = p_of(day)
    if fresh(path) and _load(path):
        return _load(path), 0
    for k in range(7, REUSE_DAYS + 1, 7):
        for other in (day - timedelta(days=k), day + timedelta(days=k)):
            if fresh(p_of(other)) and _load(p_of(other)):
                return _load(p_of(other)), (day - other).days
    key = os.environ.get("IGNAV_API_KEY")
    if key:
        body = json.dumps({"origin": origin, "destination": dest, "departure_date": day.isoformat()}).encode()
        for i in range(tries):
            try:
                req = urllib.request.Request("https://ignav.com/api/fares/one-way", data=body, method="POST",
                                             headers={"X-Api-Key": key, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=45) as r:
                    data = json.load(r)
                if data and data.get("itineraries"):
                    json.dump(data, open(path, "w"), indent=1)
                    return data, 0
                print(f"[ignav] {origin}-{dest} {day}: empty result (not cached)")
                break
            except urllib.error.HTTPError as e:
                print(f"[ignav] {origin}-{dest} {day}: HTTP {e.code} (try {i + 1}/{tries})")
                if e.code != 424:
                    break
                time.sleep(3 * (i + 1))
            except Exception as e:
                print(f"[ignav] {origin}-{dest} {day}: {type(e).__name__} (try {i + 1}/{tries})")
                time.sleep(3)
    if os.path.exists(path) and _load(path):      # API down: fall back to an old cache
        return _load(path), 0
    return None, 0


_US, _NAMES = None, None


def _us():
    global _US, _NAMES
    if _US is None:
        s = pr.us_schedule()
        _US = set(s.origin) | set(s.dest)
        _NAMES = {}
        for c in s.airline.dropna().unique():
            n = str(pr.carrier_name(c) or "").lower()
            if n and n != str(c).lower():
                _NAMES[n] = c
    return _US, _NAMES


def _op_code(seg):
    _, names = _us()
    n = str(seg.get("operating_carrier_name") or "").lower()
    if n in names:
        return names[n]
    for k, c in names.items():
        if n and k.split()[0] == n.split()[0]:
            return c
    return seg.get("marketing_carrier_code") or ""


def _rng(x):
    if x is None:
        return None
    if isinstance(x, dict):
        return (x.get("lo", x.get("low")), x.get("hi", x.get("high")))
    return (float(x[0]), float(x[1]))


@lru_cache(maxsize=4096)
def _predict_sched(o, de, code, dep):
    """(forecast, region, (co2_lo, co2_hi) kg per seat if delayed) for one leg, or Nones."""
    us, _ = _us()
    day, hhmm = dep.date(), dep.hour * 100 + dep.minute
    if o in us and de in us:
        try:
            res = pr.predict_flight(o, de, code, day, hhmm)
            if not res:
                return None, None, None
            late = pr.typical_late_minutes(res["probs"], "US")
            try:
                co2 = _rng(pr.delay_co2_range_pp(None, late))
            except Exception:
                co2 = None
            return res, "US", co2
        except Exception:
            return None, None, None
    try:
        rows = pr.flights_on(o, de, day)
    except Exception:
        return None, None, None
    if rows.empty:
        return None, None, None
    m = dep.hour * 60 + dep.minute
    rows = rows.assign(_d=[abs((int(h) // 100) * 60 + int(h) % 100 - m) for h in rows.dep_hhmm])
    same = rows[rows.airline == code]
    r = (same if len(same) else rows).sort_values("_d").iloc[0]
    if r._d > 180:
        return None, None, None
    try:
        res = pr.predict_flight_eu(r, day)
        if not res:
            return None, None, None
        late = pr.typical_late_minutes(res["probs"], "EU")
        try:
            co2 = _rng(pr.delay_co2_range_pp_eu(r.ac_type, r.Fuel_Flow_Idle_kg_sec, r.Engine_Count, late))
        except Exception:
            co2 = None
        return res, "EU", co2
    except Exception:
        return None, None, None


_REF = None
_AC_MAP = [("A380", "A388"), ("A350-1000", "A35K"), ("A350", "A359"), ("A330-900", "A339"), ("A330NEO", "A339"),
           ("A330-300", "A333"), ("A330-200", "A332"), ("A330", "A333"), ("A321NEO", "A21N"), ("A321", "A321"),
           ("A320NEO", "A20N"), ("A320", "A320"), ("A319", "A319"), ("A220-300", "BCS3"), ("A220", "BCS1"),
           ("787-10", "B78X"), ("787-9", "B789"), ("787-8", "B788"), ("787", "B789"), ("777-300", "B77W"),
           ("777-200LR", "B77L"), ("777-200", "B772"), ("777", "B77W"), ("767-400", "B764"), ("767-300", "B763"),
           ("767", "B763"), ("757", "B752"), ("737 MAX 8", "B38M"), ("737-8", "B38M"), ("737 MAX 9", "B39M"),
           ("737-900", "B739"), ("737-800", "B738"), ("737-700", "B737"), ("737", "B738"), ("747-8", "B748"),
           ("747", "B744"), ("190", "E190"), ("195", "E195"), ("175", "E75L"), ("170", "E170"),
           ("CRJ900", "CRJ9"), ("CRJ-900", "CRJ9"), ("CRJ700", "CRJ7"), ("CRJ-700", "CRJ7"),
           ("ATR 72", "AT76"), ("Q400", "DH8D"), ("DASH 8", "DH8D")]


def _ac_icao(name):
    n = str(name or "").upper()
    for k, v in _AC_MAP:
        if k in n:
            return v
    return ""


def _ref():
    """IATA -> ICAO airport/airline maps and airport coordinates (for model-based estimates)."""
    global _REF
    if _REF is None:
        import pandas as pd
        data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        ap = pd.read_csv(os.path.join(data, "ref", "airports.csv"), keep_default_na=False, na_values=[""],
                         usecols=["ident", "iata_code", "latitude_deg", "longitude_deg"]).dropna(subset=["iata_code"])
        ap = ap.drop_duplicates("iata_code")
        eu = pd.read_csv(os.path.join(data, "eu_schedule.csv"), usecols=["airline_iata", "airline_icao"]).dropna()
        al = eu.groupby("airline_iata")["airline_icao"].agg(lambda v: v.value_counts().index[0]).to_dict()
        _REF = {"ap": dict(zip(ap.iata_code, ap.ident)),
                "ll": {k: (la, lo) for k, la, lo in zip(ap.iata_code, ap.latitude_deg, ap.longitude_deg)},
                "al": al}
    return _REF


def _gc_nm(a, b):
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 3440.065 * math.asin(math.sqrt(h))


def _estimate(o, de, code, dep, aircraft):
    """Tier 2: same EUROCONTROL model for a leg that is not in our schedule, from what the model knows
    (origin/destination airport, airline, hour, weekday, month, distance, aircraft type)."""
    try:
        import pandas as pd
        clf, meta = pr._load_eu()
        te, ref = meta["te_tables"], _ref()
        oi, di = ref["ap"].get(o), ref["ap"].get(de)
        if not oi or not di:
            return None, None, None
        ai = ref["al"].get(code, code)
        if not (oi in te["origin_te"] or di in te["dest_te"] or ai in te["airline_te"]):
            return None, None, None
        nm = _gc_nm(ref["ll"][o], ref["ll"][de])
        act = _ac_icao(aircraft)
        r = pd.Series({"dep_hhmm": dep.hour * 100 + dep.minute, "dist_nm": nm, "distance": nm * 1.15078,
                       "airline_icao": ai, "ac_type": act, "origin_icao": oi, "dest_icao": di})
        res = pr.predict_flight_eu(r, dep.date())
        if not res:
            return None, None, None
        res["tier"] = 2
        late = pr.typical_late_minutes(res["probs"], "EU")
        try:
            co2 = _rng(pr.delay_co2_range_pp_eu(act, float("nan"), float("nan"), late))
        except Exception:
            co2 = None
        return res, "EU", co2
    except Exception as e:
        print(f"[estimate] {o}-{de} {code}: {type(e).__name__} {e}")
        return None, None, None


@lru_cache(maxsize=4096)
def _predict(o, de, code, dep, aircraft=""):
    """Tier 1 (schedule match) first; for non-US-domestic legs fall back to the tier-2 model estimate."""
    from core import build_au as au
    if au.is_au(o) and au.is_au(de):              # Australian domestic leg: BITRE route x airline data
        fc = au.forecast(o, de, code, dep.month)
        if not fc:
            return None, None, None
        meta = pr._load()[2]
        prior = meta["bands"]["train_prior"]
        s_late = [x / sum(prior[1:]) for x in prior[1:]]          # within-late band shape borrowed from BTS
        p, pn = fc["p_late"], fc["national"]
        res = {"labels": meta["bands"]["labels"], "probs": [1 - p] + [p * x for x in s_late],
               "prior": [1 - pn] + [pn * x for x in s_late], "p_late": p, "base_late": pn,
               "ratio": p / pn, "level": pr.risk_level(p * pr.typical_late_minutes([1 - p] + [p * x for x in s_late], "US")), "cancel": fc["cancel"],
               "tier": 1, "src": "BITRE", "n": fc["n"]}
        late = pr.typical_late_minutes(res["probs"], "US")
        try:
            co2 = _rng(pr.delay_co2_range_pp(None, late))
        except Exception:
            co2 = None
        return res, "US", co2
    out = _predict_sched(o, de, code, dep)
    if out[0]:
        return out
    us, _ = _us()
    if o in us and de in us:
        return out
    return _estimate(o, de, code, dep, aircraft)


def _key(seg, day):
    """Key of the matching flight in our schedule (same format as the flight page), or None."""
    try:
        rows = pr.flights_on(seg["o"], seg["d"], day)
    except Exception:
        return None
    if rows.empty:
        return None
    m = seg["dep"].hour * 60 + seg["dep"].minute
    rows = rows.assign(_d=[abs((int(h) // 100) * 60 + int(h) % 100 - m) for h in rows.dep_hhmm])
    cand = rows[(rows.airline == seg["op"]) | (rows.airline == seg["code"])]
    try:
        ex = cand[cand.flight_number.fillna(0).astype(int) == int(seg["fn"])]
        if len(ex):
            cand = ex
    except (ValueError, TypeError):
        pass
    if cand.empty:
        return None
    r = cand.sort_values("_d").iloc[0]
    if r._d > 45:
        return None
    return f"{r.origin}-{r.dest}-{r.airline}-{int(r.flight_number)}-{int(r.dep_hhmm)}"


def _dt(x):
    return datetime.fromisoformat(str(x).replace("Z", "+00:00"))


def itineraries(origin, dest, day):
    data, shift = fetch(origin, dest, day)
    if not data:
        return None
    sh = timedelta(days=shift)
    us, _ = _us()
    out = []
    for it in data.get("itineraries", []):
        ob = it.get("outbound") or {}
        segs = []
        for s in ob.get("segments", []):
            dep, arr = _dt(s["departure_time_local"]) + sh, _dt(s["arrival_time_local"]) + sh
            op = _op_code(s)
            res, reg, co2 = _predict(s["departure_airport"], s["arrival_airport"], op, dep, s.get("aircraft") or "")
            segs.append({"code": s.get("marketing_carrier_code") or "", "fn": str(s.get("flight_number") or ""),
                         "op_name": s.get("operating_carrier_name") or "", "op": op,
                         "o": s["departure_airport"], "d": s["arrival_airport"], "dep": dep, "arr": arr,
                         "dep_utc": _dt(s["departure_time_utc"]) + sh, "arr_utc": _dt(s["arrival_time_utc"]) + sh,
                         "aircraft": s.get("aircraft") or "", "res": res, "region": reg, "co2": co2})
        if not segs:
            continue
        for sg in segs:
            sg["key"] = _key(sg, sg["dep"].date())
        transfers, p_ok, known = [], 1.0, True
        for a, b in zip(segs, segs[1:]):
            lay = int((b["dep_utc"] - a["arr_utc"]).total_seconds() // 60)
            mct = MCT_DOM if all(x in us for x in (a["o"], a["d"], b["o"], b["d"])) else MCT_INTL
            pm = None
            if a["res"]:
                pm = p_late_over(a["res"]["probs"], lay - mct, a["region"])
                p_ok *= 1 - pm
            else:
                known = False
            transfers.append({"hub": a["d"], "layover": lay, "p_miss": pm})
        total = ob.get("duration_minutes") or int((segs[-1]["arr_utc"] - segs[0]["dep_utc"]).total_seconds() // 60)
        out.append({"segs": segs, "transfers": transfers, "total": int(total),
                    "p_miss": (1 - p_ok) if transfers and known else None,
                    "price": it.get("price"), "id": it.get("ignav_id"), "shift": shift})
    return out


BOOK_MAX_AGE_H = 6   # booking links and prices go stale quickly


def _post(path, payload):
    key = os.environ.get("IGNAV_API_KEY")
    if not key:
        return None
    req = urllib.request.Request("https://ignav.com/api/" + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"X-Api-Key": key, "Content-Type": "application/json"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            print(f"[ignav] {path}: HTTP {e.code} (try {i + 1}/3)")
            if e.code != 424:
                return None
            time.sleep(3 * (i + 1))
        except Exception as e:
            print(f"[ignav] {path}: {type(e).__name__} (try {i + 1}/3)")
            time.sleep(3)
    return None


def _fns(segs):
    return [f'{s.get("marketing_carrier_code") or ""}{s.get("flight_number") or ""}' for s in segs]


def booking_links(origin, dest, day, fns, ig_id=None, shift=0):
    """Booking options for one itinerary (fns = ["UA901", "LH400"]), cached BOOK_MAX_AGE_H hours.
    1) ignav_id, only when the fare search was for this exact date; 2) manual flight details (single flight);
    3) fresh fare search for the exact date, matched by flight numbers, then its ignav_id."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"book_{origin}_{dest}_{day.isoformat()}_{'-'.join(fns)}.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < BOOK_MAX_AGE_H * 3600 and _load(path):
        return _load(path)
    data = None
    if ig_id and not shift:
        data = _post("fares/booking-links", {"ignav_id": ig_id})
    if not (data and data.get("booking_options")) and len(fns) == 1:
        data = _post("fares/booking-links", {"origin": origin, "destination": dest, "departure_date": day.isoformat(),
                                             "outbound_carrier_code": fns[0][:2], "outbound_flight_number": fns[0][2:]})
    if not (data and data.get("booking_options")):
        fresh = _post("fares/one-way", {"origin": origin, "destination": dest, "departure_date": day.isoformat()})
        if fresh and fresh.get("itineraries"):
            json.dump(fresh, open(os.path.join(CACHE, f"{origin}_{dest}_{day.isoformat()}.json"), "w"), indent=1)
            hit = next((it for it in fresh["itineraries"]
                        if _fns((it.get("outbound") or {}).get("segments", [])) == fns), None)
            if hit and hit.get("ignav_id"):
                data = _post("fares/booking-links", {"ignav_id": hit["ignav_id"]})
    if data and data.get("booking_options"):
        json.dump(data, open(path, "w"), indent=1)
        return data
    return None
