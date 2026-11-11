import os
from functools import lru_cache

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
MONTH_ABBR = [m[:3] for m in MONTH_NAMES]

US_INFO = {
    "ATL": ("Hartsfield–Jackson Atlanta International", "Atlanta"),
    "ORD": ("O'Hare International", "Chicago"),
    "DFW": ("Dallas/Fort Worth International", "Dallas–Fort Worth"),
    "DEN": ("Denver International", "Denver"),
    "JFK": ("John F. Kennedy International", "New York"),
    "LGA": ("LaGuardia", "New York"),
    "EWR": ("Newark Liberty International", "Newark"),
    "LAX": ("Los Angeles International", "Los Angeles"),
    "SFO": ("San Francisco International", "San Francisco"),
    "SEA": ("Seattle–Tacoma International", "Seattle"),
    "MIA": ("Miami International", "Miami"),
    "BOS": ("Logan International", "Boston"),
    "LAS": ("Harry Reid International", "Las Vegas"),
    "PHX": ("Phoenix Sky Harbor International", "Phoenix"),
    "MCO": ("Orlando International", "Orlando"),
    "CLT": ("Charlotte Douglas International", "Charlotte"),
    "IAH": ("George Bush Intercontinental", "Houston"),
    "MSP": ("Minneapolis–Saint Paul International", "Minneapolis"),
    "DTW": ("Detroit Metropolitan Wayne County", "Detroit"),
    "PHL": ("Philadelphia International", "Philadelphia"),
    "FLL": ("Fort Lauderdale–Hollywood International", "Fort Lauderdale"),
    "BWI": ("Baltimore/Washington International", "Baltimore"),
    "SLC": ("Salt Lake City International", "Salt Lake City"),
    "SAN": ("San Diego International", "San Diego"),
    "DCA": ("Ronald Reagan Washington National", "Washington, D.C."),
    "MDW": ("Chicago Midway International", "Chicago"),
    "TPA": ("Tampa International", "Tampa"),
    "PDX": ("Portland International", "Portland"),
    "HNL": ("Daniel K. Inouye International", "Honolulu"),
    "AUS": ("Austin–Bergstrom International", "Austin"),
}

EU_INFO = {
    "LTFM": ("Istanbul Airport", "Istanbul", "Türkiye"),
    "EHAM": ("Amsterdam Schiphol", "Amsterdam", "Netherlands"),
    "EGLL": ("London Heathrow", "London", "United Kingdom"),
    "LFPG": ("Paris Charles de Gaulle", "Paris", "France"),
    "EDDF": ("Frankfurt Airport", "Frankfurt", "Germany"),
    "LEMD": ("Madrid–Barajas", "Madrid", "Spain"),
    "LEBL": ("Barcelona–El Prat", "Barcelona", "Spain"),
    "EDDM": ("Munich Airport", "Munich", "Germany"),
    "LIRF": ("Rome Fiumicino", "Rome", "Italy"),
    "EGKK": ("London Gatwick", "London", "United Kingdom"),
    "EIDW": ("Dublin Airport", "Dublin", "Ireland"),
    "LGAV": ("Athens International", "Athens", "Greece"),
    "LSZH": ("Zurich Airport", "Zurich", "Switzerland"),
    "LOWW": ("Vienna International", "Vienna", "Austria"),
    "EKCH": ("Copenhagen Airport", "Copenhagen", "Denmark"),
    "ENGM": ("Oslo Gardermoen", "Oslo", "Norway"),
    "ESSA": ("Stockholm Arlanda", "Stockholm", "Sweden"),
    "EFHK": ("Helsinki–Vantaa", "Helsinki", "Finland"),
    "LPPT": ("Lisbon Humberto Delgado", "Lisbon", "Portugal"),
    "LIMC": ("Milan Malpensa", "Milan", "Italy"),
    "EBBR": ("Brussels Airport", "Brussels", "Belgium"),
    "EDDB": ("Berlin Brandenburg", "Berlin", "Germany"),
    "EDDL": ("Düsseldorf Airport", "Düsseldorf", "Germany"),
    "EDDH": ("Hamburg Airport", "Hamburg", "Germany"),
    "EGCC": ("Manchester Airport", "Manchester", "United Kingdom"),
    "EGSS": ("London Stansted", "London", "United Kingdom"),
    "LFPO": ("Paris Orly", "Paris", "France"),
    "LFMN": ("Nice Côte d'Azur", "Nice", "France"),
    "LEPA": ("Palma de Mallorca", "Palma", "Spain"),
    "LEMG": ("Málaga–Costa del Sol", "Málaga", "Spain"),
    "LEAL": ("Alicante–Elche", "Alicante", "Spain"),
    "EPWA": ("Warsaw Chopin", "Warsaw", "Poland"),
    "LKPR": ("Prague Václav Havel", "Prague", "Czechia"),
    "LHBP": ("Budapest Ferenc Liszt", "Budapest", "Hungary"),
    "LROP": ("Bucharest Henri Coandă", "Bucharest", "Romania"),
    "LBSF": ("Sofia Airport", "Sofia", "Bulgaria"),
    "LDZA": ("Zagreb Airport", "Zagreb", "Croatia"),
    "LYBE": ("Belgrade Nikola Tesla", "Belgrade", "Serbia"),
    "LCLK": ("Larnaca International", "Larnaca", "Cyprus"),
    "LMML": ("Malta International", "Valletta", "Malta"),
    "BIKF": ("Keflavík International", "Reykjavík", "Iceland"),
    "LIME": ("Bergamo Orio al Serio", "Bergamo", "Italy"),
    "LIPZ": ("Venice Marco Polo", "Venice", "Italy"),
    "EGPH": ("Edinburgh Airport", "Edinburgh", "United Kingdom"),
    "EGBB": ("Birmingham Airport", "Birmingham", "United Kingdom"),
    "LSGG": ("Geneva Airport", "Geneva", "Switzerland"),
    "ENBR": ("Bergen Flesland", "Bergen", "Norway"),
    "ESGG": ("Gothenburg Landvetter", "Gothenburg", "Sweden"),
}

