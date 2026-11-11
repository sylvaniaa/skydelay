"""Connection risk: real two-leg itineraries from the schedule (BTS timetable + EUROCONTROL sample)
and the chance of missing the connection, from the first leg's predicted arrival-delay distribution
(4-band probabilities x the real delay distribution inside each band)."""
import os

import numpy as np
import pandas as pd

from core import predict as pr

MCT_DOM = 45       # min. connection time, domestic -> domestic (minutes)
MCT_INTL = 90      # when either leg is international
MAX_LAYOVER = 360  # ignore layovers longer than 6 h

ALLIANCES = {
    "oneworld": "AA BA IB AY QR JL CX QF AS MH RJ UL WY AT FJ".split(),
    "Star Alliance": "UA LH LX OS SN AC NH SQ TK LO SK TP A3 OZ ET MS AI CA NZ TG ZH OU AV CM BR".split(),
    "SkyTeam": "DL AF KL AM KE VN MU CI GA SV KQ AR ME RO UX VS".split(),
}
# US regional carriers fly for these mainline airlines (operating vs marketing carrier)
REGIONAL = {"YX": ["AA", "DL", "UA"], "OO": ["AA", "DL", "UA", "AS"], "MQ": ["AA"], "OH": ["AA"], "PT": ["AA"],
            "9E": ["DL"], "G7": ["UA"], "C5": ["UA"], "ZW": ["AA", "UA"], "QX": ["AS"], "HA": ["AS"]}


# airline hubs: domestic connections must go through a real hub of one of the two airlines
HUBS = {"AA": "DFW CLT MIA ORD PHL PHX DCA LAX JFK LGA".split(),
        "DL": "ATL DTW MSP SLC SEA LAX JFK LGA BOS".split(),
        "UA": "ORD DEN IAH EWR SFO IAD LAX".split(),
        "AS": "SEA PDX SFO LAX ANC".split(),
        "B6": "JFK BOS FLL MCO".split(),
        "WN": "MDW DAL HOU DEN LAS BWI PHX MCO ATL".split(),
        "NK": "FLL LAS DTW MCO".split(),
        "F9": "DEN LAS MCO".split()}


def hub_ok(hub, code_a, code_b, intl):
    if intl:                      # international second leg: hub is a gateway airport
        return True
    parents = REGIONAL.get(code_a, [code_a]) + REGIONAL.get(code_b, [code_b])
    return any(hub in HUBS.get(p, []) for p in parents)


_MAP = None


def marketing(r):
    """(marketing carrier, flight number) of a BTS flight, from data/marketing_map.csv."""
    global _MAP
    if _MAP is None:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "marketing_map.csv")
        try:
            m = pd.read_csv(p)
            _MAP = {(x.op, int(x.op_fn), x.origin, x.dest): (x.mkt, int(x.mkt_fn)) for x in m.itertuples()}
        except Exception:
            _MAP = {}
    if r.region != "US":
        return r.airline, None
    fn = int(r.flight_number)
    return _MAP.get((r.airline, fn, r.origin, r.dest), (r.airline, fn))


def groups(code):
    code = str(code).strip().upper()
    out = {code}
    for p in REGIONAL.get(code, [code]):
        out.add(p)
        out.update(name for name, mem in ALLIANCES.items() if p in mem)
    return out


def same_ticket(a, b):
    return bool(groups(a) & groups(b))


def _mins(hhmm):
    h = int(hhmm)
    return (h // 100) * 60 + h % 100


def p_late_over(probs, t, region="US"):
    """P(arrival delay > t minutes) from band probabilities + real within-band delay quantiles."""
    if region == "EU":
        bq = pr._load_eu()[1]["bands"]["band_quantiles"]
        qs = [bq["1"], bq["2"], bq["3"]]
    else:
        qs = pr._load()[2]["bands"]["band_quantiles"]
    p = probs[0] * min(1.0, max(0.0, (15 - t) / 30.0)) if t < 15 else 0.0   # on-time band: -15..15 min
    for pk, q in zip(probs[1:], qs):
        q = np.asarray(q, float)
        p += pk * (1.0 - np.searchsorted(q, t, side="right") / len(q))
    return float(min(1.0, max(0.0, p)))


def _dedupe(df):
    return df.drop_duplicates(["airline", "flight_number", "dep_hhmm"])


def find_connections(origin, dest, flight_date, limit=8):
    s = pr.schedule()
    hubs = (set(s[s.origin == origin].dest) & set(s[s.dest == dest].origin)) - {origin, dest}
    l1_all = _dedupe(pr.flights_on(origin, None, flight_date))
    cands = []
    for hub in hubs:
        l1 = l1_all[l1_all.dest == hub]
        if l1.empty:
            continue
        l2 = _dedupe(pr.flights_on(hub, dest, flight_date))
        for a in l1.itertuples():
            if a.region != "US":        # first leg must be a BTS flight (local times, model trained on it)
                continue
            dep1, arr1 = _mins(a.dep_hhmm), _mins(a.arr_hhmm)
            mk, mk_fn = marketing(a)
            if arr1 < dep1:            # first leg lands after midnight: skip
                continue
            for b in l2.itertuples():
                mk2 = marketing(b)[0]
                if not same_ticket(mk, mk2) or not hub_ok(hub, mk, mk2, b.region == "EU"):
                    continue
                mct = MCT_INTL if "EU" in (a.region, b.region) else MCT_DOM
                lay = _mins(b.dep_hhmm) - arr1
                if mct <= lay <= MAX_LAYOVER:
                    cands.append({"hub": hub, "l1": a, "l2": b, "mkt": mk, "mkt_fn": mk_fn, "layover": lay, "mct": mct,
                                  "total": float(a.block_min) + lay + float(b.block_min)})
    cands.sort(key=lambda c: c["total"])
    out = []
    seen, memo = {}, {}
    for c in cands:
        if len(out) >= limit:
            break
        a = c["l1"]
        k = (a.airline, a.flight_number, a.dep_hhmm)
        if seen.get(k, 0) >= 2:
            continue
        seen[k] = seen.get(k, 0) + 1
        if k not in memo:
            if a.region == "EU":
                memo[k] = pr.predict_flight_eu(a, flight_date)
            else:
                fam = a.family if isinstance(a.family, str) else None
                memo[k] = pr.predict_flight(a.origin, a.dest, a.airline, flight_date, a.dep_hhmm, fam, a.distance)
        res = memo[k]
        if not res:
            continue
        c["p_miss"] = p_late_over(res["probs"], c["layover"] - c["mct"], a.region)
        c["res"] = res
        out.append(c)
    return out[:limit]


_REACH = None


def reach_one_stop():
    """origin -> destinations reachable with one connection through a real hub (first leg = BTS)."""
    global _REACH
    if _REACH is None:
        s = pr.schedule()
        us = s[s.region == "US"].groupby("origin").dest.apply(set).to_dict()
        allr = s.groupby("origin").dest.apply(set).to_dict()
        hubs = {h for v in HUBS.values() for h in v}
        _REACH = {}
        for o, ds in us.items():
            r = set()
            for h in ds & hubs:
                r |= allr.get(h, set())
            _REACH[o] = r - allr.get(o, set()) - {o}
    return _REACH
