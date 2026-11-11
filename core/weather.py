"""Weather for a flight date at an airport, from Open-Meteo (free, no API key; CC BY 4.0).
Within 16 days: real forecast. Further ahead: typical weather for that date (same day in the
last 5 years). Not used by the delay model; shown as context with warnings."""
from datetime import date

import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
         "snowfall_sum,wind_speed_10m_max,wind_gusts_10m_max")
TIMEOUT = 6

WMO = [((0,), "Clear", "☀️"), ((1, 2), "Partly cloudy", "⛅"), ((3,), "Cloudy", "☁️"),
       ((45, 48), "Fog", "🌫️"), ((51, 53, 55, 56, 57), "Drizzle", "🌦️"),
       ((61, 63, 65, 66, 67, 80, 81, 82), "Rain", "🌧️"), ((71, 73, 75, 77, 85, 86), "Snow", "❄️"),
       ((95, 96, 99), "Thunderstorms", "⛈️")]


def describe(code):
    for codes, text, icon in WMO:
        if code in codes:
            return text, icon
    return "Mixed", "🌤️"


def _get(url, params):
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["daily"]


def _forecast(lat, lon, d):
    day = _get(FORECAST_URL, {"latitude": lat, "longitude": lon, "daily": DAILY, "timezone": "auto",
                              "start_date": d.isoformat(), "end_date": d.isoformat()})
    v = {k: day[k][0] for k in day if k != "time"}
    text, icon = describe(v["weather_code"])
    warn = []
    if v["weather_code"] in (95, 96, 99):
        warn.append("Thunderstorms forecast")
    if (v["snowfall_sum"] or 0) >= 1:
        warn.append("Snow forecast (%.0f cm)" % v["snowfall_sum"])
    if (v["wind_gusts_10m_max"] or 0) >= 60:
        warn.append("Strong gusts (%.0f km/h)" % v["wind_gusts_10m_max"])
    if v["weather_code"] in (45, 48):
        warn.append("Fog forecast")
    if (v["precipitation_sum"] or 0) >= 10:
        warn.append("Heavy rain (%.0f mm)" % v["precipitation_sum"])
    return {"kind": "forecast", "text": text, "icon": icon,
            "t_max": v["temperature_2m_max"], "t_min": v["temperature_2m_min"],
            "precip_mm": v["precipitation_sum"], "gust_kmh": v["wind_gusts_10m_max"], "warnings": warn}


def _typical(lat, lon, d, years=5):
    rows = []
    for y in range(date.today().year - years, date.today().year):
        try:
            dd = d.replace(year=y)
        except ValueError:          # 29 Feb
            dd = d.replace(year=y, day=28)
        try:
            day = _get(ARCHIVE_URL, {"latitude": lat, "longitude": lon, "daily": DAILY, "timezone": "auto",
                                     "start_date": dd.isoformat(), "end_date": dd.isoformat()})
        except Exception:
            continue                # one failed year should not drop the whole card
        rows.append({k: day[k][0] for k in day if k != "time"})
    rows = [r for r in rows if r["temperature_2m_max"] is not None]
    if not rows:
        return None
    n = len(rows)
    avg = lambda k: sum((r[k] or 0) for r in rows) / n
    snow_years = sum(1 for r in rows if (r["snowfall_sum"] or 0) >= 1)
    rain_years = sum(1 for r in rows if (r["precipitation_sum"] or 0) >= 1)
    storm_years = sum(1 for r in rows if r["weather_code"] in (95, 96, 99))
    codes = [r["weather_code"] for r in rows]
    text, icon = describe(max(set(codes), key=codes.count))
    warn = []
    if snow_years >= 2:
        warn.append("Snow on %d of %d years around this date" % (snow_years, n))
    if storm_years >= 2:
        warn.append("Thunderstorms on %d of %d years around this date" % (storm_years, n))
    return {"kind": "typical", "text": text, "icon": icon,
            "t_max": avg("temperature_2m_max"), "t_min": avg("temperature_2m_min"),
            "precip_mm": avg("precipitation_sum"), "gust_kmh": avg("wind_gusts_10m_max"),
            "rain_years": rain_years, "years": n, "warnings": warn}


def day_weather(lat, lon, d):
    """Weather dict for date d at (lat, lon), or None if unavailable (offline etc.)."""
    try:
        days_ahead = (d - date.today()).days
        if 0 <= days_ahead <= 15:
            w = _forecast(lat, lon, d)
            if w and w.get("t_max") is not None:
                return w
            return _typical(lat, lon, d)   # provider has no values for this day yet
        return _typical(lat, lon, d)
    except Exception:
        return None