PERIODS = [("Overnight", 0, 4), ("Morning", 5, 11), ("Afternoon", 12, 17), ("Evening", 18, 23)]


def region_of(code):
    # US airports use 3-letter IATA codes, European airports 4-letter ICAO codes
    return "Europe" if len(str(code)) == 4 else "United States"


def _read(name):
    path = os.path.join(DATA_DIR, name)
    return pd.read_csv(path) if os.path.exists(path) else None


@lru_cache(maxsize=1)
def load_monthly():
    parts = [p for p in (_read("monthly.csv"), _read("monthly_eu.csv")) if p is not None]
    return pd.concat(parts, ignore_index=True)


@lru_cache(maxsize=1)
def load_hourly():
    parts = [p for p in (_read("hourly.csv"), _read("hourly_eu.csv")) if p is not None]
    return pd.concat(parts, ignore_index=True)


def _region_mask(frame, region):
    is_eu = frame["airport"].astype(str).str.len() == 4
    return is_eu if region == "Europe" else ~is_eu


def airport_list(region=None):
    m = load_monthly()
    m = m[(m.n_dep.fillna(0) > 0) & (m.n_arr.fillna(0) > 0)]
    if region:
        m = m[_region_mask(m, region)]
    totals = m.groupby("airport")["n_dep"].sum()
    totals = totals[totals >= 1000]
    return list(totals.sort_values(ascending=False).index)


def airport_info(code):
    if region_of(code) == "Europe":
        name, city, country = EU_INFO.get(code, (code + " Airport", "—", "Europe"))
        return {"name": name, "city": city, "country": country, "region": "Europe"}
    name, city = US_INFO.get(code, (code + " Airport", "—"))
    return {"name": name, "city": city, "country": "United States", "region": "United States"}


def month_label(year, month):
    return MONTH_NAMES[int(month) - 1] + " " + str(int(year))


def all_months(region=None):
    m = load_monthly()
    if region:
        m = m[_region_mask(m, region)]
    m = m[["Year", "Month"]].drop_duplicates().sort_values(["Year", "Month"], ascending=False)
    return [(int(y), int(mo)) for y, mo in zip(m.Year, m.Month)]


def month_options(code):
    m = load_monthly()
    r = m[(m.airport == code) & (m.n_dep.fillna(0) > 0) & (m.n_arr.fillna(0) > 0)]
    r = r.sort_values(["Year", "Month"], ascending=False)
    return [(int(y), int(mo)) for y, mo in zip(r.Year, r.Month)]


def get_month(code, year, month):
    m = load_monthly()
    r = m[(m.airport == code) & (m.Year == year) & (m.Month == month)]
    if r.empty:
        return None
    return r.iloc[0].to_dict()


def airport_table(year, month, min_flights=300, region=None):
    m = load_monthly()
    r = m[(m.Year == year) & (m.Month == month)
          & (m.n_dep.fillna(0) >= min_flights) & (m.n_arr.fillna(0) > 0)].copy()
    if region:
        r = r[_region_mask(r, region)]
    return r.sort_values("n_dep", ascending=False)


def hour_label(h):
    h = int(h)
    suffix = "a" if h < 12 else "p"
    return str(h % 12 or 12) + suffix


def get_hourly(code, year, month, min_n=5):
    h = load_hourly()
    h = h[(h.airport == code) & (h.Year == year) & (h.Month == month) & (h.n >= min_n)]
    h = h.sort_values("hour").copy()
    h["label"] = h.hour.apply(hour_label)
    return h[["hour", "label", "n", "avg_dep_delay"]]


def peak_period(code, year, month):
    h = get_hourly(code, year, month)
    best, best_val = None, None
    for name, lo, hi in PERIODS:
        s = h[(h.hour >= lo) & (h.hour <= hi)]
        if s.n.sum() == 0:
            continue
        val = (s.avg_dep_delay * s.n).sum() / s.n.sum()
        if best_val is None or val > best_val:
            best, best_val = name, val
    return best


def monthly_series(code, column, year, month, n=12):
    m = load_monthly()
    r = m[(m.airport == code) & ((m.Year * 12 + m.Month) <= year * 12 + month)]
    r = r.sort_values(["Year", "Month"]).tail(n).copy()
    r["label"] = [MONTH_ABBR[int(mo) - 1] + " " + str(int(y))[2:] for y, mo in zip(r.Year, r.Month)]
    r["value"] = r[column]
    return r[["label", "value"]]


def export_csv(code):
    m = load_monthly()
    r = m[m.airport == code].sort_values(["Year", "Month"])
    return r.to_csv(index=False).encode("utf-8")