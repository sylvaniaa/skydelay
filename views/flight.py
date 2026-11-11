"""Check a flight (planning tool): from/to + date -> reliability-across-the-day strip and
sortable booking-style flight cards with an on-time chip; tap a card to expand its forecast."""
import base64
import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st
from core.loader import loading

from core import predict as pr
from core.weather import day_weather
from views.airport_picker import airport_picker, lookup

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
<style>
.hero{padding:24px 0 4px 0;}
.hero-title{font-size:2.3rem;font-weight:700;color:#111418;letter-spacing:-.02em;}
.strip{background:#FFFFFF;border:1px solid #E2E6EC;border-radius:16px;padding:16px 20px 8px 20px;margin:18px 0 6px 0;}
.strip-h{font-weight:600;color:#111418;font-size:1.05rem;}
.strip-s{color:#111418;font-size:.95rem;margin-top:2px;}
.strip svg{width:100%;height:auto;margin-top:6px;}
.legend{display:flex;gap:16px;flex-wrap:wrap;color:#111418;font-size:.82rem;margin:2px 0 8px 0;}
.legend span{display:inline-flex;align-items:center;gap:6px;}
.ldot{width:10px;height:10px;border-radius:50%;display:inline-block;}
details.fc{background:#FFFFFF;border:1px solid #E2E6EC;border-radius:16px;margin:10px 0;box-shadow:0 1px 3px rgba(11,31,51,.04);}
details.fc:hover{border-color:#0055A0;}
details.fc[open]{border:2px solid #0055A0;}
details.fc > summary{list-style:none;cursor:pointer;padding:16px 22px;}
details.fc > summary::-webkit-details-marker{display:none;}
.fc-top{display:flex;align-items:center;gap:18px;}
.fc-end{min-width:70px;}
.fc-time{font-size:1.45rem;font-weight:700;color:#111418;line-height:1.2;}
.fc-time sup{font-size:.68rem;color:#D45252;margin-left:2px;font-weight:600;}
.fc-code{color:#111418;font-size:.9rem;font-weight:500;}
.fc-mid{flex:1;max-width:420px;text-align:center;}
.fc-dur{color:#111418;font-size:.85rem;}
.fc-line{height:1px;background:#C9DEEE;margin:6px 0;}
.fc-right{margin-left:auto;text-align:right;}
.chip-ot{display:inline-block;border-radius:999px;padding:6px 14px;font-weight:600;font-size:.95rem;white-space:nowrap;}
.fc-more{color:#111418;font-size:.8rem;margin-top:6px;}
details.fc[open] .fc-more{visibility:hidden;}
.fc-sub{margin-top:10px;color:#111418;font-size:.95rem;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.fno{color:#111418;font-size:.88rem;}
.badge{border-radius:999px;padding:2px 10px;font-size:.8rem;font-weight:600;}
.b-rel{background:#DCEAF6;color:#003F7A;}
.b-co2{background:#EAF6E3;color:#3F7A1F;}
.logo{width:28px;height:28px;object-fit:contain;border-radius:6px;background:#FFFFFF;flex:none;}
.al{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;
  background:#DCEAF6;color:#0055A0;font-size:.62rem;font-weight:700;}
.fx{padding:4px 22px 20px 22px;border-top:1px solid #E9F1F7;}
.vx{display:flex;gap:14px;align-items:flex-start;margin-top:16px;}
.halo{display:inline-block;width:14px;height:14px;border-radius:50%;margin-top:9px;flex:none;}
.vh{font-size:1.35rem;font-weight:700;color:#111418;}
.vs{color:#111418;margin-top:2px;}
.fx-grid{display:flex;gap:14px;flex-wrap:wrap;margin-top:16px;}
.fx-box{flex:1;min-width:240px;background:#F7FAFC;border-radius:14px;padding:14px 16px;}
.fx-box .k{color:#111418;font-size:.85rem;}
.fx-box .v{font-size:1.15rem;font-weight:600;color:#111418;margin-top:2px;}
.fx-box .s{color:#111418;font-size:.85rem;margin-top:4px;}
details.more{margin-top:14px;}
details.more > summary{cursor:pointer;color:#0055A0;font-weight:600;font-size:.92rem;}
.bandbar{display:flex;height:14px;border-radius:999px;overflow:hidden;margin:14px 0 8px 0;background:#E9F1F7;}
.band-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #E9F1F7;color:#111418;}
.band-row .avg{color:#111418;font-size:.88rem;margin-left:12px;}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:9px;}
.co2note{color:#111418;font-size:.8rem;margin-top:10px;line-height:1.45;}
.risk-tag{display:inline-flex;align-items:center;gap:6px;border-radius:6px;padding:4px 10px;
  font-size:.78rem;font-weight:700;letter-spacing:.04em;white-space:nowrap;}
.rdot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.sec{font-size:1.1rem;font-weight:700;color:#111418;margin:22px 0 2px 0;}
.sec2{font-weight:700;color:#111418;margin:20px 0 4px 0;font-size:1rem;}
.muted{color:#111418;font-size:.88rem;}
.segbar{display:flex;gap:3px;height:8px;margin:10px 0 8px 0;}
.segbar div{border-radius:999px;}
.stats{display:flex;gap:10px;flex-wrap:wrap;}
.st{flex:1;min-width:110px;}
.st-k{color:#111418;font-size:.85rem;display:flex;align-items:center;gap:6px;}
.st-bar{width:3px;height:14px;border-radius:2px;display:inline-block;}
.st-v{font-size:1.6rem;font-weight:700;color:#111418;}
.st-n{color:#111418;font-size:.8rem;}
.wx{display:flex;gap:12px;flex-wrap:wrap;margin-top:6px;}
.wx-box{flex:1;min-width:220px;background:#F7FAFC;border-radius:14px;padding:12px 14px;}
.wx-top{display:flex;align-items:center;gap:10px;}
.wx-icon{font-size:1.8rem;}
.wx-city{font-weight:600;color:#111418;}
.wx-kind{color:#111418;font-size:.78rem;}
.wx-t{font-size:1.15rem;font-weight:700;color:#111418;margin-top:6px;}
.wx-s{color:#111418;font-size:.85rem;}
.warn{background:#FEF0C7;color:#8A5A00;border-radius:10px;padding:9px 13px;margin-top:14px;font-size:.92rem;}
.code{border:1px solid #C9DEEE;border-radius:5px;padding:0 6px;font-size:.8rem;color:#111418;}
.pg-card{background:#FFFFFF;border:1px solid #E2E6EC;border-radius:18px;padding:22px 26px;margin:14px 0;}
.pg-title{font-size:1.9rem;font-weight:700;color:#111418;line-height:1.1;}
.pg-sub{color:#111418;font-size:.95rem;margin-top:2px;}
.h-row{display:flex;align-items:center;gap:16px;}
.h-logo .logo{width:60px;height:60px;}
.h-logo .al{width:52px;height:52px;font-size:.9rem;}
a.full-link{display:inline-block;margin-top:14px;color:#0055A0 !important;font-weight:600;text-decoration:none !important;}
a.alt-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #E9F1F7;text-decoration:none !important;color:#111418 !important;}
div[class*="st-key-pgc_"]{background:#FFFFFF;border:1px solid #E2E6EC;border-radius:18px;padding:22px 26px;margin:4px 0 6px 0;}
.ct{font-size:1.15rem;}
.ct svg{width:20px;height:20px;}
.stats4{display:grid;grid-template-columns:repeat(auto-fit,minmax(74px,1fr));gap:10px 12px;}
.s4-l{font-size:.8rem;overflow:hidden;text-overflow:ellipsis;}
.s4-v{font-size:1.75rem;white-space:nowrap;}
.s4-c{font-size:.78rem;}
.big{font-size:2.3rem;}
.st-title{font-size:1.15rem;}
.st-k{font-size:.92rem;}
.st-v{font-size:.88rem;}
.wr-t{font-size:1.8rem;}
.hb-t{white-space:nowrap;}
.spark{flex:1;display:flex;align-items:flex-end;gap:2px;height:32px;}
.sb{flex:1;min-width:3px;border-radius:2px;position:relative;}
.sb:hover{filter:brightness(.85);}
.sb-tip{display:none;position:absolute;bottom:36px;left:50%;transform:translateX(-50%);background:#0B0F14;color:#fff;
  font-style:normal;font-size:.78rem;font-weight:600;padding:6px 9px;border-radius:8px;white-space:nowrap;z-index:6;}
.sb:hover .sb-tip{display:block;}
.hb-val{width:62px !important;}
@media (max-width:1200px){
  div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-pgc_"]){flex-wrap:wrap !important;}
  div[data-testid="stColumn"]:has(div[class*="st-key-pgc_"]),
  div[data-testid="stColumn"]:has(div[class*="st-key-pgs_"]){flex:1 1 calc(50% - 1rem) !important;min-width:calc(50% - 1rem) !important;}
}
@media (max-width:800px){
  div[data-testid="stColumn"]:has(div[class*="st-key-pgc_"]),
  div[data-testid="stColumn"]:has(div[class*="st-key-pgs_"]){flex:1 1 100% !important;min-width:100% !important;}
}
</style>
"""

BAND_COLORS = ["#2C9A69", "#E8B53A", "#E07B39", "#D45252"]
BAND_NAMES = ["On time (≤15 min)", "15–60 min late", "1–2 h late", "Over 2 h late"]
LEVEL_COLORS = {"Low": "#2C9A69", "Moderate": "#D99019", "High": "#D45252"}
LEVEL_HALO = {"Low": "#DDF3E8", "Moderate": "#FEF0C7", "High": "#FEE4E2"}
LEVEL_TEXT = {"Low": "#1F7A52", "Moderate": "#8A5A00", "High": "#B42318"}


def aircraft_name(fam):
    if not isinstance(fam, str) or not fam or fam == "nan":
        return "Aircraft n/a"
    if fam[0] == "7":
        return "Boeing " + fam
    if fam.startswith("A3"):
        return "Airbus " + fam
    if fam.startswith("ERJ") or fam.startswith("EMB"):
        return "Embraer " + fam
    return {"CL": "Bombardier CRJ", "BD": "Airbus A220"}.get(fam, fam)


def in_ten(p):
    if p >= 0.95:
        return "19 in 20"
    return f"{int(round(p * 10))} in 10"


def one_in(p):
    if p < 0.005:
        return "very rare"
    return f"about 1 in {int(round(1 / p))}"


def pct(x):
    v = 100 * x
    return f"{v:.0f}%" if v >= 10 else f"{v:.1f}%"


def kg(x):
    return f"{x:.1f}" if x < 10 else f"{x:.0f}"


def verdict(p0):
    if p0 >= 0.85:
        return "Usually on time"
    if p0 >= 0.75:
        return "Mostly on time"
    if p0 >= 0.65:
        return "Delays are common"
    return "Often delayed"


def late_text(probs):
    p_late = sum(probs[1:])
    short = probs[1] / p_late if p_late > 0 else 1
    if short >= 0.6:
        return "Usually under 1 hour"
    if short >= 0.4:
        return "Often under 1 hour"
    return "Often over 1 hour"


_LOGO_FAILED = set()


@lru_cache(maxsize=None)
def logo_html(code):
    path = os.path.join(APP_DIR, "data", "logos", code + ".png")
    if not os.path.exists(path) and code and len(str(code)) == 2 and code not in _LOGO_FAILED:
        from core.fetch_logos import fetch
        if not fetch(str(code)):
            _LOGO_FAILED.add(code)       # try once per run, never slow the page down twice
    if os.path.exists(path):
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        return f'<img class="logo" src="data:image/png;base64,{b64}" alt="{code}">'
    return f'<span class="al">{code}</span>'


_logo_html_raw = logo_html
_LOGO_HTML = {}


def logo_html(code):
    """Cached: each airline logo is read (and base64-encoded) once per run."""
    if code not in _LOGO_HTML:
        _LOGO_HTML[code] = _logo_html_raw(code)
    return _LOGO_HTML[code]


def day_shift(origin, dest, d, dep_hhmm, block):
    lk = lookup()
    tz_o = (lk.get(origin) or {}).get("tz") or "UTC"
    tz_d = (lk.get(dest) or {}).get("tz") or tz_o
    dep = datetime(d.year, d.month, d.day, dep_hhmm // 100, dep_hhmm % 100, tzinfo=ZoneInfo(tz_o))
    arr = (dep.astimezone(timezone.utc) + timedelta(minutes=int(block))).astimezone(ZoneInfo(tz_d))
    return (arr.date() - d).days


@st.cache_data(show_spinner=False)
def day_predictions(origin, dest, date_iso):
    d = date.fromisoformat(date_iso)
    return predict_rows(pr.flights_on(origin, dest, d), d)


def predict_rows(df, d):
    """Forecast for each scheduled flight in df (rows of the schedule) on date d."""
    out = []
    pre = pr.predict_batch(df, d)
    for _i, (_, r) in enumerate(df.iterrows()):
        fam = r.family if isinstance(r.family, str) else None
        region = r.get("region", "US")
        res = pre[_i] if pre else None
        if res is None:
            if region == "EU":
                res = pr.predict_flight_eu(r, d)
            else:
                res = pr.predict_flight(r.origin, r.dest, r.airline, d, int(r.dep_hhmm), fam, float(r.distance))
        probs = res["probs"]
        p_late = sum(probs[1:])
        m_late = pr.typical_late_minutes(probs, region)
        svc = (r.airline_icao, r.origin_icao, r.dest_icao, int(r.dep_min), int(r.weekday)) if region == "EU" else None
        hist = hist_for({"region": region, "svc": svc, "airline": r.airline,
                         "flight_number": int(r.flight_number), "origin": r.origin, "dest": r.dest})
        if hist and hist["delayed"] and pd.notna(hist["median_late"]):
            k = int(hist["delayed"])
            m_late = (10 * m_late + k * float(hist["median_late"])) / (10 + k)
        exp_delay = p_late * m_late
        base_exp = (1 - res["prior"][0]) * pr.typical_late_minutes(res["prior"], region)
        res["ratio"] = exp_delay / base_exp
        res["level"] = pr.risk_level(exp_delay)
        if region == "EU":
            lo, hi = pr.delay_co2_range_pp_eu(r.ac_type, r.Fuel_Flow_Idle_kg_sec, r.Engine_Count, m_late)
        else:
            lo, hi = pr.delay_co2_range_pp(fam, m_late)
        out.append({"origin": r.origin, "dest": r.dest, "airline": r.airline,
                    "airline_name": r.airline_name, "flight_number": int(r.flight_number),
                    "dep_hhmm": int(r.dep_hhmm), "dep_time": r.dep_time, "arr_time": r.arr_time,
                    "block_min": int(r.block_min), "family": fam, "res": res, "p0": probs[0],
                    "m_late": m_late, "exp_delay": exp_delay, "key": f"{r.origin}-{r.dest}-{r.airline}-{int(r.flight_number)}-{int(r.dep_hhmm)}", "co2_lo": lo, "co2_hi": hi, "exp_co2": p_late * hi,
                    "region": region, "svc": svc, "ac_type": (r.ac_type if region == "EU" else pr.US_REP.get(fam or "", "")), "shift": day_shift(r.origin, r.dest, d, int(r.dep_hhmm), int(r.block_min))})
    return out


def strip_html(flights):
    mins = [(f["dep_hhmm"] // 100) * 60 + f["dep_hhmm"] % 100 for f in flights]
    start = max(0, min(mins) // 60 - 1) * 60
    end = min(24 * 60, (max(mins) // 60 + 2) * 60)
    left, right = 30, 970
    pts = sorted(((left + (m - start) / (end - start) * (right - left), f) for m, f in zip(mins, flights)),
                 key=lambda t: t[0])
    lanes, dots = [], []
    for x, f in pts:
        lane = next((i for i, last in enumerate(lanes) if x - last >= 16), None)
        if lane is None:
            lanes.append(x)
            lane = len(lanes) - 1
        else:
            lanes[lane] = x
        y = 22 + lane * 18
        c = LEVEL_COLORS[f["res"]["level"]]
        tip = f'{f["dep_time"]} · {f["airline"]} {f["flight_number"]} · {in_ten(f["p0"])} on time'
        dots.append(f'<circle cx="{x:.1f}" cy="{y}" r="7" fill="{c}"><title>{tip}</title></circle>')
    axis_y = 22 + max(len(lanes), 1) * 18 + 6
    h = axis_y + 26
    ticks = []
    t = ((start + 179) // 180) * 180
    while t <= end:
        x = left + (t - start) / (end - start) * (right - left)
        ticks.append(f'<line x1="{x:.1f}" y1="{axis_y}" x2="{x:.1f}" y2="{axis_y + 5}" stroke="#C9DEEE"/>'
                     f'<text x="{x:.1f}" y="{axis_y + 20}" font-size="13" fill="#8592A6" text-anchor="middle" '
                     f'font-family="Plus Jakarta Sans,sans-serif">{t // 60:02d}:00</text>')
        t += 180
    svg = (f'<svg viewBox="0 0 1000 {h}" xmlns="http://www.w3.org/2000/svg">'
           f'<line x1="{left}" y1="{axis_y}" x2="{right}" y2="{axis_y}" stroke="#C9DEEE"/>'
           + "".join(ticks) + "".join(dots) + '</svg>')

    parts = [("Morning", 0, 720), ("Afternoon", 720, 1020), ("Evening", 1020, 1440)]
    means = []
    for name, a, b in parts:
        ps = [f["p0"] for m, f in zip(mins, flights) if a <= m < b]
        if ps:
            means.append((sum(ps) / len(ps), name))
    if len(means) == 1:
        insight = f"All flights on this day leave in the {means[0][1].lower()}."
    else:
        best, worst = max(means), min(means)
        if best[0] - worst[0] >= 0.02:
            insight = (f"{best[1]} departures are the most likely to be on time on this route; "
                       f"{worst[1].lower()} departures the least.")
        else:
            insight = "Delay chances are similar throughout the day on this route."
    legend = ('<div class="legend">'
              '<span style="font-weight:700">Expected delay</span>'
              f'<span><span class="ldot" style="background:{LEVEL_COLORS["Low"]}"></span>under {pr.RISK_MINUTES[0]} min</span>'
              f'<span><span class="ldot" style="background:{LEVEL_COLORS["Moderate"]}"></span>{pr.RISK_MINUTES[0]}–{pr.RISK_MINUTES[1]} min</span>'
              f'<span><span class="ldot" style="background:{LEVEL_COLORS["High"]}"></span>{pr.RISK_MINUTES[1]}+ min</span></div>')
    return ('<div class="strip"><div class="strip-h">Reliability across the day</div>'
            f'<div class="strip-s">{insight}</div>{svg}{legend}</div>')


VERDICT = {
    "Low": ('Usually on time', 'Under 15 min expected delay'),
    "Moderate": ('Mostly on time', '15–30 min expected delay'),
    "High": ('Often late', '30+ min expected delay'),
}
REGION_WORD = {"US": "US", "EU": "European"}


def verdict_text(level, region="US"):
    head, sub = VERDICT[level]
    return head, sub.format(REGION_WORD.get(region, "US"))


def late_minutes_text(m):
    mm = int(round(m))
    if mm >= 60:
        return f"≈ {mm // 60} h {mm % 60:02d} min late"
    return f"≈ {mm} min late"


@lru_cache(maxsize=1)
def history():
    h = pd.read_csv(os.path.join(APP_DIR, "data", "flight_history.csv"))
    return {(r.airline, int(r.flight_number), r.origin, r.dest): r._asdict()
            for r in h.itertuples(index=False)}


@st.cache_data(ttl=3600, show_spinner=False)
def get_weather(code, date_iso):
    a = lookup().get(code)
    if not a or a.get("lat") in (None, ""):
        return None
    return day_weather(float(a["lat"]), float(a["lon"]), date.fromisoformat(date_iso))


@lru_cache(maxsize=1)
def eu_hist():
    h = pd.read_csv(os.path.join(APP_DIR, "data", "eu_flight_history.csv.gz"))
    idx = h.groupby(["airline_icao", "origin_icao", "dest_icao", "dep_min", "weekday"]).indices
    return h, idx


def eu_rows(svc):
    h, idx = eu_hist()
    ii = idx.get(tuple(svc)) if svc else None
    return h.iloc[ii] if ii is not None else h.iloc[0:0]


def hist_for(f):
    """Track-record summary: US = BTS flight-number history; EU = EUROCONTROL service history
    (same airline, route, filed departure time and weekday)."""
    if f.get("region") != "EU":
        return history().get((f["airline"], f["flight_number"], f["origin"], f["dest"]))
    g = eu_rows(f.get("svc"))
    if g.empty:
        return None
    late = g.arr_delay_min > 15
    return {"n": len(g), "on_time": int((~late).sum()), "delayed": int(late.sum()),
            "cancelled": 0, "diverted": 0,
            "median_late": float(g.arr_delay_min[late].median()) if late.any() else float("nan")}


def days_for(f):
    if f.get("region") == "EU":
        g = eu_rows(f.get("svc")).sort_values("date").tail(20)
        return pd.DataFrame({"date": g.date.values, "arr_delay": g.arr_delay_min.values,
                             "cancelled": 0, "diverted": 0})
    df = flight_days_df()
    return df[(df.airline == f["airline"]) & (df.flight_number == f["flight_number"])
              & (df.origin == f["origin"]) & (df.dest == f["dest"])].sort_values("date")


def flight_title(f):
    if f.get("flight_number"):
        return f'{f["airline"]} {f["flight_number"]}'
    return f'{f["airline"]} · {f["origin"]} → {f["dest"]}'


def flight_label(x):
    return f'{x["airline"]} {x["flight_number"]}' if x.get("flight_number") else x["airline"]


def city_of(code):
    return (lookup().get(code) or {}).get("city", code)


def month_span(first, last):
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    if a.strftime("%b %Y") == b.strftime("%b %Y"):
        return a.strftime("%b %Y")
    return a.strftime("%b") + "–" + b.strftime("%b %Y")


def track_html(f):
    r = hist_for(f)
    head = '<div class="sec2">Track record</div>'
    if not r or not r["n"]:
        return head + '<div class="muted">No past record for this flight number in our data.</div>'
    n = int(r["n"])
    items = [("On time", int(r["on_time"]), "#2C9A69"), ("Delayed", int(r["delayed"]), "#D45252"),
             ("Cancelled", int(r["cancelled"]), "#8E2A21"), ("Diverted", int(r["diverted"]), "#4A1D18")]
    tiles = "".join(
        f'<div class="st"><div class="st-k"><span class="st-bar" style="background:{c}"></span>{k}</div>'
        f'<div class="st-v">{100 * v / n:.0f}%</div><div class="st-n">{v} of {n} flights</div></div>'
        for k, v, c in items)
    seg = "".join(f'<div style="width:{100 * v / n:.2f}%;background:{c}"></div>' for k, v, c in items if v)
    ml = r["median_late"]
    extra = f" · when late, typically {int(ml)} min" if pd.notna(ml) else ""
    return (head + f'<div class="muted">What actually happened to {f["airline"]} {f["flight_number"]}'
            f'{extra}</div>'
            f'<div class="segbar">{seg}</div><div class="stats">{tiles}</div>')


def _deg(v):
    """Temperature as text; '–' when the weather service returned no value."""
    try:
        return f"{float(v):.0f}"
    except (TypeError, ValueError):
        return "–"


def wx_box(code, w):
    if not w:
        return ""
    kind = "Forecast" if w["kind"] == "forecast" else "Typical for this date (last 5 years)"
    if w["kind"] == "forecast":
        rain = f'{w["precip_mm"]:.1f} mm rain' if w["precip_mm"] else "no rain"
    else:
        rain = f'rain on {w["rain_years"]} of {w["years"]} years'
    return (f'<div class="wx-box"><div class="wx-top"><span class="wx-icon">{w["icon"]}</span><div>'
            f'<div class="wx-city">{city_of(code)} <span class="code">{code}</span></div>'
            f'<div class="wx-kind">{kind}</div></div></div>'
            f'<div class="wx-t">{_deg(w["t_max"])}° / {_deg(w["t_min"])}°C · {w["text"]}</div>'
            f'<div class="wx-s">{rain} · gusts {w["gust_kmh"]:.0f} km/h</div></div>')


def weather_html(f, wx):
    wo, wd = wx.get(f["origin"]), wx.get(f["dest"])
    if not wo and not wd:
        return ""
    return ('<div class="sec2">Weather on ' + wx["_date"].strftime("%a %d %b") + '</div>'
            '<div class="wx">' + wx_box(f["origin"], wo) + wx_box(f["dest"], wd) + '</div>'
            '<div class="muted" style="margin-top:6px">Weather data by Open-Meteo.com</div>')


def warn_html(f, wx):
    msgs = []
    for code in (f["origin"], f["dest"]):
        for m in (wx.get(code) or {}).get("warnings", []):
            msgs.append(f"{m} in {city_of(code)}")
    if not msgs:
        return ""
    return '<div class="warn">⚠️ ' + "; ".join(msgs) + ". Delays may be more likely than this estimate.</div>"


def late_odds_text(p):
    """Natural frequency for the chance of arriving 15+ min late."""
    if p is None or p <= 0:
        return ""
    if p >= 0.6:
        return f"{round(p * 10)} in 10 flights arrive 15+ min late"
    return f"1 in {max(2, round(1 / p))} flights arrive 15+ min late"


def late_odds_short(p):
    if p is None or p <= 0:
        return ""
    return f"{round(p * 10)} in 10 flights" if p >= 0.6 else f"1 in {max(2, round(1 / p))} flights"


@lru_cache(maxsize=1)
def _rotation_us():
    p = os.path.join(APP_DIR, "data", "rotation_us.csv")
    if not os.path.exists(p):
        return {}
    r = pd.read_csv(p)
    return {(str(a), int(fn), o, d, int(h)): (int(l), int(n))
            for a, fn, o, d, h, l, n in zip(r.airline, r.flight_number, r.origin, r.dest, r.dep_hhmm, r.leg, r.legs_day)}


@lru_cache(maxsize=1)
def _rotation_idx():
    d = {}
    for (a, fn, o, de, h), v in _rotation_us().items():
        d.setdefault((a, o, de), []).append((fn, h, v))
    return d


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


@lru_cache(maxsize=1)
def _rotation_hour():
    p = os.path.join(APP_DIR, "data", "rotation_us_hour.csv")
    if not os.path.exists(p):
        return {}
    r = pd.read_csv(p)
    return {(str(a), o, int(h)): (int(l), int(k)) for a, o, h, l, k in zip(r.airline, r.origin, r.hour, r.leg, r.share10)}


def rotation_text(airline, fn, origin, dest, hhmm):
    """Exact flight match first; else same airline + route with the nearest departure within 30 min."""
    try:
        fn, hhmm = int(fn or 0), int(hhmm)
    except (TypeError, ValueError):
        return ""
    v = _rotation_us().get((str(airline), fn, str(origin), str(dest), hhmm))
    if not v:
        m = hhmm // 100 * 60 + hhmm % 100
        cands = [(abs(h // 100 * 60 + h % 100 - m), f_ != fn, vv)
                 for f_, h, vv in _rotation_idx().get((str(airline), str(origin), str(dest)), [])]
        best = min(cands, key=lambda t: (t[0], t[1])) if cands else None
        v = best[2] if best and best[0] <= 30 else None
    if not v:
        h = _rotation_hour().get((str(airline), str(origin), hhmm // 100))
        if not h:
            return ""
        leg, k = h
        nm = pr.carrier_name(str(airline)) or str(airline)
        return f"{k} in 10 {nm} flights from {origin} at this hour are the plane's {_ordinal(leg)} flight of the day"
    leg, n = v
    return f"This plane's {_ordinal(leg)} flight of the day (of {n})"


def summary_html(f, wx):
    res = f["res"]
    level = res["level"]
    head, sub = verdict_text(level, f.get("region", "US"))
    sub = late_odds_text(res.get("p_late")) or sub
    rot = rotation_text(f.get("airline"), f.get("flight_number", 0), f.get("origin"), f.get("dest"), f.get("dep_hhmm", 0))
    rot_line = f'<div class="vs">{rot}</div>' if rot else ""
    return (
        f'<div class="vx"><span class="halo" style="background:{LEVEL_COLORS[level]};'
        f'box-shadow:0 0 0 6px {LEVEL_HALO[level]}"></span><div>'
        f'<div class="vh">{head}</div><div class="vs">{sub}</div>{rot_line}</div></div>'
        + warn_html(f, wx) +
        '<div class="fx-grid">'
        f'<div class="fx-box"><div class="k">Typical delay</div><div class="v">{late_minutes_text(f["m_late"])}</div></div>'
        f'<div class="fx-box"><div class="k">Climate cost of a delay</div>'
        f'<div class="v">{kg(f["co2_lo"])}–{kg(f["co2_hi"])} kg CO₂ for your seat</div></div>'
        '</div>')


def details_html(f, wx):
    return ('<div class="fx">' + summary_html(f, wx) +
            f'<a class="full-link" href="{f.get("href", "#")}" target="_self">See full breakdown →</a></div>')


def fno_html(f):
    if f.get("flight_number"):
        return f'<span class="fno">· {f["airline"]} {f["flight_number"]}</span>'
    return ""


def book_href(it, f=None):
    """'Book' button for one Ignav itinerary. Passes the card's own forecast so the booking page shows the same numbers."""
    import html
    from urllib.parse import urlencode
    if not it or not it.get("segs"):
        return ""
    s = it["segs"]
    if not all(g.get("code") and g.get("fn") for g in s):
        return ""
    legs = []
    if f is not None and f.get("res"):
        legs = [(f.get("p0"), f.get("m_late"), f["res"].get("level"), f.get("co2_lo"), f.get("co2_hi"))]
    else:
        for g in s:
            r = g.get("res")
            if not r:
                legs.append(None)
                continue
            try:
                ml = pr.typical_late_minutes(r["probs"], g.get("region") or "US")
            except Exception:
                ml = None
            c = g.get("co2")
            lo, hi = c if isinstance(c, (list, tuple)) and len(c) == 2 else (None, None)
            legs.append((r["probs"][0], ml, r.get("level"), lo, hi))

    def _v(x):
        if x is None:
            return ""
        if isinstance(x, str):
            return x
        try:
            return f"{float(x):.3f}"
        except (TypeError, ValueError):
            return ""
    fc = ";".join("" if x is None else ",".join(_v(v) for v in x) for x in legs)
    back = globals().get("_BACK") or {}
    q = urlencode({"page": "book", "o": s[0]["o"], "d": s[-1]["d"], "date": s[0]["dep"].date().isoformat(),
                   "f": ",".join(g["code"] + g["fn"] for g in s), "id": it.get("id") or "", "s": it.get("shift") or 0,
                   "bf": back.get("from", ""), "bt": back.get("to", ""), "bd": back.get("date", ""), "fc": fc})
    return f'<a class="fc-book" href="?{html.escape(q)}" target="_self">Book ↗</a>'


def card_html(f, badges, wx):
    res = f["res"]
    level = res["level"]
    sup = f"<sup>+{f['shift']}</sup>" if f["shift"] > 0 else ""
    dur = f'{f["block_min"] // 60}h {f["block_min"] % 60:02d}m'
    label = {"Low": "LOW RISK", "Moderate": "MEDIUM RISK", "High": "HIGH RISK"}[level]
    chip = (f'<span class="risk-tag" style="background:{LEVEL_HALO[level]};color:{LEVEL_TEXT[level]}">'
            f'<span class="rdot" style="background:{LEVEL_COLORS[level]}"></span>{label}</span>')
    pa = f.get("price") if isinstance(f.get("price"), dict) else {}
    try:
        amt = float(pa["amount"]) if pa.get("amount") is not None else None
    except Exception:
        amt = None
    cur = pa.get("currency") or "USD"
    price_html = (f'<div class="fc-price">{"&#36;" if cur == "USD" else cur + " "}{amt:,.0f}</div>'
                  if amt is not None else "")
    return ('<details class="fc"><summary><div class="cx-g">'
            f'<div class="cx-air"><span class="lg">{logo_html(f["airline"])}</span><span>{f["airline_name"]}</span></div>'
            f'<div class="cx-dep"><div class="fc-time">{f["dep_time"]}</div><div class="fc-code">{f["origin"]}</div></div>'
            f'<div class="cx-mid"><div class="fc-dur">{dur}</div><div class="fc-line cx-line"></div>'
            '<div class="fc-dur cx-tr">Direct</div></div>'
            f'<div class="cx-arr"><div class="fc-time">{f["arr_time"]}{sup}</div><div class="fc-code">{f["dest"]}</div></div>'
            f'<div class="cx-right">{price_html}{book_href(f.get("_ig"), f)}{chip}<div class="fc-more">Tap for details ▾</div></div>'
            '<div class="cx-tr2">Direct</div>'
            '</div></summary>' + details_html(f, wx) + '</details>')


CX_CSS = """<style>
.cx-g{display:grid;grid-template-columns:minmax(170px,1.2fr) auto minmax(150px,2fr) auto minmax(130px,1fr);
  grid-template-areas:"air dep mid arr right";align-items:center;column-gap:22px}
.cx-air{grid-area:air;display:flex;align-items:center;gap:12px;color:#111418;font-size:.98rem;line-height:1.35}
.cx-dep{grid-area:dep}
.cx-arr{grid-area:arr}
.cx-mid{grid-area:mid;text-align:center}
.cx-right{grid-area:right;text-align:right}
.cx-tr2{grid-area:tr;display:none;color:#111418;font-size:.88rem;margin-top:10px}
.cx-line{position:relative;overflow:visible}
.cx-line span{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:#FFFFFF;
  padding:0 8px;font-size:.8rem;color:#111418;font-weight:600}
.cx-pl{width:40px;height:40px;display:inline-flex;align-items:center;justify-content:center;flex:none}
.cx-pl svg{width:26px;height:26px;fill:#12284B;transform:rotate(45deg)}
@media (max-width:1000px){
  .cx-g{grid-template-columns:auto 1fr auto auto;grid-template-areas:"dep mid arr right" "tr tr tr tr" "air air air air";row-gap:4px}
  .cx-mid .cx-tr{display:none}
  .cx-tr2{display:block}
  .cx-air{margin-top:4px;font-size:.92rem;gap:8px}
  .cx-air .lg{zoom:.6}
}
.tl{margin-top:16px;border-top:1px solid #E8F1F8;padding:16px 22px 18px}
.tl-head{color:#111418;font-size:.95rem;margin-bottom:12px}
.tl-g{display:grid;grid-template-columns:64px 24px 1fr;column-gap:14px}
.tl-t{text-align:right;color:#111418;font-size:.9rem;padding:8px 0;align-self:center}
.tl-t.b{color:#111418;font-weight:700;font-size:1.05rem}
.tl-t small{display:block;font-size:.75rem;font-weight:500;color:#111418}
.tl-r{position:relative;background:linear-gradient(#C9DEEE,#C9DEEE) center/2px 100% no-repeat}
.tl-r.top{background-size:2px 50%;background-position:center bottom}
.tl-r.bot{background-size:2px 50%;background-position:center top}
.tl-r i{position:absolute;left:50%;top:50%;width:10px;height:10px;border-radius:50%;transform:translate(-50%,-50%);background:#8592A6}
.tl-r i.o{background:#FFFFFF;border:2px solid #8592A6;width:8px;height:8px}
.tl-c{padding:8px 0;align-self:center;color:#111418}
.tl-c.b{font-weight:700;font-size:1.05rem}
.tl-al{display:flex;flex-direction:column;gap:6px;padding:10px 0;color:#111418;font-size:.92rem}
.tl-ln{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.tl-op,.tl-ac{color:#111418;font-size:.88rem;padding-left:34px}
.tl-logo{zoom:.55;display:inline-flex;align-items:center}
.tl-link{color:#0055A0 !important;font-weight:600;font-size:.88rem;padding-left:34px;text-decoration:none !important}
.tl-link:hover{text-decoration:underline !important}
.tl-box{grid-row:span 2;background:#DCEAF6;border-radius:14px;padding:12px 16px;margin:6px 0;align-self:stretch}
.tl-box b{color:#111418}
.tl-box div{color:#003F7A;font-size:.88rem;margin-top:4px}
</style>"""


def conn_card_html(c, d):
    import html
    a, b, res = c["l1"], c["l2"], c["res"]
    p = c["p_miss"]
    level = "High" if p >= 0.2 else "Moderate" if p >= 0.08 else "Low"
    odds = "under 1 in 100" if p < 0.01 else f"1 in {max(2, round(1 / p))}"
    label = {"Low": "LOW RISK", "Moderate": "MEDIUM RISK", "High": "HIGH RISK"}[level]
    chip = (f'<span class="risk-tag" style="background:{LEVEL_HALO[level]};color:{LEVEL_TEXT[level]}">'
            f'<span class="rdot" style="background:{LEVEL_COLORS[level]}"></span>{label}</span>')
    plus = int(b.arr_hhmm) < int(b.dep_hhmm)
    sup = "<sup>+1</sup>" if plus else ""
    tot = int(c["total"])
    dur = f"{tot // 60}h {tot % 60:02d}m"
    lay = int(c["layover"])
    lay_txt = f"{lay // 60}h {lay % 60:02d}m"
    hub_city = html.escape(str(city_of(c["hub"]) or c["hub"]))
    tr = f'1 transit • {lay_txt} in {c["hub"]}'
    n1 = f'{c["mkt"]} {c["mkt_fn"]}'
    n2 = f"{b.airline} {int(b.flight_number)}" if b.flight_number else str(b.airline)
    name1 = html.escape(str(pr.carrier_name(c["mkt"]) or c["mkt"]))
    name2 = html.escape(str(b.airline_name if isinstance(b.airline_name, str) else (pr.carrier_name(b.airline) or b.airline)))
    if b.airline == c["mkt"]:
        air = f'<span class="lg">{logo_html(c["mkt"])}</span><span>{name1}</span>'
    else:
        air = ('<span class="lg cx-pl"><svg viewBox="0 0 24 24"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg></span>'
               f'<span>{name1} + {name2}</span>')

    def acl(fam):
        try:
            return f'<div class="tl-ln tl-ac">{html.escape(str(aircraft_name(fam)))}</div>' if isinstance(fam, str) and fam else ""
        except Exception:
            return ""

    def apt(code):
        return f"{code} - {html.escape(str(city_of(code) or code))}"

    op = (f'<div class="tl-ln tl-op">Operated by <span class="tl-logo">{logo_html(a.airline)}</span>'
          f'{html.escape(str(pr.carrier_name(a.airline)))}</div>' if c["mkt"] != a.airline else "")
    p_late = 1.0 - float(res["probs"][0])
    late = pr.typical_late_minutes(res["probs"], a.region)
    nxt = d + timedelta(days=1)
    tl = ('<div class="tl">'
          f'<div class="tl-head">{d:%a}, {d.day} {d:%b} • {dur} • 1 transit</div><div class="tl-g">'
          f'<div class="tl-t b">{a.dep_time}</div><div class="tl-r top"><i></i></div><div class="tl-c b">{apt(a.origin)}</div>'
          f'<div class="tl-t"></div><div class="tl-r"></div><div class="tl-al">'
          f'<div class="tl-ln"><span class="tl-logo">{logo_html(c["mkt"])}</span>{name1} {n1}</div>{op}{acl(a.family)}</div>'
          f'<div class="tl-t">{a.arr_time}</div><div class="tl-r"><i class="o"></i></div>'
          f'<div class="tl-box"><b>Transit {lay_txt} in {hub_city}</b>'
          f'<div>{p_late:.0%} probability to be late by about {dur_words(late)} · {odds} chance to miss the connection</div></div>'
          f'<div class="tl-t">{b.dep_time}</div><div class="tl-r"><i class="o"></i></div>'
          f'<div class="tl-t"></div><div class="tl-r"></div><div class="tl-al">'
          f'<div class="tl-ln"><span class="tl-logo">{logo_html(b.airline)}</span>{name2} {n2}</div>{acl(b.family)}</div>'
          f'<div class="tl-t b">{f"<small>{nxt.day} {nxt:%b}</small>" if plus else ""}{b.arr_time}</div>'
          f'<div class="tl-r bot"><i></i></div><div class="tl-c b">{apt(b.dest)}</div>'
          '</div></div>')
    return ('<details class="fc"><summary><div class="cx-g">'
            f'<div class="cx-air">{air}</div>'
            f'<div class="cx-dep"><div class="fc-time">{a.dep_time}</div><div class="fc-code">{a.origin}</div></div>'
            f'<div class="cx-mid"><div class="fc-dur">{dur}</div><div class="fc-line cx-line"><span>1</span></div>'
            f'<div class="fc-dur cx-tr">{tr}</div></div>'
            f'<div class="cx-arr"><div class="fc-time">{b.arr_time}{sup}</div><div class="fc-code">{b.dest}</div></div>'
            f'<div class="cx-right">{chip}<div class="fc-more">Tap for details ▾</div></div>'
            f'<div class="cx-tr2">{tr}</div>'
            '</div></summary>' + tl + '</details>')


TP_NAMES = {"bal": "Best balance", "cheap": "Cheapest", "rel": "Most reliable", "co2": "Lowest delay CO₂"}

PRICE_CSS = """<style>
details.fc, details.fc:focus, details.fc > summary:focus, details.fc > summary:focus-visible{outline:none !important;}
.tp-lab{display:none;}
.fc-price{font-weight:700;font-size:1.15rem;color:#111418;margin-bottom:6px;}.fc-book{display:inline-block;margin:0 0 6px;padding:4px 12px;border-radius:999px;background:#0055A0;color:#fff !important;font-size:.78rem;font-weight:700;text-decoration:none !important;}.fc-book:hover{background:#00447F;}
.cx-right .badge{display:inline-block;margin-bottom:6px;}
.badge.b-bal{background:#DCEAF6;color:#003F7A;}
.fx-safer{margin-top:12px;background:#DCEAF6;border-radius:14px;padding:12px 16px;text-align:center;}
.fx-safer .k{color:#003F7A;font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;}
.fx-safer .v{color:#111418;font-weight:700;margin-top:4px;}
.fx-safer .s{color:#111418;font-size:.9rem;margin-top:2px;}
</style>"""


def itin_card_html(it, d):
    import html
    segs, trs = it["segs"], it["transfers"]
    a, z, n = segs[0], segs[-1], len(it["transfers"])

    def hm(m):
        return f"{m // 60}h {m % 60:02d}m"

    def odds(p):
        return "under 1 in 100" if p < 0.01 else f"1 in {max(2, round(1 / p))}"

    def cname(s):
        nm = pr.carrier_name(s["code"])
        return str(nm) if nm and str(nm) != s["code"] else (s["op_name"] or s["code"])

    def city(code):
        return html.escape(str(city_of(code) or code))

    def apt(code):
        return f"{code} - {city(code)}"

    def tm(dt):
        return dt.strftime("%H:%M")

    def dl(dt):
        return f"<small>{dt.day} {dt:%b}</small>" if dt.date() != d else ""

    pm = it["p_miss"]
    if n:
        level = None if pm is None else ("High" if pm >= 0.2 else "Moderate" if pm >= 0.08 else "Low")
    else:
        level = a["res"]["level"] if a["res"] else None
    if level:
        label = {"Low": "LOW RISK", "Moderate": "MEDIUM RISK", "High": "HIGH RISK"}[level]
        chip = (f'<span class="risk-tag" style="background:{LEVEL_HALO[level]};color:{LEVEL_TEXT[level]}">'
                f'<span class="rdot" style="background:{LEVEL_COLORS[level]}"></span>{label}</span>')
    else:
        chip = '<span class="risk-tag" style="background:#E8F1F8;color:#111418">NO FORECAST</span>'
    days = (z["arr"].date() - a["dep"].date()).days
    sup = f"<sup>+{days}</sup>" if days > 0 else ""
    dur = hm(it["total"])
    tr = "Direct" if n == 0 else (f'{n} transit{"s" if n > 1 else ""} • '
                                  + ", ".join(f'{hm(t["layover"])} in {t["hub"]}' for t in trs))
    names = []
    for s in segs:
        if cname(s) not in names:
            names.append(cname(s))
    if len(names) == 1:
        air = f'<span class="lg">{logo_html(a["code"])}</span><span>{html.escape(names[0])}</span>'
    else:
        air = ('<span class="lg cx-pl"><svg viewBox="0 0 24 24"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 '
               '2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg></span>'
               f'<span>{html.escape(" + ".join(names))}</span>')

    def al_block(s):
        nm = cname(s)
        out = (f'<div class="tl-ln"><span class="tl-logo">{logo_html(s["code"])}</span>'
               f'{html.escape(nm)} {s["code"]}{s["fn"]}</div>')
        if s["op_name"] and s["op_name"].lower() != nm.lower():
            out += (f'<div class="tl-ln tl-op">Operated by <span class="tl-logo">{logo_html(s["op"])}</span>'
                    f'{html.escape(s["op_name"])}</div>')
        if s["aircraft"]:
            out += f'<div class="tl-ln tl-ac">{html.escape(s["aircraft"])}</div>'
        rt = ""
        if s.get("region") == "US":
            for a_ in dict.fromkeys([s.get("op"), s.get("code")]):
                if a_ and not rt:
                    rt = rotation_text(a_, s.get("fn") or 0, s["o"], s["d"], s["dep"].hour * 100 + s["dep"].minute)
        if rt:
            out += f'<div class="tl-ln tl-ac">{rt}</div>'
        q = None
        if s.get("key"):
            q = urlencode({"page": "predict", "from": s["o"], "to": s["d"],
                           "date": s["dep"].date().isoformat(), "flight": s["key"]})
        elif s.get("res") and str(s.get("fn") or "").isdigit():
            a_ = s.get("op") or s.get("code")
            q = urlencode({"page": "predict", "from": s["o"], "to": s["d"], "date": s["dep"].date().isoformat(),
                           "flight": f'{s["o"]}-{s["d"]}-{a_}-{int(s["fn"])}-{s["dep"].hour * 100 + s["dep"].minute}',
                           "leg": 1, "arr": s["arr"].hour * 100 + s["arr"].minute,
                           "blk": int((s["arr_utc"] - s["dep_utc"]).total_seconds() // 60),
                           "ac": s.get("aircraft") or "", "code": s.get("code") or ""})
        if q:
            out += f'<a class="tl-link" href="?{q}" target="_self">See full breakdown →</a>'
        return out

    def risk_line(s, t):
        if not s["res"]:
            return "No delay forecast for this flight"
        probs = s["res"]["probs"]
        late = pr.typical_late_minutes(probs, s["region"])
        return (f"{1 - float(probs[0]):.0%} probability to be late by about {dur_words(late)} · "
                f'{odds(t["p_miss"])} chance to miss the connection')

    rows = [f'<div class="tl-t b">{tm(a["dep"])}</div><div class="tl-r top"><i></i></div><div class="tl-c b">{apt(a["o"])}</div>']
    for i, s in enumerate(segs):
        rows.append(f'<div class="tl-t"></div><div class="tl-r"></div><div class="tl-al">{al_block(s)}</div>')
        if i < n:
            t, nx = trs[i], segs[i + 1]
            rows.append(f'<div class="tl-t">{dl(s["arr"])}{tm(s["arr"])}</div><div class="tl-r"><i class="o"></i></div>'
                        f'<div class="tl-box"><b>Transit {hm(t["layover"])} in {city(t["hub"])}</b><div>{risk_line(s, t)}</div></div>'
                        f'<div class="tl-t">{dl(nx["dep"])}{tm(nx["dep"])}</div><div class="tl-r"><i class="o"></i></div>')
    rows.append(f'<div class="tl-t b">{dl(z["arr"])}{tm(z["arr"])}</div><div class="tl-r bot"><i></i></div>'
                f'<div class="tl-c b">{apt(z["d"])}</div>')
    known = [s["co2"] for s in segs if s.get("co2")]
    boxes = []
    if n and pm is not None:
        boxes.append(("Chance to miss a connection", odds(pm)))
    elif not n and a["res"]:
        boxes.append(("Late arrivals", late_odds_short(1 - float(a["res"]["probs"][0]))))
        boxes.append(("Typical delay", late_minutes_text(pr.typical_late_minutes(a["res"]["probs"], a["region"]))))
    if known:
        boxes.append(("Climate cost of a delay",
                      f'{kg(sum(c[0] for c in known))}–{kg(sum(c[1] for c in known))} kg CO₂ for your seat'))
    grid = ('<div class="fx-grid" style="margin-top:14px">'
            + "".join(f'<div class="fx-box" style="text-align:center"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in boxes)
            + '</div>') if boxes else ""
    sf = it.get("_safer")
    if sf:
        sign = "+" if sf["delta"] >= 0 else "−"
        risk_t = "no connection to miss" if sf["risk"] == 0 else f'{odds(sf["risk"])} chance to miss'
        grid += (f'<div class="fx-safer"><div class="k">Safer option</div>'
                 f'<div class="v">{sign}&#36;{abs(sf["delta"]):,.0f} · {html.escape(sf["who"])} · {sf["dep"]} · '
                 f'{html.escape(sf["how"])}</div>'
                 f'<div class="s">{odds(pm)} → {risk_t}</div></div>')
    head = f'{d:%a}, {d.day} {d:%b} • {dur} • ' + ("Direct" if n == 0 else f'{n} transit{"s" if n > 1 else ""}')
    tl = f'<div class="tl"><div class="tl-head">{head}</div><div class="tl-g">' + "".join(rows) + '</div>' + grid + '</div>'
    pa = it.get("price") if isinstance(it.get("price"), dict) else {}
    try:
        amt = float(pa["amount"]) if pa.get("amount") is not None else None
    except Exception:
        amt = None
    cur = pa.get("currency") or "USD"
    price_html = (f'<div class="fc-price">{"&#36;" if cur == "USD" else cur + " "}{amt:,.0f}</div>'
                  if amt is not None else "")
    lab = f"<span>{n}</span>" if n else ""
    return ('<details class="fc"><summary><div class="cx-g">'
            f'<div class="cx-air">{air}</div>'
            f'<div class="cx-dep"><div class="fc-time">{tm(a["dep"])}</div><div class="fc-code">{a["o"]}</div></div>'
            f'<div class="cx-mid"><div class="fc-dur">{dur}</div><div class="fc-line cx-line">{lab}</div>'
            f'<div class="fc-dur cx-tr">{tr}</div></div>'
            f'<div class="cx-arr"><div class="fc-time">{tm(z["arr"])}{sup}</div><div class="fc-code">{z["d"]}</div></div>'
            f'<div class="cx-right">{price_html}{book_href(it)}{chip}<div class="fc-more">Tap for details ▾</div></div>'
            f'<div class="cx-tr2">{tr}</div>'
            '</div></summary>' + tl + '</details>')


@st.cache_data(ttl=86400, show_spinner=False)
def _au_refresh():
    """Australia (BITRE) data: download + rebuild when data.gov.au has a newer release (at most daily)."""
    from core import build_au
    return build_au.ensure_fresh().get("latest_month")


@lru_cache(maxsize=1)
def _au_network():
    """Australian airports (busiest first) and reported destinations per origin, from BITRE."""
    try:
        r = pd.read_csv(os.path.join(APP_DIR, "data", "au_routes.csv"))
    except Exception:
        return [], {}
    r = r[r.airline == "ALL"]
    order = list(r.groupby("origin").Sectors_Flown.sum().sort_values(ascending=False).index)
    dest = {o: list(g.groupby("dest").Sectors_Flown.sum().sort_values(ascending=False).index)
            for o, g in r.groupby("origin")}
    return order, dest


def render_flight():
    from core.connections import find_connections, reach_one_stop
    st.markdown(CSS, unsafe_allow_html=True)
    _au_refresh()
    if st.query_params.get("flight"):
        render_flight_page()
        return
    st.markdown('<div class="hero"><div class="hero-title">Check a flight</div></div>', unsafe_allow_html=True)

    qp = st.query_params
    sched = pr.schedule()
    au_order, au_dest = _au_network()
    origins = pr.schedule_origins()
    origins = origins + [c for c in au_order if c not in set(origins)]
    c1, c2, c3 = st.columns([2, 2, 1.2])
    with c1:
        from_val, o_codes, o_opt = airport_picker("From", origins, qp.get("from") or "ORD", key="from_pick")
    dsum = sched[sched.origin.isin(o_codes)].groupby("dest").n_flights.sum().sort_values(ascending=False)
    dests = [c for c in dsum.index if c not in o_codes]
    one = set().union(*[reach_one_stop().get(o, set()) for o in o_codes]) if o_codes else set()
    dests += sorted(c for c in one if c not in dests and c not in o_codes)
    for o in o_codes:
        dests += [c for c in au_dest.get(o, []) if c not in dests and c not in o_codes]
    _seen = set(dests)
    if not dests:
        st.info("No regular flights from here in the schedule.")
        return
    with c2:
        to_val, d_codes, d_opt = airport_picker("To", dests, qp.get("to") or None, key="to_pick", allow_empty=True)
    try:
        date_def = date.fromisoformat(qp.get("date"))
    except Exception:
        date_def = date.today() + timedelta(days=14)
    with c3:
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        d = st.date_input("Date", value=max(date_def, date.today()), min_value=date.today())
    if not d_codes:
        return   # wait until the user picks a destination

    flights = []
    for o in o_codes:
        for de in d_codes:
            if o != de:
                flights.extend(day_predictions(o, de, d.isoformat()))
    o_name = o_opt["t1"].split(",")[0] if o_opt else from_val
    d_name = d_opt["t1"].split(",")[0] if d_opt else to_val
    from core.ignav import itineraries as sold_itins
    with loading():
        conns = []
        for o in o_codes:
            for de in d_codes:
                if o != de:
                    conns.extend(sold_itins(o, de, d) or [])
    have = {(str(f["airline"]), int(f["dep_hhmm"])) for f in flights}
    ignav_ok = bool(conns)
    matched = set()
    for f in flights:
        f["price"] = None
        f["_sold"] = False
        fa = str(f["airline"])
        fm = int(f["dep_hhmm"]) // 100 * 60 + int(f["dep_hhmm"]) % 100
        best = None
        for i_, c in enumerate(conns):
            if len(c["segs"]) != 1:
                continue
            g = c["segs"][0]
            if fa not in (g["code"], g.get("op")):
                continue
            dm = abs(g["dep"].hour * 60 + g["dep"].minute - fm)
            if dm <= 10 and (best is None or dm < best[0]):
                best = (dm, i_)
        if best:
            matched.add(best[1])
            f["_sold"] = True
            f["_ig"] = conns[best[1]]
            if isinstance(conns[best[1]].get("price"), dict):
                f["price"] = conns[best[1]]["price"]
    conns = [c for i_, c in enumerate(conns) if i_ not in matched]
    if ignav_ok:   # show only what is actually sold; schedule-only cards are a fallback when Ignav is down
        flights = [f for f in flights if f.get("_sold")]
    INF = float("inf")

    def _amt(x):
        p = x.get("price")
        try:
            return float(p["amount"]) if isinstance(p, dict) and p.get("amount") is not None else None
        except Exception:
            return None

    def _risk(x):
        """Chance the trip does not go to plan: arrive >15 min late, or miss a connection."""
        if "segs" in x:
            if any(not g.get("res") for g in x["segs"]):
                return None
            late_last = 1 - float(x["segs"][-1]["res"]["probs"][0])
            if not x["transfers"]:
                return late_last
            pm = x.get("p_miss")
            if pm is None:
                return None
            return pm + (1 - pm) * late_last
        r = x.get("res")
        return None if not r else 1 - float(r["probs"][0])

    def _mins(x):
        return x["total"] if "segs" in x else x.get("block_min")

    def _dep(x):
        if "segs" in x:
            return x["segs"][0]["dep"].hour * 100 + x["segs"][0]["dep"].minute
        return int(x["dep_hhmm"])

    def _co2(x):
        known = [s["co2"] for s in x["segs"] if s.get("co2")]
        return sum((lo + hi) / 2 for lo, hi in known) if known else INF

    for x in flights + conns:
        x["_best"] = False
    cand = [x for x in flights + conns if _amt(x) is not None and _risk(x) is not None and _mins(x)]
    if len(cand) >= 3:
        P, R, M = [_amt(x) for x in cand], [_risk(x) for x in cand], [_mins(x) for x in cand]

        def _n(v, vals):
            lo, hi = min(vals), max(vals)
            return 0.0 if hi == lo else (v - lo) / (hi - lo)
        min(cand, key=lambda x: _n(_amt(x), P) + _n(_risk(x), R) + _n(_mins(x), M))["_best"] = True

    def _hmtxt(m):
        return f"{m // 60}h {m % 60:02d}m"

    def _who(x):
        if "segs" not in x:
            return str(x.get("airline_name") or x["airline"])
        out = []
        for g in x["segs"]:
            nm = pr.carrier_name(g["code"])
            nm = str(nm) if nm and str(nm) != g["code"] else (g["op_name"] or g["code"])
            if nm not in out:
                out.append(nm)
        return " + ".join(out)

    def _how(x):
        if "segs" not in x or not x["transfers"]:
            return "Direct"
        n_ = len(x["transfers"])
        return (f'{n_} transit{"s" if n_ > 1 else ""}, '
                + ", ".join(f'{_hmtxt(t["layover"])} in {t["hub"]}' for t in x["transfers"]))

    def _deptxt(x):
        if "segs" in x:
            return f'{x["segs"][0]["dep"]:%H:%M}'
        v = int(x["dep_hhmm"])
        return f"{v // 100:02d}:{v % 100:02d}"

    for c in conns:
        c["_safer"] = None
        pm_ = c.get("p_miss") if c["transfers"] else None
        pc = _amt(c)
        if pm_ is None or pm_ < 0.05 or pc is None:
            continue
        pick = None
        for x in flights + conns:
            if x is c or _amt(x) is None:
                continue
            if "segs" in x and x["transfers"]:
                if x.get("p_miss") is None or x["p_miss"] > pm_ / 2:
                    continue
                rm = x["p_miss"]
            else:
                rm = 0.0
            if _amt(x) - pc > 200:
                continue
            k_ = (_amt(x), rm)
            if pick is None or k_ < pick[0]:
                pick = (k_, x)
        if pick:
            (pa_, rm), x = pick
            c["_safer"] = {"delta": pa_ - pc, "who": _who(x), "dep": _deptxt(x), "how": _how(x), "risk": rm}
    import datetime as _dt
    FDEF = {"sort": "Departure time", "stops": [], "airlines": [], "dep": (0, 1439), "arr": (0, 1439), "price": None, "maxdur": None}
    SORT_LABEL = {"Departure time": "Earliest departure", "Cheapest": "Lowest price", "Most reliable": "Most reliable",
                  "Shortest": "Shortest duration", "Lowest delay CO₂": "Lowest delay CO₂"}
    STOP_OPTS = ["Direct", "1 transit", "2+ transits"]
    _sig = (tuple(o_codes), tuple(d_codes), d.isoformat())
    if st.session_state.get("flt_sig") != _sig:
        for _k in [k for k in st.session_state.keys() if str(k).startswith("fd_")]:
            del st.session_state[_k]
        st.session_state.flt = dict(FDEF)
        st.session_state.flt_sig = _sig
    _F = dict(FDEF, **st.session_state.get("flt", {}))

    def _stops(x):
        return len(x["transfers"]) if "segs" in x else 0

    def _hm(t):
        return t.hour * 60 + t.minute

    def _depm(x):
        if "segs" in x:
            return _hm(x["segs"][0]["dep"])
        v = int(x["dep_hhmm"])
        return v // 100 * 60 + v % 100

    def _arrm(x):
        if "segs" in x:
            return _hm(x["segs"][-1]["arr"])
        try:
            h_, m_ = str(x.get("arr_time") or "").split(":")[:2]
            return int(h_) * 60 + int(m_[:2])
        except Exception:
            return None

    def _airl(x):
        if "segs" not in x:
            return {str(x.get("airline_name") or pr.carrier_name(x["airline"]) or x["airline"])}
        out = set()
        for g in x["segs"]:
            nm = pr.carrier_name(g["code"])
            out.add(str(nm) if nm and str(nm) != g["code"] else (g["op_name"] or g["code"]))
        return out

    def _pass(x, F):
        k = _stops(x)
        if F["stops"] and ("Direct" if k == 0 else "1 transit" if k == 1 else "2+ transits") not in F["stops"]:
            return False
        if not (F["dep"][0] <= _depm(x) <= F["dep"][1]):
            return False
        a_ = _arrm(x)
        if a_ is not None and not (F["arr"][0] <= a_ <= F["arr"][1]):
            return False
        if F["airlines"] and not (_airl(x) & set(F["airlines"])):
            return False
        if F["price"]:
            p_ = _amt(x)
            if p_ is None or not (F["price"][0] <= p_ <= F["price"][1]):
                return False
        if F.get("maxdur") and (_mins(x) or 0) > F["maxdur"]:
            return False
        return True

    pool = flights + conns

    def _t(m):
        return _dt.time(m // 60, m % 60)

    def _tt(m):
        return f"{m // 60:02d}:{m % 60:02d}"

    def _dur_txt(m):
        return f"{m // 60}h {m % 60:02d}m"

    def _n_active(F):
        return sum([bool(F["stops"]), bool(F["airlines"]), tuple(F["dep"]) != FDEF["dep"],
                    tuple(F["arr"]) != FDEF["arr"], bool(F["price"]), bool(F.get("maxdur"))])

    def _draft():
        if "fdraft" not in st.session_state:
            st.session_state.fdraft = dict(_F)
        return st.session_state.fdraft

    def _hrow(title, val=""):
        return f'<div class="fs-hr"><span class="fs-h">{title}</span><span class="fs-v">{val}</span></div>'

    def _ends(a, b):
        return f'<div class="fs-ends"><span>{a}</span><span>{b}</span></div>'

    @st.dialog("Filter & Sort", width="large")
    def _fs_dialog():
        import html as _html
        ss = st.session_state
        D = _draft()
        st.markdown("""<style>
div[role="dialog"]{background:#FFFFFF !important;max-width:880px !important;}
.st-key-fs_band{background:#EAF2F8;border-radius:18px;padding:14px;}
.fs-nav{background:#FFFFFF;border-radius:16px;padding:10px 8px;display:flex;flex-direction:column;gap:2px;}
.fs-nl{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:10px;font-size:.95rem;
  color:#111418 !important;text-decoration:none !important;transition:background .15s;}
.fs-nl:hover{background:#EEF4FA;}
.fs-nl.on{background:#DCEAF6;color:#003F7A !important;font-weight:700;}
.fs-nl i{width:7px;height:7px;border-radius:50%;background:#0055A0;display:inline-block;}
.st-key-fs_scroll{max-height:max(240px, calc(100vh - 350px));overflow-y:auto;gap:12px;padding-right:2px;}
[class*="st-key-fs_c_"]{background:#FFFFFF;border-radius:16px;padding:18px 22px 12px;flex-shrink:0;}
.fs-hr{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 8px;}
.fs-h{font-weight:700;font-size:1.05rem;color:#111418;}
.fs-v{font-weight:700;font-size:.92rem;color:#111418;white-space:nowrap;}
.fs-sub-h{font-weight:600;font-size:.95rem;color:#111418;margin-top:6px;}
.fs-ticks{display:flex;justify-content:space-between;color:#111418;font-size:.8rem;margin:-10px 0 14px;}
.st-key-fs_c_sort [data-testid="stRadio"],.st-key-fs_c_sort [role="radiogroup"]{width:100%;}
.st-key-fs_c_sort label[data-baseweb="radio"]{flex-direction:row-reverse;justify-content:space-between;
  width:100%;padding:9px 0;margin:0;cursor:pointer;}
.st-key-fs_c_sort label[data-baseweb="radio"] p{color:#111418;font-size:.98rem;}
.st-key-fs_c_transit [data-testid="stButtonGroup"],.st-key-fs_c_transit [data-testid="stButtonGroup"] > div{width:100%;}
.st-key-fs_c_transit [data-testid="stButtonGroup"] > div{display:flex;gap:10px;flex-wrap:nowrap;}
.st-key-fs_c_transit [data-testid="stButtonGroup"] button{flex:1 1 0;justify-content:center;min-height:42px;border-radius:999px;}
div[role="dialog"] div[role="slider"]{width:22px !important;height:22px !important;background:#fff !important;
  border:1px solid #D3DCE6 !important;box-shadow:0 1px 5px rgba(18,40,75,.22) !important;}
div[role="dialog"] [data-testid="stSliderThumbValue"],div[role="dialog"] [data-testid="stSliderTickBar"]{display:none;}
.fs-al{font-weight:600;color:#111418;line-height:1.25;}
.fs-sub{color:#111418;font-size:.84rem;}
.fs-logo{zoom:.8;}
div[role="dialog"] button[kind="tertiary"] p{color:#0055A0;font-weight:700;}
div[role="dialog"] .stElementContainer:has(iframe){display:none;}
.st-key-fs_foot{border-top:1px solid #E5E9EF;padding-top:14px;}
.st-key-w_reset button{background:#DCEAF6;border:none;min-height:48px;}
.st-key-w_reset button p{color:#003F7A;font-weight:700;}
.st-key-w_apply button{min-height:48px;}
.st-key-w_apply button p{font-weight:700;}
@media (max-width:900px){
  .st-key-fs_band{background:transparent;padding:0;}
  .st-key-fs_band [data-testid="stHorizontalBlock"]:has(.fs-nav){flex-direction:column;gap:0;align-items:stretch !important;}
  .st-key-fs_band [data-testid="stHorizontalBlock"]:has(.fs-nav) > [data-testid="stColumn"]{width:100% !important;
    flex:0 0 auto !important;min-width:100% !important;height:auto !important;}
  .st-key-fs_band [data-testid="stHorizontalBlock"]:has(.fs-nav) > [data-testid="stColumn"] [data-testid="stVerticalBlock"]{
    justify-content:flex-start !important;}
  .fs-nav{flex-direction:row;overflow-x:auto;border-radius:0;padding:0 4px;gap:6px;
    border-bottom:1px solid #E5E9EF;scrollbar-width:none;}
  .fs-nav::-webkit-scrollbar{display:none;}
  .fs-nl{border-radius:0;padding:12px 8px;white-space:nowrap;border-bottom:3px solid transparent;}
  .fs-nl:hover{background:transparent;}
  .fs-nl.on{background:transparent;border-bottom-color:#0055A0;}
  .st-key-fs_scroll{background:#EAF2F8;padding:12px;border-radius:0 0 16px 16px;
    max-height:max(220px, calc(100vh - 380px));}
  [class*="st-key-fs_c_"]{padding:14px 16px 10px;}
}
[class*="st-key-fs_c_"] [data-testid="stHorizontalBlock"]{flex-direction:row !important;flex-wrap:nowrap !important;
  align-items:center !important;gap:12px;}
[class*="st-key-fs_c_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{min-width:0 !important;
  width:auto !important;flex:0 0 auto !important;}
[class*="st-key-fs_c_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){flex:1 1 auto !important;}
.st-key-fs_c_transit [data-testid="stButtonGroup"] div:has(> button){display:flex !important;flex-wrap:nowrap !important;
  gap:10px;width:100%;}
.st-key-fs_c_transit [data-testid="stButtonGroup"] button{flex:1 1 0 !important;min-width:0 !important;max-width:none !important;}
.st-key-fs_c_transit [data-testid="stButtonGroup"] button p,
.st-key-fs_c_transit [data-testid="stButtonGroup"] button div{white-space:nowrap !important;overflow:visible !important;
  text-overflow:clip !important;max-width:none !important;}
.st-key-fs_c_sort [role="radiogroup"] > *{width:100% !important;}
.st-key-fs_c_sort label[data-baseweb="radio"]{display:flex !important;width:100% !important;}
.fs-nl:focus,.fs-nl:focus-visible{outline:none !important;box-shadow:none !important;}
.st-key-fs_c_sort [role="radiogroup"]{align-items:stretch !important;}
@media (min-width:901px){
  .st-key-fs_band [data-testid="stHorizontalBlock"]:has(.fs-nav){align-items:center !important;}
}
@media (max-width:900px){
  .fs-nav{background:#FFFFFF;position:relative;z-index:5;}
  .st-key-fs_scroll{position:relative;z-index:1;overflow-y:auto !important;}
}
</style>""", unsafe_allow_html=True)

        def _seg_name(g):
            nm = pr.carrier_name(g["code"])
            return str(nm) if nm and str(nm) != g["code"] else (g["op_name"] or g["code"])

        def _ticks(labels):
            return '<div class="fs-ticks">' + "".join(f"<span>{x}</span>" for x in labels) + "</div>"

        al = {}
        for x in pool:
            pairs = ([(_seg_name(g), g["code"]) for g in x["segs"]] if "segs" in x
                     else [(next(iter(_airl(x))), str(x["airline"]))])
            seen = set()
            for nm, cd in pairs:
                if nm in seen:
                    continue
                seen.add(nm)
                r = al.setdefault(nm, {"code": cd, "n": 0, "min": None})
                r["n"] += 1
                a_ = _amt(x)
                if a_ is not None and (r["min"] is None or a_ < r["min"]):
                    r["min"] = a_
        al_names = sorted(al, key=lambda k: (-al[k]["n"], k))
        prices = [v for v in (_amt(x) for x in pool) if v is not None]
        pmin, pmax = (int(min(prices)), int(max(prices)) + 1) if prices else (0, 0)
        durs = [v for v in (_mins(x) for x in pool) if v]
        dmin, dmax = (min(durs), max(durs)) if durs else (0, 0)

        act = {"Sort": False, "Transit": bool(D["stops"]),
               "Time": tuple(D["dep"]) != FDEF["dep"] or tuple(D["arr"]) != FDEF["arr"],
               "Airlines": bool(D["airlines"]), "Duration": bool(D.get("maxdur")), "Price": bool(D["price"])}
        secs = [x for x in ["Sort", "Transit", "Time", "Airlines", "Duration", "Price"]
                if not (x == "Price" and not prices) and not (x == "Duration" and dmax <= dmin)
                and not (x == "Airlines" and not al)]

        with st.container(key="fs_band"):
            cn, cc = st.columns([1, 3], gap="small")
            with cn:
                links = "".join(f'<a class="fs-nl" data-t="fs-{x.lower()}" href="#fs-{x.lower()}" target="_self">{x}'
                                f'{"<i></i>" if act[x] else ""}</a>' for x in secs)
                st.markdown(f'<div class="fs-nav">{links}</div>', unsafe_allow_html=True)
            with cc:
                with st.container(key="fs_scroll"):
                    for sec in secs:
                        with st.container(key=f"fs_c_{sec.lower()}"):
                            st.markdown(f'<div id="fs-{sec.lower()}" class="fs-anchor"></div>', unsafe_allow_html=True)
                            if sec == "Sort":
                                ss.w_sort = D["sort"]

                                def _cb_sort():
                                    D["sort"] = ss.w_sort
                                st.markdown(_hrow("Sort by"), unsafe_allow_html=True)
                                st.radio("Sort by", list(SORT_LABEL), format_func=SORT_LABEL.get, key="w_sort",
                                         on_change=_cb_sort, label_visibility="collapsed")
                            elif sec == "Transit":
                                ss.w_stops = list(D["stops"])

                                def _cb_st():
                                    D["stops"] = list(ss.w_stops or [])
                                st.markdown(_hrow("Transit"), unsafe_allow_html=True)
                                st.pills("Transit", STOP_OPTS, selection_mode="multi", key="w_stops",
                                         on_change=_cb_st, label_visibility="collapsed")
                            elif sec == "Time":
                                def _cb_time(fld):
                                    v = ss["w_" + fld]
                                    D[fld] = (_hm(v[0]), _hm(v[1]))
                                st.markdown(_hrow("Time"), unsafe_allow_html=True)
                                for fld, lab in (("dep", "Departure time"), ("arr", "Arrival time")):
                                    ss["w_" + fld] = (_t(D[fld][0]), _t(D[fld][1]))
                                    st.markdown(f'<div class="fs-hr"><span class="fs-sub-h">{lab}</span>'
                                                f'<span class="fs-v">{_tt(D[fld][0])} – {_tt(D[fld][1])}</span></div>',
                                                unsafe_allow_html=True)
                                    st.slider(lab, min_value=_dt.time(0, 0), max_value=_dt.time(23, 59),
                                              step=_dt.timedelta(minutes=30), format="HH:mm", key="w_" + fld,
                                              on_change=_cb_time, args=(fld,), label_visibility="collapsed")
                                    st.markdown(_ticks(["00:00", "06:00", "12:00", "18:00", "23:59"]),
                                                unsafe_allow_html=True)
                            elif sec == "Airlines":
                                def _cb_al(nm):
                                    on = ss["w_al_" + nm]
                                    D["airlines"] = [a_ for a_ in D["airlines"] if a_ != nm] + ([nm] if on else [])
                                st.markdown(_hrow("Airlines"), unsafe_allow_html=True)
                                show_all = ss.get("w_al_showall", False)
                                for nm in (al_names if show_all else al_names[:5]):
                                    r = al[nm]
                                    ss["w_al_" + nm] = nm in D["airlines"]
                                    c1, c2, c3 = st.columns([0.8, 5, 0.6], vertical_alignment="center")
                                    c1.markdown(f'<div class="fs-logo">{logo_html(r["code"])}</div>',
                                                unsafe_allow_html=True)
                                    sub = f'From &#36;{r["min"]:,.0f}' if r["min"] is not None else ""
                                    c2.markdown(f'<div class="fs-al">{_html.escape(nm)} ({r["n"]})</div>'
                                                f'<div class="fs-sub">{sub}</div>', unsafe_allow_html=True)
                                    c3.checkbox(nm, key="w_al_" + nm, on_change=_cb_al, args=(nm,),
                                                label_visibility="collapsed")
                                if len(al_names) > 5:
                                    st.button("Show less" if show_all else f"Show {len(al_names) - 5} more",
                                              type="tertiary", key="w_al_more",
                                              on_click=lambda: ss.update(w_al_showall=not show_all))
                            elif sec == "Duration":
                                cur = D.get("maxdur") or dmax
                                ss.w_dur = cur

                                def _cb_dur():
                                    D["maxdur"] = None if ss.w_dur >= dmax else ss.w_dur
                                st.markdown(_hrow("Travel duration", f"{_dur_txt(dmin)} – {_dur_txt(cur)}"),
                                            unsafe_allow_html=True)
                                st.slider("Travel duration", min_value=dmin, max_value=dmax, step=1, key="w_dur",
                                          on_change=_cb_dur, label_visibility="collapsed")
                                st.markdown(_ticks([_dur_txt(dmin), _dur_txt(dmax)]), unsafe_allow_html=True)
                            elif sec == "Price":
                                cur = tuple(D["price"]) if D["price"] else (pmin, pmax)
                                cut = [pmin + (pmax - pmin) * i // 3 for i in range(4)]
                                presets = ["\\$" + f"{cut[i]:,} – " + "\\$" + f"{cut[i + 1]:,}" for i in range(3)]
                                ss.w_price = cur
                                ss.w_pp = next((presets[i] for i in range(3) if cur == (cut[i], cut[i + 1])), None)

                                def _cb_price():
                                    v = tuple(ss.w_price)
                                    D["price"] = None if v == (pmin, pmax) else v

                                def _cb_pp():
                                    v = ss.w_pp
                                    D["price"] = ((cut[presets.index(v)], cut[presets.index(v) + 1])
                                                  if v in presets else None)
                                st.markdown(_hrow("Price", f"&#36;{cur[0]:,} – &#36;{cur[1]:,}"),
                                            unsafe_allow_html=True)
                                st.slider("Price", min_value=pmin, max_value=pmax, step=1, key="w_price",
                                          on_change=_cb_price, label_visibility="collapsed")
                                st.markdown(_ticks([f"&#36;{pmin:,}", f"&#36;{pmax:,}"]), unsafe_allow_html=True)
                                st.pills("Price range", presets, selection_mode="single", key="w_pp",
                                         on_change=_cb_pp, label_visibility="collapsed")

        def _p(v):
            return "\\$" + f"{v:,}"
        chips = [(x, "stops", x) for x in D["stops"]] + [(a_, "airlines", a_) for a_ in D["airlines"]]
        if tuple(D["dep"]) != FDEF["dep"]:
            chips.append((f"Departs {_tt(D['dep'][0])}–{_tt(D['dep'][1])}", "dep", None))
        if tuple(D["arr"]) != FDEF["arr"]:
            chips.append((f"Arrives {_tt(D['arr'][0])}–{_tt(D['arr'][1])}", "arr", None))
        if D.get("maxdur"):
            chips.append((f"Up to {_dur_txt(D['maxdur'])}", "maxdur", None))
        if D["price"]:
            chips.append((f"{_p(D['price'][0])} – {_p(D['price'][1])}", "price", None))

        def _rm(fld, val):
            if fld in ("stops", "airlines"):
                D[fld] = [v for v in D[fld] if v != val]
            elif fld in ("dep", "arr"):
                D[fld] = FDEF[fld]
            else:
                D[fld] = None

        with st.container(key="fs_foot"):
            if chips:
                with st.container(key="fs_chips", horizontal=True):
                    for i, (lab, fld, val) in enumerate(chips):
                        st.button(lab, icon=":material/close:", key=f"w_chip_{i}", on_click=_rm, args=(fld, val))
            n_ok = sum(_pass(x, D) for x in pool)
            fb1, fb2 = st.columns([1, 2])
            fb1.button("Reset", use_container_width=True, key="w_reset",
                       on_click=lambda: ss.update(fdraft=dict(FDEF)))
            if fb2.button(f"See {n_ok} flights", type="primary", use_container_width=True, key="w_apply"):
                ss.flt = dict(D)
                st.rerun()
        import streamlit.components.v1 as _cv1
        _cv1.html("""<script>
const d = window.parent.document;
function bind(){
  const sc = d.querySelector('.st-key-fs_scroll');
  const links = Array.from(d.querySelectorAll('.fs-nl'));
  if (!sc || !links.length || links[0].dataset.fsb === '1') return;
  let last = null;
  const upd = () => {
    const top = sc.getBoundingClientRect().top;
    let cur = links[0];
    links.forEach(a => {
      const t = d.getElementById(a.dataset.t);
      if (t && t.getBoundingClientRect().top - top <= 48) cur = a;
    });
    if (sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 4) cur = links[links.length - 1];
    links.forEach(a => a.classList.toggle('on', a === cur));
    if (cur !== last) { cur.scrollIntoView({block: 'nearest', inline: 'nearest'}); last = cur; }
  };
  links.forEach(a => {
    a.dataset.fsb = '1';
    a.onclick = e => {
      e.preventDefault();
      const t = d.getElementById(a.dataset.t);
      if (t) sc.scrollTo({top: sc.scrollTop + t.getBoundingClientRect().top - sc.getBoundingClientRect().top - 6,
                          behavior: 'smooth'});
    };
  });
  sc.onscroll = upd;
  upd();
}
setInterval(bind, 250);
</script>""", height=0)

    if not flights and not conns:
        st.info(f"No regular flights from {o_name} to {d_name} on a {d.strftime('%A')}.")
        return

    wx = {"_date": d}
    with loading():
        for c in {f["origin"] for f in flights} | {f["dest"] for f in flights}:
            wx[c] = get_weather(c, d.isoformat())

    base = {"page": "predict", "from": from_val, "to": to_val, "date": d.isoformat()}
    globals()["_BACK"] = base
    for f in flights:
        f["href"] = "?" + urlencode(dict(base, flight=f["key"]))
    best_rel = min(flights, key=lambda f: (f["exp_delay"], f["dep_hhmm"])) if flights else None
    best_co2 = min(flights, key=lambda f: (f["exp_co2"], f["dep_hhmm"])) if flights else None

    def badges_for(f):
        return []

    top = []
    n_act = _n_active(_F)
    st.markdown("""<style>
.st-key-fs_bar{margin:4px 0 12px;flex-wrap:wrap;gap:10px;}
.st-key-fs_bar > div{width:auto !important;flex:0 0 auto !important;}
.st-key-fs_bar button{border-radius:999px;border:1px solid #D3DCE6;background:#FFFFFF;color:#111418;
  min-height:38px;padding:0 18px;box-shadow:none;}
.st-key-fs_bar button p{font-weight:500;font-size:.92rem;white-space:nowrap;}
.st-key-fs_bar button:hover{border-color:#0055A0;background:#EEF4FA;color:#111418;}
.st-key-fs_bar button:focus:not(:active){border-color:#0055A0;color:#111418;box-shadow:none;}
.st-key-fs_bar span[data-testid="stIconMaterial"]{color:#003F7A;}
div[role="dialog"]{background:#F3F8FB;}
.st-key-fs_nav{background:#FFFFFF;border-radius:16px;padding:10px 6px;}
.st-key-fs_nav [role="radiogroup"]{gap:2px;}
.st-key-fs_nav label[data-baseweb="radio"]{padding:9px 14px;border-radius:10px;width:100%;margin:0;cursor:pointer;}
.st-key-fs_nav label[data-baseweb="radio"] > div:first-child{display:none;}
.st-key-fs_nav label[data-baseweb="radio"] p{color:#111418;}
.st-key-fs_nav label[data-baseweb="radio"]:has(input:checked){background:#DCEAF6;}
.st-key-fs_nav label[data-baseweb="radio"]:has(input:checked) p{color:#003F7A;font-weight:700;}
.st-key-fs_body{background:#FFFFFF;border-radius:16px;padding:18px 20px;min-height:340px;}
.fs-hr{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:4px 0 4px;}
.fs-h{font-weight:700;font-size:1.02rem;color:#111418;}
.fs-v{font-weight:700;font-size:.92rem;color:#111418;white-space:nowrap;}
.fs-ends{display:flex;justify-content:space-between;color:#111418;font-size:.82rem;margin:-8px 0 16px;}
.fs-al{font-weight:600;color:#111418;line-height:1.25;}
.fs-sub{color:#111418;font-size:.84rem;}
.fs-logo{zoom:.8;}
div[role="dialog"] [data-testid="stSliderThumbValue"],
div[role="dialog"] [data-testid="stSliderTickBar"]{display:none;}
.st-key-fs_chips{flex-wrap:wrap;gap:8px;margin:6px 0 4px;}
.st-key-fs_chips > div{width:auto !important;flex:0 0 auto !important;}
.st-key-fs_chips button{border-radius:999px;border:1px solid #0055A0;background:#DCEAF6;color:#003F7A;
  min-height:32px;padding:0 12px;}
.st-key-fs_chips button p{font-size:.85rem;white-space:nowrap;}
@media (max-width: 640px){
  .st-key-fs_nav [role="radiogroup"]{flex-direction:row;flex-wrap:wrap;}
  .st-key-fs_nav label[data-baseweb="radio"]{width:auto;padding:7px 12px;}
  .st-key-fs_body{min-height:0;padding:14px;}
}
</style>""", unsafe_allow_html=True)

    def _cb_qsort():
        st.session_state.flt = dict(_F, sort=st.session_state.q_sort)
    st.session_state.q_sort = _F["sort"]
    with st.container(key="fs_bar", horizontal=True):
        o1 = st.button("Filter" + (f" · {n_act}" if n_act else ""), icon=":material/tune:", key="fs_open1")
        with st.popover(SORT_LABEL[_F["sort"]], icon=":material/swap_vert:"):
            st.radio("Sort by", list(SORT_LABEL), format_func=SORT_LABEL.get, key="q_sort",
                     on_change=_cb_qsort, label_visibility="collapsed")
    if o1:
        st.session_state.fdraft = dict(_F)
        _fs_dialog()
    _pool = [x for x in flights + conns if _pass(x, _F)]
    for x in flights + conns:
        x["_picks"] = []
    if len(_pool) >= 3:
        def _first(cands, key):
            cands = [x for x in cands if key(x) is not None]
            return min(cands, key=lambda x: (key(x), _dep(x))) if cands else None
        co2c = [x for x in _pool if "segs" in x and _co2(x) < INF]
        picks = (("bal", next((x for x in _pool if x.get("_best")), None)),
                 ("cheap", _first(_pool, _amt)),
                 ("co2", _first(co2c, _co2) if co2c
                  else _first([x for x in _pool if "segs" not in x], lambda x: x.get("exp_co2"))))
        for tag, x in picks:
            if x is not None:
                x["_picks"].append(tag)
                if all(x is not t for t in top):
                    top.append(x)
    if top:
        st.markdown('<div class="sec">Top picks</div><div class="fc-list">'
                    + "".join('<div class="tp-item"><div class="tp-lab">' + " · ".join(TP_NAMES[t] for t in x.get("_picks", []))
                              + '</div>' + (itin_card_html(x, d) if "segs" in x else card_html(x, [], wx)) + '</div>'
                              for x in top) + '</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec">All flights</div>', unsafe_allow_html=True)

    items = [("f", f) for f in flights if all(f is not t for t in top)] + [("c", c) for c in conns if all(c is not t for t in top)]
    items = [it for it in items if _pass(it[1], _F)]
    sort = _F["sort"]
    if not top and not items:
        st.markdown('<div class="sec">No flights match these filters</div>', unsafe_allow_html=True)
    if sort == "Cheapest":
        items.sort(key=lambda it: (_amt(it[1]) if _amt(it[1]) is not None else INF, _dep(it[1])))
    elif sort == "Shortest":
        items.sort(key=lambda it: (_mins(it[1]) or INF, _dep(it[1])))
    elif sort == "Lowest delay CO₂":
        items.sort(key=lambda it: (0, it[1]["exp_co2"], _dep(it[1])) if it[0] == "f"
                   else (1, _co2(it[1]), _dep(it[1])))
    elif sort == "Most reliable":
        items.sort(key=lambda it: (0, it[1]["exp_delay"], int(it[1]["dep_hhmm"])) if it[0] == "f"
                   else (1, it[1]["p_miss"] if it[1]["p_miss"] is not None else 1.0,
                         it[1]["segs"][0]["dep"].hour * 100 + it[1]["segs"][0]["dep"].minute))
    else:
        items.sort(key=lambda it: int(it[1]["dep_hhmm"]) if it[0] == "f" else it[1]["segs"][0]["dep"].hour * 100 + it[1]["segs"][0]["dep"].minute)
    st.markdown(PRICE_CSS, unsafe_allow_html=True)
    st.markdown(CX_CSS + '<div class="fc-list">'
                + "".join(card_html(x, badges_for(x), wx) if k == "f" else itin_card_html(x, d) for k, x in items)
                + '</div>', unsafe_allow_html=True)


# ======================= full flight page =======================
def risk_tag(level):
    label = {"Low": "LOW RISK", "Moderate": "MEDIUM RISK", "High": "HIGH RISK"}[level]
    return (f'<span class="risk-tag" style="background:{LEVEL_HALO[level]};color:{LEVEL_TEXT[level]}">'
            f'<span class="rdot" style="background:{LEVEL_COLORS[level]}"></span>{label}</span>')


@lru_cache(maxsize=1)
def flight_days_df():
    return pd.read_csv(os.path.join(APP_DIR, "data", "flight_days.csv"))


@lru_cache(maxsize=1)
def hourly_df():
    return pd.read_csv(os.path.join(APP_DIR, "data", "hourly.csv"))


def pg(inner):
    return f'<div class="pg-card">{inner}</div>' if inner else ""


def header_html(f, d):
    level = f["res"]["level"]
    dur = f'{f["block_min"] // 60}h {f["block_min"] % 60:02d}m'
    sup = f"<sup>+{f['shift']}</sup>" if f["shift"] > 0 else ""
    return (
        '<div class="h-row">'
        f'<div class="h-logo">{logo_html(f["airline"])}</div>'
        f'<div><div class="pg-title">{flight_title(f)}</div>'
        f'<div class="pg-sub">{f["airline_name"]} · {aircraft_name(f["family"])}</div></div>'
        f'<div style="margin-left:auto">{risk_tag(level)}</div></div>'
        '<div class="fc-top" style="margin-top:18px">'
        f'<div class="fc-end"><div class="fc-time">{f["dep_time"]}</div><div class="fc-code">{city_of(f["origin"])} · {f["origin"]}</div></div>'
        f'<div class="fc-mid"><div class="fc-dur">{dur}</div><div class="fc-line"></div><div class="fc-dur">Direct</div></div>'
        f'<div class="fc-end"><div class="fc-time">{f["arr_time"]}{sup}</div><div class="fc-code">{city_of(f["dest"])} · {f["dest"]}</div></div>'
        '</div>'
        f'<div class="pg-sub" style="margin-top:10px">{d.strftime("%A %d %B %Y")}</div>')


def forecast_html(f, route, d):
    res = f["res"]
    probs, prior = res["probs"], res["prior"]
    bar = "".join(f'<div style="width:{100 * p:.2f}%;background:{c}"></div>' for p, c in zip(probs, BAND_COLORS))
    rows = "".join(
        f'<div class="band-row"><span><span class="sw" style="background:{BAND_COLORS[k]}"></span>{name}</span>'
        f'<span><b>{pct(probs[k])}</b><span class="avg">average US flight {pct(prior[k])}</span></span></div>'
        for k, name in enumerate(BAND_NAMES))
    rank = 1 + sum(1 for x in route if x["exp_delay"] < f["exp_delay"])
    return ('<div class="sec2" style="margin-top:0">Delay forecast</div>'
            f'<div class="muted">Ranks #{rank} of {len(route)} flights on this route on {d.strftime("%a %d %b")} '
            f'for least expected delay.</div><div class="bandbar">{bar}</div>{rows}')


def timeline_html(f):
    g = days_for(f)
    if g.empty:
        return ""
    n = len(g)
    W, base, scale = 1000, 150, 0.6
    step = (W - 60) / n
    bw = step * 0.62
    bars, labels = [], []
    for i, r in enumerate(g.itertuples()):
        x = 40 + i * step + (step - bw) / 2
        day = date.fromisoformat(r.date)
        dl = day.strftime("%a %d %b")
        if r.cancelled:
            h, c, tip = 120, "#8E2A21", f"{dl}: cancelled"
        elif r.diverted:
            h, c, tip = 120, "#4A1D18", f"{dl}: diverted"
        else:
            m = 0.0 if pd.isna(r.arr_delay) else float(r.arr_delay)
            h = max(6, min(m, 200) * scale)
            c = "#D45252" if m > 15 else "#2C9A69"
            tip = f"{dl}: {abs(m):.0f} min {'late' if m >= 0 else 'early'}"
        bars.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="{c}"><title>{tip}</title></rect>')
        if i % max(1, n // 5) == 0 or i == n - 1:
            labels.append(f'<text x="{x + bw / 2:.1f}" y="{base + 20}" font-size="13" fill="#8592A6" '
                          f'text-anchor="middle" font-family="Plus Jakarta Sans,sans-serif">{day.strftime("%d %b")}</text>')
    y15 = base - 15 * scale
    grid = (f'<line x1="40" y1="{base}" x2="{W - 20}" y2="{base}" stroke="#C9DEEE"/>'
            f'<line x1="40" y1="{y15:.1f}" x2="{W - 20}" y2="{y15:.1f}" stroke="#C9DEEE" stroke-dasharray="4 4"/>'
            f'<text x="{W - 20}" y="{y15 - 6:.1f}" font-size="12" fill="#8592A6" text-anchor="end" '
            'font-family="Plus Jakarta Sans,sans-serif">15 min late</text>')
    svg = (f'<svg viewBox="0 0 {W} {base + 30}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;margin-top:8px">'
           + grid + "".join(bars) + "".join(labels) + '</svg>')
    return (f'<div class="sec2">Last {n} flights</div><div class="muted">One bar per day: green = on time, '
            'red = more than 15 min late (taller = later), dark = cancelled or diverted. Hover for details.</div>' + svg)


def avg_txt(v):
    return "on time" if v < 1 else f"{v:.0f} min late"


def hour_html(f, d):
    h = hourly_df()
    a = h[h.airport == f["origin"]]
    if a.empty:
        return ""
    m = a[a.Month == d.month]
    if m.empty:
        m = a
    m = m.assign(w=m.n * m.avg_dep_delay)
    prof = m.groupby("hour").agg(n=("n", "sum"), w=("w", "sum"))
    prof = prof[prof.n >= 30]
    if prof.empty:
        return ""
    prof["avg"] = prof.w / prof.n
    day_avg = prof.w.sum() / prof.n.sum()
    hr = f["dep_hhmm"] // 100
    hours = list(range(int(prof.index.min()), int(prof.index.max()) + 1))
    W, base = 1000, 140
    mx = max(float(prof["avg"].max()), 1.0)
    step = (W - 60) / len(hours)
    bw = step * 0.6
    bars, labels = [], []
    for i, hh in enumerate(hours):
        val = float(prof.loc[hh, "avg"]) if hh in prof.index else 0.0
        hgt = max(3.0, val / mx * 110) if val > 0 else 3.0
        x = 40 + i * step + (step - bw) / 2
        c = "#0055A0" if hh == hr else "#C9DEEE"
        bars.append(f'<rect x="{x:.1f}" y="{base - hgt:.1f}" width="{bw:.1f}" height="{hgt:.1f}" rx="3" fill="{c}">'
                    f'<title>{hh:02d}:00 · average {avg_txt(val)}</title></rect>')
        if hh % 3 == 0:
            labels.append(f'<text x="{x + bw / 2:.1f}" y="{base + 20}" font-size="13" fill="#8592A6" '
                          f'text-anchor="middle" font-family="Plus Jakarta Sans,sans-serif">{hh:02d}:00</text>')
    svg = (f'<svg viewBox="0 0 {W} {base + 30}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;margin-top:8px">'
           f'<line x1="40" y1="{base}" x2="{W - 20}" y2="{base}" stroke="#C9DEEE"/>' + "".join(bars) + "".join(labels) + '</svg>')
    v_hr = float(prof.loc[hr, "avg"]) if hr in prof.index else day_avg
    city = city_of(f["origin"])
    text = (f"Around {hr:02d}:00, departures from {city} in {d.strftime('%B')} are on average {avg_txt(v_hr)}, "
            f"compared with {avg_txt(day_avg)} across the whole day (BTS 2023–2025).")
    link = f'<a class="full-link" href="?airport={f["origin"]}" target="_self">{city} airport page →</a>'
    return (f'<div class="sec2" style="margin-top:0">{f["origin"]} departures through the day</div>'
            f'<div class="muted">{text}</div>' + svg + link)


def alternatives_html(f, route):
    if f["res"]["level"] == "Low":
        return ""
    alts = sorted([x for x in route if x["exp_delay"] < 0.85 * f["exp_delay"]], key=lambda x: x["exp_delay"])[:3]
    if not alts:
        return ""
    rows = "".join(
        f'<a class="alt-row" href="{x["href"]}" target="_self">{logo_html(x["airline"])}'
        f'<b>{x["dep_time"]}</b><span>{x["airline_name"]} {x["flight_number"]}</span>'
        f'<span style="margin-left:auto">{risk_tag(x["res"]["level"])}</span></a>' for x in alts)
    return ('<div class="sec2" style="margin-top:0">More reliable flights on this route</div>'
            '<div class="muted">Same day, same route, lower delay risk.</div>' + rows)


def method_html(f):
    return ('<div class="sec2" style="margin-top:0">How this is calculated</div><div class="co2note">'
            'The delay forecast comes from a gradient-boosting model trained on 3 million US flights (2023–2024) '
            'and tested on Jan–Mar 2025 (AUC 0.60; predicted and observed delay shares agree within about 1 point). '
            'It uses only what is known when a flight is scheduled (route, airline, aircraft, day, month and hour): '
            'no live tracking and no weather. The risk level combines how often the flight is late and how late it '
            'typically is (expected delay), compared with the average US flight. '
            'Typical delay is the expected delay if the flight is more than 15 minutes late: the model estimate, '
            'blended with this flight’s own delays in Feb–Mar 2025 (the more often it was late, the more its own '
            'history counts). '
            'CO₂ range: low = waiting at the gate with engines off (auxiliary power unit only); high = engines idling '
            'for the whole delay (ICAO idle fuel flow), shared over a typical number of seats. '
            'Schedule and track record: BTS on-time data, Feb–Mar 2025. Weather: Open-Meteo.com.</div>')


PAGE_CSS = """
<style>
div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-pgc_"]){align-items:stretch !important;}
div[data-testid="stColumn"]:has(div[class*="st-key-pgc_"]) > div,
div[data-testid="stColumn"]:has(div[class*="st-key-pgs_"]) > div{height:100%;}
div[class*="st-key-pgc_"]{background:#FFFFFF;border-radius:22px;padding:22px 24px;box-shadow:0 1px 2px rgba(11,31,51,.05);height:100%;}
div[class*="st-key-pgs_"]{height:100%;}
.ct{display:flex;align-items:center;gap:10px;font-size:1.25rem;font-weight:700;color:#111418;}
.ct svg{width:22px;height:22px;color:#111418;}
.cs{color:#111418;font-size:.85rem;margin-top:2px;}
.stats4{display:flex;gap:12px;margin-top:16px;}
.s4{flex:1;min-width:0;}
.s4-l{display:flex;align-items:center;gap:6px;color:#111418;font-size:.85rem;font-weight:600;white-space:nowrap;}
.vb{width:4px;height:15px;border-radius:2px;display:inline-block;flex:none;}
.s4-v{font-size:2.1rem;font-weight:700;color:#111418;letter-spacing:-.03em;line-height:1.15;margin-top:2px;}
.s4-c{color:#111418;font-size:.85rem;font-weight:600;}
.seg{display:flex;gap:4px;height:8px;margin:14px 0 4px 0;}
.seg div{border-radius:999px;}
.sub-h{color:#111418;font-size:1rem;font-weight:600;margin:18px 0 0 0;}
.status{border-radius:22px;overflow:hidden;height:100%;display:flex;flex-direction:column;}
.st-body{padding:22px 24px 4px 24px;flex:1;}
.st-title{display:flex;align-items:center;gap:12px;font-size:1.3rem;font-weight:700;color:#111418;}
.st-dot{width:12px;height:12px;border-radius:50%;flex:none;}
.st-row{display:flex;gap:14px;padding:13px 0;border-bottom:1px solid rgba(11,31,51,.08);}
.st-row:last-child{border-bottom:none;}
.st-ic{width:22px;flex:none;color:#111418;padding-top:1px;}
.st-ic svg{width:21px;height:21px;}
.st-k{font-weight:700;color:#111418;font-size:.98rem;}
.st-v{color:#111418;font-size:.92rem;margin-top:1px;}
.st-foot{padding:14px 24px;font-weight:700;font-size:.95rem;}
.st-foot a{text-decoration:none !important;}
.fc-top2{display:flex;gap:36px;flex-wrap:wrap;margin-top:14px;align-items:flex-start;}
.big{font-size:2.8rem;font-weight:700;color:#111418;letter-spacing:-.03em;line-height:1;}
.big-l{color:#111418;font-size:.95rem;font-weight:600;margin-top:4px;}
.fcl{flex:1;min-width:240px;}
.fl-row{display:flex;align-items:center;gap:9px;padding:4px 0;font-size:.95rem;color:#111418;font-weight:600;}
.fl-row .p{margin-left:auto;font-weight:700;}
.fl-row .a{width:74px;text-align:right;color:#111418;font-weight:600;}
.lists2{display:flex;gap:32px;flex-wrap:wrap;margin-top:6px;}
.lists2 > div{flex:1;min-width:280px;}
.hb-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:18px 0 4px 0;}
.hb-t{font-size:1.05rem;font-weight:700;color:#111418;}
.hb-s{color:#111418;font-size:.8rem;}
a.hb-row{display:flex;align-items:center;gap:10px;padding:5px 0;text-decoration:none !important;color:#111418 !important;position:relative;}
a.hb-row.dim{opacity:.4;}
a.hb-row:hover{opacity:1;}
.hb-row .logo{width:22px;height:22px;}
.hb-row .al{width:22px;height:22px;font-size:.55rem;}
.hb-lab{width:112px;flex:none;font-weight:700;font-size:.9rem;}
.hb-lab span{display:block;color:#111418;font-weight:500;font-size:.75rem;}
.hb-track{flex:1;height:18px;background:#E9F1F7;border-radius:999px;}
.hb-bar{height:100%;border-radius:999px;}
.hb-val{width:44px;text-align:right;color:#111418;font-weight:700;font-size:.9rem;}
.hb-tip{display:none;position:absolute;left:146px;bottom:30px;background:#0B0F14;color:#fff;border-radius:10px;padding:9px 13px;
  font-size:.85rem;z-index:5;white-space:nowrap;box-shadow:0 8px 24px rgba(0,0,0,.25);}
.hb-tip b{display:block;font-size:.92rem;margin-bottom:2px;}
a.hb-row:hover .hb-tip{display:block;}
.wr{display:flex;align-items:center;gap:14px;padding:14px 0;border-bottom:1px solid #E8F1F8;}
.wr:last-of-type{border-bottom:none;}
.wr-ic{font-size:2.4rem;line-height:1;}
.wr-main{flex:1;min-width:0;}
.wr-city{font-weight:700;color:#111418;font-size:.98rem;}
.wr-kind{color:#111418;font-size:.78rem;}
.wr-t{font-size:2.2rem;font-weight:700;color:#111418;letter-spacing:-.03em;line-height:1;}
.wr-t sup{font-size:1rem;}
.wr-c{color:#111418;font-weight:600;font-size:.88rem;text-align:right;}
.wr-m{color:#111418;font-size:.82rem;font-weight:600;margin-top:4px;}
.ticks{display:flex;gap:2px;margin-top:5px;}
.ticks i{width:3px;height:10px;border-radius:2px;display:inline-block;}
.warn2{background:#FFF4DB;color:#8A5A00;border-radius:12px;padding:9px 12px;margin-top:10px;font-weight:600;font-size:.9rem;}
#vg-tooltip-element{background:#0B0F14 !important;color:#fff !important;border:none !important;border-radius:10px !important;
  padding:10px 14px !important;font-family:Plus Jakarta Sans,sans-serif !important;font-size:14px !important;box-shadow:0 8px 24px rgba(0,0,0,.25) !important;}
#vg-tooltip-element table tr td.key{color:#8CC1E9 !important;}
#vg-tooltip-element table tr td.value{color:#fff !important;font-weight:600 !important;}
.tr-big{font-size:2.3rem;font-weight:700;color:#2F7D4F;letter-spacing:-.03em;line-height:1;margin-top:14px;}
.tr-sub{font-size:.42em;vertical-align:baseline;margin-left:2px;letter-spacing:0;}
.tr-l{color:#111418;font-size:.9rem;font-weight:600;margin-top:4px;}
.tr-row{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #E8F1F8;color:#111418;font-size:.92rem;}
.tr-row:last-of-type{border-bottom:none;}
.tr-ic{font-size:1.15rem;width:24px;flex:none;}
.ct{font-size:1.15rem;}
.ct svg{width:20px;height:20px;}
.stats4{display:grid;grid-template-columns:repeat(auto-fit,minmax(74px,1fr));gap:10px 12px;}
.s4-l{font-size:.8rem;overflow:hidden;text-overflow:ellipsis;}
.s4-v{font-size:1.75rem;white-space:nowrap;}
.s4-c{font-size:.78rem;}
.big{font-size:2.3rem;}
.st-title{font-size:1.15rem;}
.st-k{font-size:.92rem;}
.st-v{font-size:.88rem;}
.wr-t{font-size:1.8rem;}
.hb-t{white-space:nowrap;}
@media (max-width:1200px){
  div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-pgc_"]){flex-wrap:wrap !important;}
  div[data-testid="stColumn"]:has(div[class*="st-key-pgc_"]),
  div[data-testid="stColumn"]:has(div[class*="st-key-pgs_"]){flex:1 1 calc(50% - 1rem) !important;min-width:calc(50% - 1rem) !important;}
}
@media (max-width:800px){
  div[data-testid="stColumn"]:has(div[class*="st-key-pgc_"]),
  div[data-testid="stColumn"]:has(div[class*="st-key-pgs_"]){flex:1 1 100% !important;min-width:100% !important;}
}

/* spotlight: hover one row/card, the rest fade */
.hb-row{transition:opacity .25s ease;}
div:has(> .hb-row:hover) > .hb-row:not(:hover){opacity:.3;}
</style>
"""

IC_UP = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.5 19h19v2h-19zM22.07 9.64c-.21-.8-1.04-1.28-1.84-1.06L14.92 10 8 3.57l-1.93.51 4.14 7.17-4.97 1.33-1.97-1.54-1.45.39 2.59 4.49 16.6-4.45c.81-.23 1.28-1.05 1.06-1.83z"/></svg>'
IC_DOWN = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.5 19h19v2h-19zM9.68 13.27l4.35 1.16 5.31 1.42c.8.21 1.62-.26 1.84-1.06.21-.8-.26-1.62-1.06-1.84l-5.31-1.42-2.76-9.02L10.12 2v8.28L5.15 8.95l-.93-2.32-1.45-.39v5.17l1.6.43 5.31 1.43z"/></svg>'
IC_CLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
IC_LEAF = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l.95-2.3c.48.17.98.3 1.34.3C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.5s1.75 3.75 1.75 3.75C7 8 17 8 17 8z"/></svg>'
IC_CLOUD = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z"/></svg>'
IC_GAUGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 12l4.5-3.5"/><path d="M7 15h.01M12 6.5h.01M17 15h.01"/></svg>'
IC_THERM = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 14.76V4a2 2 0 0 0-4 0v10.76a4 4 0 1 0 4 0z"/></svg>'

RISK_TITLE = {"Low": "Low delay risk", "Moderate": "Medium delay risk", "High": "High delay risk"}
TINT = {"Low": ("#EEF8F1", "#E0F0E5", "#3E9A5D", "#1F7A52"),
        "Moderate": ("#FFF8E6", "#F5EAD0", "#E8963A", "#9A5B00"),
        "High": ("#FDEEEC", "#F5DCD8", "#D2483A", "#9B2C21")}


def sev(m, t1, t2):
    return "#3E9A5D" if m < t1 else ("#E8963A" if m < t2 else "#D2483A")


def dur_words(m):
    m = int(round(m))
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d} min"


def y_axis():
    return alt.Axis(orient="right", title=None, gridDash=[3, 3], gridColor="#D5DEE8", domain=False, ticks=False,
                    labelColor="#8592A6", labelFontSize=12, labelPadding=6, tickCount=3,
                    labelExpr="datum.value >= 60 && datum.value % 60 == 0 ? (datum.value / 60) + 'h' : datum.value + 'm'")


def x_axis(values=None):
    kw = {"values": values} if values else {}
    return alt.Axis(**kw, title=None, labelAngle=0, labelColor="#8592A6", labelFontSize=12, ticks=False,
                    domainColor="#D5DEE8", labelOverlap="greedy", labelPadding=6)


def status_card(f, wx, list_href):
    level = f["res"]["level"]
    bg, foot, dot, link = TINT[level]
    head, sub = verdict_text(level, f.get("region", "US"))
    rows = [(IC_UP, "Delay chance", f"{in_ten(f['p0'])} flights like this arrive on time."),
            (IC_CLOCK, "Typical delay", f"Typically {dur_words(f['m_late'])}."),
            (IC_LEAF, "Climate cost of a delay", f"{kg(f['co2_lo'])}–{kg(f['co2_hi'])} kg CO₂ for your seat.")]
    parts = [f"{wx[c]['text']} in {city_of(c)}" for c in (f["origin"], f["dest"]) if wx.get(c)]
    if parts:
        txt = ", ".join(parts) + "."
        warns = [f"{m} in {city_of(c)}" for c in (f["origin"], f["dest"]) for m in (wx.get(c) or {}).get("warnings", [])]
        if warns:
            txt += " ⚠️ " + "; ".join(warns) + "."
        rows.append((IC_CLOUD, "Weather", txt))
    body = "".join(f'<div class="st-row"><div class="st-ic">{ic}</div><div><div class="st-k">{k}</div>'
                   f'<div class="st-v">{val}</div></div></div>' for ic, k, val in rows)
    return (f'<div class="status" style="background:{bg}"><div class="st-body">'
            f'<div class="st-title"><span class="st-dot" style="background:{dot};box-shadow:0 0 0 5px {foot}"></span>'
            f'{RISK_TITLE[level]}</div>{body}</div>'
            f'<div class="st-foot" style="background:{foot}"><a href="{list_href}" target="_self" style="color:{link}">'
            'Compare all flights on this route ›</a></div></div>')


def hb_row(href, logo, label, sub, width, color, value, tip, dim):
    return (f'<a class="hb-row{" dim" if dim else ""}" href="{href}" target="_self"><div class="hb-tip">{tip}</div>'
            f'{logo}<div class="hb-lab">{label}<span>{sub}</span></div>'
            f'<div class="hb-track"><div class="hb-bar" style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="hb-val">{value}</div></a>')


def forecast_card(f, route, list_href):
    probs, prior = f["res"]["probs"], f["res"]["prior"]
    rows = "".join(
        f'<div class="fl-row"><span class="vb" style="background:{BAND_COLORS[k]}"></span>{name}'
        f'<span class="p">{pct(probs[k])}</span><span class="a">avg {pct(prior[k])}</span></div>'
        for k, name in enumerate(BAND_NAMES))
    seg = "".join(f'<div style="width:{100 * p:.2f}%;background:{c}"></div>' for p, c in zip(probs, BAND_COLORS) if p > 0.002)

    shown = sorted(route, key=lambda x: x["m_late"])[:8]
    if all(x is not f for x in shown):
        shown = shown[:7] + [f]
    mx = max(x["m_late"] for x in shown) or 1.0
    flights = "".join(
        hb_row(x["href"], logo_html(x["airline"]), flight_label(x),
               f'{x["dep_time"]} → {x["arr_time"]}', 6 + 94 * x["m_late"] / mx,
               LEVEL_COLORS[x["res"]["level"]], f'{x["m_late"]:.0f} min',
               f'<b>{x["airline_name"]} {x["flight_number"] or x["dep_time"]}</b>Predicted delay: about {dur_words(x["m_late"])}', x is not f)
        for x in shown)

    by_air = {}
    for x in route:
        by_air.setdefault(x["airline"], []).append(x)
    stats = sorted(((a, sum(x["m_late"] for x in xs) / len(xs), len(xs),
                     sum(x["exp_delay"] for x in xs) / len(xs), xs[0]["airline_name"])
                    for a, xs in by_air.items()), key=lambda t: t[1])[:6]
    amx = max(t[1] for t in stats) or 1.0
    airlines = "".join(
        hb_row(list_href, logo_html(a), a, f"{n} flight{'s' if n > 1 else ''}", 6 + 94 * m / amx,
               LEVEL_COLORS[pr.risk_level(r)], f"{m:.0f} min",
               f"<b>{name}</b>Predicted delay: about {dur_words(m)} on average · {n} flight{'s' if n > 1 else ''}",
               a != f["airline"])
        for a, m, n, r, name in stats)

    return (f'<div class="ct">{IC_GAUGE} Delay forecast</div>'
            '<div class="fc-top2">'
            f'<div><div class="big">{pct(probs[0])}</div><div class="big-l">chance of arriving on time</div></div>'
            f'<div class="fcl">{rows}</div></div><div class="seg">{seg}</div>'
            '<div class="lists2">'
            '<div><div class="hb-h"><span class="hb-t">Flights on this route</span>'
            '</div>' + flights + '</div>'
            '<div><div class="hb-h"><span class="hb-t">Airlines on this route</span>'
            '</div>' + airlines + '</div></div>')


@lru_cache(maxsize=1)
def _route_hist_us():
    agg = {}
    for (a, fn, o, d), r in history().items():
        x = agg.setdefault((a, o, d), {"n": 0, "on_time": 0, "delayed": 0, "cancelled": 0, "diverted": 0})
        for c in x:
            try:
                x[c] += int(r[c] or 0)
            except (KeyError, TypeError, ValueError):
                pass
    return agg


@lru_cache(maxsize=1)
def _route_hist_eu():
    h, _ = eu_hist()
    g = (h.assign(late=h.arr_delay_min > 15)
          .groupby(["airline_icao", "origin_icao", "dest_icao"]).late.agg(["size", "sum"]))
    return {k: {"n": int(v["size"]), "on_time": int(v["size"] - v["sum"]), "delayed": int(v["sum"]),
                "cancelled": 0, "diverted": 0} for k, v in g.iterrows()}


def _route_hist_au(airline, o, d):
    import os
    try:
        r = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "au_routes.csv"))
    except Exception:
        return None
    r = r[(r.origin == o) & (r.dest == d) & (r.airline == airline)]
    if r.empty:
        return None
    r = r[r.ym > r.ym.max() - 100]
    n, flown, can = int(r.Sectors_Scheduled.sum()), int(r.Sectors_Flown.sum()), int(r.Cancellations.sum())
    if not n:
        return None
    return {"n": n, "on_time": int(r.Arrivals_On_Time.sum()), "delayed": int(r.Arrivals_Delayed.sum()),
            "cancelled": can, "diverted": max(0, n - flown - can)}


def route_hist(f):
    """Track record of the same airline on the same route (all its flight numbers / services)."""
    if f.get("au"):
        return _route_hist_au(f["airline"], f["origin"], f["dest"])
    if f.get("region") != "EU":
        return _route_hist_us().get((f["airline"], f["origin"], f["dest"]))
    svc = f.get("svc")
    return _route_hist_eu().get(tuple(svc[:3])) if svc else None


def track_card(f):
    r = hist_for(f)
    title = f'<div class="ct">{IC_DOWN} Track record</div>'
    fallback = False
    if not r or not r["n"]:
        r = route_hist(f)
        if not r or not r["n"]:
            return title + '<div class="cs">No past record for this flight number in our data.</div>'
        fallback = True
    n = int(r["n"])
    items = [("On time", int(r["on_time"]), "#3E9A5D"), ("Delayed", int(r["delayed"]), "#D2483A"),
             ("Cancelled", int(r["cancelled"]), "#8E2A21"), ("Diverted", int(r["diverted"]), "#4A1D18")]
    if f.get("region") == "EU" and not f.get("au"):
        items = items[:2]
    stats = "".join(
        f'<div class="s4"><div class="s4-l"><span class="vb" style="background:{c}"></span>{k}</div>'
        f'<div class="s4-v">{100 * cnt / n:.0f}%</div></div>' for k, cnt, c in items)
    seg = "".join(f'<div style="width:{100 * cnt / n:.2f}%;background:{c}"></div>' for k, cnt, c in items if cnt)
    return (title + f'<div class="stats4">{stats}</div>'
            + ("" if fallback else '<div class="sub-h">Arrival delay per flight</div>'))


def timeline_chart(f):
    g = days_for(f)
    if g.empty:
        return None
    rows = []
    multi_year = len({str(x)[:4] for x in g.date}) > 1
    for r in g.itertuples():
        day = date.fromisoformat(r.date)
        base = {"day": day.strftime("%d %b %y" if multi_year else "%d %b"), "date": day.strftime("%a %d %b %Y")}
        if r.cancelled or r.diverted:
            rows.append(dict(base, v=60.0, c="#7A2A22", detail="Cancelled" if r.cancelled else "Diverted"))
            continue
        m = 0.0 if pd.isna(r.arr_delay) else float(r.arr_delay)
        rows.append(dict(base, v=max(m, 1.5), c=sev(max(m, 0.0), 15.01, 45),
                         detail=f"{abs(m):.0f} min {'late' if m >= 0 else 'early'}"))
    cdf = pd.DataFrame(rows)
    ymax = max(60.0, float(cdf.v.max()) * 1.12)
    ch = alt.Chart(cdf).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("day:N", sort=None, scale=alt.Scale(paddingInner=0.3), axis=x_axis(cdf.day.tolist()[::max(1, -(-len(cdf) // 4))])),
        y=alt.Y("v:Q", scale=alt.Scale(domain=[0, ymax]), axis=y_axis()),
        color=alt.Color("c:N", scale=None),
        tooltip=[alt.Tooltip("date:N", title="Flight"), alt.Tooltip("detail:N", title="Arrival")])
    return ch.properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)


def ticks(val, maxv):
    n = 24
    on = int(round(min(max(val, 0) / maxv, 1) * n))
    out = ""
    for i in range(n):
        col = ("#4A90D9" if i < 9 else ("#3E9A5D" if i < 16 else "#E8963A")) if i < on else "#DDE3EA"
        out += f'<i style="background:{col}"></i>'
    return f'<div class="ticks">{out}</div>'


def weather_card(f, wx):
    rows, warns = "", []
    for code in (f["origin"], f["dest"]):
        w = wx.get(code)
        if not w:
            continue
        kind = "Forecast" if w["kind"] == "forecast" else "Typical for this date"
        rain = (f'{(w["precip_mm"] or 0):.1f} mm rain' if w["kind"] == "forecast"
                else f'rain {w["rain_years"]}/{w["years"]} yrs')
        gust = w["gust_kmh"] or 0
        rows += (f'<div class="wr"><div class="wr-ic">{w["icon"]}</div><div class="wr-main">'
                 f'<div class="wr-city">{city_of(code)} <span class="code">{code}</span></div>'
                 f'<div class="wr-kind">{kind}</div>'
                 f'<div class="wr-m">Low {_deg(w["t_min"])}° · {rain} · gusts {gust:.0f} km/h</div>{ticks(gust, 80)}</div>'
                 f'<div><div class="wr-t">{_deg(w["t_max"])}<sup>°C</sup></div><div class="wr-c">{w["text"]}</div></div></div>')
        warns += [f"{m} in {city_of(code)}" for m in w.get("warnings", [])]
    if not rows:
        return ""
    warn = "".join(f'<div class="warn2">⚠️ {m}</div>' for m in warns)
    return (f'<div class="ct">{IC_THERM} Weather</div><div class="cs">{wx["_date"].strftime("%a %d %b")}</div>'
            f'{rows}{warn}<div class="cs" style="margin-top:8px">Weather data by Open-Meteo.com</div>')


@lru_cache(maxsize=1)
def hourly_eu_df():
    return pd.read_csv(os.path.join(APP_DIR, "data", "hourly_eu.csv"))


def eu_hourly_local(icao, iata):
    """hourly_eu.csv hours are UTC (EUROCONTROL) -> shift to local time at the airport,
    using the UTC offset in the middle of each sampled month (handles summer time)."""
    h = hourly_eu_df()
    a = h[h.airport == icao].copy()
    if a.empty:
        return a
    tz = ZoneInfo((lookup().get(iata) or {}).get("tz") or "UTC")
    off = {(y, mo): int(datetime(int(y), int(mo), 15, 12, tzinfo=tz).utcoffset().total_seconds() // 3600)
           for y, mo in a[["Year", "Month"]].drop_duplicates().itertuples(index=False)}
    a["hour"] = [(int(hr) + off[(y, mo)]) % 24 for y, mo, hr in zip(a.Year, a.Month, a.hour)]
    return a


def _au_intl_month(code):
    """International departures per day by calendar month for one AU airport (BITRE Table 4, latest 12 months)."""
    import calendar, os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "bitre_intl", "au_intl_departures.csv")
    try:
        t = pd.read_csv(p)
    except Exception:
        return {}
    t = t[t.month.isin(sorted(t.month.unique())[-12:]) & (t.iata == code)]
    out = {}
    for ym, v in zip(t.month, t.intl_departures):
        y, mo = int(ym[:4]), int(ym[5:7])
        out[mo] = float(v) / calendar.monthrange(y, mo)[1]
    return out


def _airport_card_au(f, d):
    import calendar, os
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    try:
        a = pd.read_csv(os.path.join(root, "monthly_au.csv"))
        r = pd.read_csv(os.path.join(root, "au_routes.csv"))
    except Exception:
        return "", None, ""
    a = a[(a.airport == f["origin"]) & (a.n_dep > 0)].copy()
    if a.empty:
        return "", None, ""
    a["days"] = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(a.Year, a.Month)]
    m = a[a.Month == d.month]
    if m.empty:
        m = a
    per_day = float((m.n_dep / m.days).mean())
    intl = _au_intl_month(f["origin"])
    per_day += intl.get(d.month, 0.0)
    ont = float((m.pct_dep_ontime * m.n_dep).sum() / m.n_dep.sum())
    r = r[(r.origin == f["origin"]) & (r.airline == "ALL")]
    rm = r[r.Month_Num == d.month] if (r.Month_Num == d.month).any() else r
    sch = float(rm.Sectors_Scheduled.sum())
    cells = [("#0055A0", "Departures", f"{per_day:.0f}", "per day"),
             ("#3E9A5D", "On time", f"{100 * ont:.0f}%", "of departures")]
    if sch and f.get("au"):
        cells.append(("#8E2A21", "Cancelled", f"{100 * float(rm.Cancellations.sum()) / sch:.1f}%", "of departures"))
    stats = '<div class="stats4">' + "".join(
        f'<div class="s4"><div class="s4-l"><span class="vb" style="background:{c}"></span>{k}</div>'
        f'<div class="s4-v">{v}</div><div class="s4-c">{sub}</div></div>' for c, k, v, sub in cells) + '</div>'
    city = city_of(f["origin"])
    if not f.get("au"):
        t = a.assign(pdy=a.n_dep / a.days).groupby("Month").pdy.mean().reset_index()
        t["pdy"] = t.pdy + t.Month.map(lambda x: intl.get(int(x), 0.0))
        t["mo"] = t.Month.map(lambda x: calendar.month_abbr[int(x)])
        t["c"] = ["#0055A0" if int(x) == d.month else "#C9DEEE" for x in t.Month]
        t = t[t.Month <= date.today().month]
        t["txt"] = t.pdy.map(lambda x: f"{x:.0f} per day")
        order = list(calendar.month_abbr[1:])
        ch = alt.Chart(t).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("mo:N", sort=order, scale=alt.Scale(domain=order, paddingInner=0.3), axis=x_axis()),
            y=alt.Y("pdy:Q", axis=alt.Axis(orient="right", title=None, gridDash=[3, 3], gridColor="#D5DEE8", domain=False, ticks=False, labelColor="#8592A6", labelFontSize=12, tickCount=3)),
            color=alt.Color("c:N", scale=None),
            tooltip=[alt.Tooltip("mo:N", title="Month"), alt.Tooltip("txt:N", title="Departures")]
        ).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)
        return (f'<div class="ct">{IC_UP} {city} departures</div>' + stats
                + '<div class="sub-h">Departures per day by month</div>', ch, "")
    top = f'<div class="ct">{IC_UP} {city} departures</div>' + stats + '<div class="sub-h">On-time departures by month</div>'
    g = a.assign(w=a.pct_dep_ontime * a.n_dep).groupby("Month").agg(w=("w", "sum"), n=("n_dep", "sum")).reset_index()
    g["v"] = 100 * g.w / g.n
    g["mo"] = g.Month.map(lambda x: calendar.month_abbr[int(x)])
    g["c"] = ["#0055A0" if int(x) == d.month else "#C9DEEE" for x in g.Month]
    g = g[g.Month <= date.today().month]
    g["txt"] = g.v.map(lambda x: f"{x:.0f}% on time")
    order = list(calendar.month_abbr[1:])
    chart = alt.Chart(g).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("mo:N", sort=order, scale=alt.Scale(domain=order, paddingInner=0.3), axis=x_axis(order[::3])),
        y=alt.Y("v:Q", scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(orient="right", title=None, gridDash=[3, 3], gridColor="#D5DEE8", domain=False,
                              ticks=False, labelColor="#8592A6", labelFontSize=12, tickCount=3,
                              labelExpr="datum.value + '%'")),
        color=alt.Color("c:N", scale=None),
        tooltip=[alt.Tooltip("mo:N", title="Month"), alt.Tooltip("txt:N", title="Departures")]
    ).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)
    link = f'<a class="full-link" href="?airport={f["origin"]}" target="_self">{city} airport page →</a>'
    return top, chart, link


def airport_card(f, d):
    if f.get("au") or f.get("region") == "AU":
        return _airport_card_au(f, d)
    if f.get("region") == "EU":
        a = eu_hourly_local(f["svc"][1], f["origin"])
        month = pr.EU_MONTH_MAP[d.month]
    else:
        h = hourly_df()
        a = h[h.airport == f["origin"]]
        month = d.month
    if a.empty:
        return "", None, ""
    m = a[a.Month == month]
    if m.empty:
        m = a
    months = max(m[["Year", "Month"]].drop_duplicates().shape[0], 1)
    m = m.assign(w=m.n * m.avg_dep_delay)
    prof = m.groupby("hour").agg(n=("n", "sum"), w=("w", "sum")).reset_index()
    prof = prof[prof.n >= 30].copy()
    if prof.empty:
        return "", None, ""
    prof["delay"] = (prof.w / prof.n).clip(lower=0)
    prof["per_day"] = prof.n / (months * 30.4)
    prof["hour_label"] = prof.hour.map(lambda x: f"{int(x):02d}:00")
    prof["c"] = "#C9DEEE"
    _bi, _wi = prof.delay.idxmin(), prof.delay.idxmax()
    prof.loc[_bi, "c"] = "#2C9A69"
    if _wi != _bi:
        prof.loc[_wi, "c"] = "#D45252"
    _b, _w = prof.loc[_bi], prof.loc[_wi]
    _cs = "border-radius:999px;padding:4px 11px;font-size:.78rem;font-weight:700;white-space:nowrap"
    _chips = ('<div style="display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 6px">'
              f'<span style="background:#DDF3E8;color:#1F7A52;{_cs}">Best {_b.hour_label} · {_b.delay:.0f}m</span>'
              f'<span style="background:#FEE4E2;color:#B42318;{_cs}">Worst {_w.hour_label} · {_w.delay:.0f}m</span></div>')
    prof["delay_txt"] = prof.delay.map(lambda x: f"{x:.0f} min")
    prof["dep_txt"] = prof.per_day.map(lambda x: f"about {x:.0f}")
    hr = f["dep_hhmm"] // 100
    hl = f"{hr:02d}:00"
    day_avg = max(float(prof.w.sum() / prof.n.sum()), 0.0)
    row = prof[prof.hour == hr]
    v_hr = float(row.delay.iloc[0]) if len(row) else day_avg
    dep_hr = float(row.per_day.iloc[0]) if len(row) else float(prof.per_day.mean())
    city = city_of(f["origin"])
    stats = ('<div class="stats4">'
             f'<div class="s4"><div class="s4-l"><span class="vb" style="background:{sev(v_hr, 10, 20)}"></span>At {hl}</div>'
             f'<div class="s4-v">{v_hr:.0f}m</div><div class="s4-c">takeoff delay</div></div>'
             '<div class="s4"><div class="s4-l"><span class="vb" style="background:#0055A0"></span>Departures</div>'
             f'<div class="s4-v">{dep_hr:.0f}</div><div class="s4-c">per hour</div></div>'
             f'<div class="s4"><div class="s4-l"><span class="vb" style="background:{sev(day_avg, 10, 20)}"></span>All day</div>'
             f'<div class="s4-v">{day_avg:.0f}m</div><div class="s4-c">takeoff delay</div></div></div>')
    top = (f'<div class="ct">{IC_UP} {city} departures</div>'
           ''
           + stats + '<div class="sub-h">Takeoff delay by hour</div>' + _chips)
    ymax = max(30.0, float(prof.delay.max()) * 1.35)
    tip = [alt.Tooltip("hour_label:N", title="Hour"), alt.Tooltip("delay_txt:N", title="Avg takeoff delay"),
           alt.Tooltip("dep_txt:N", title="Departures per hour")]
    bars = alt.Chart(prof).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("hour_label:N", sort=None, scale=alt.Scale(paddingInner=0.3),
                  axis=x_axis([l for l in prof.hour_label if int(l[:2]) % 3 == 2])),
        y=alt.Y("delay:Q", scale=alt.Scale(domain=[0, ymax]), axis=y_axis()),
        color=alt.Color("c:N", scale=None), tooltip=tip)
    hours_list = list(prof.hour)
    left_side = hours_list.index(hr) < len(hours_list) / 2 if hr in hours_list else True
    mark = pd.DataFrame({"hour_label": [hl], "label": [f"● {v_hr:.0f}m"]})
    rule = alt.Chart(mark).mark_rule(color="#8CC1E9", strokeWidth=1.5).encode(x="hour_label:N")
    pill = alt.Chart(mark).mark_text(fontSize=13, fontWeight="bold", color=sev(v_hr, 10, 20),
                                align="left" if left_side else "right", dx=7 if left_side else -7).encode(
        x="hour_label:N", y=alt.value(8), text="label:N")
    chart = alt.layer(bars, rule, pill).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)
    link = f'<a class="full-link" href="?airport={f["origin"]}" target="_self">{city} airport page →</a>'
    return top, chart, link


def trip_card(f):
    """Standalone card: whole-flight CO2 (EMEP/EEA 2023 Annex 1), comparison, delay add-on, why."""
    title = f'<div class="ct">{IC_LEAF} Climate impact of this flight</div>'
    t = pr.trip_co2(f.get("ac_type"), f["res"].get("distance"))
    if not t:
        return title + '<div class="cs">No fuel data for this aircraft.</div>'
    route = f'{f["origin"]} → {f["dest"]}'
    car_km = t["co2_kg"] / pr.CAR_KG_PER_KM
    laps = car_km / 40075
    car = (f"Like driving a car <b>{laps:.1f} times around the Earth</b>." if laps >= 1.5
           else f"Like driving a car about <b>{car_km:,.0f} km</b>.")
    share = 100 * f["co2_hi"] / t["co2_pp"]
    share_txt = f"{share:.0f}%" if share >= 1 else "less than 1%"
    rows = [("🚗", car),
            ("⏱", f"If it's delayed, this adds up to <b>{share_txt}</b> more "
                  f"(+{kg(f['co2_lo'])}–{kg(f['co2_hi'])} kg for your seat)."),
            ("✈️", f"<b>Why so much?</b> The {aircraft_name(f['family'])} burns about {t['fuel_per_km']:.1f} kg "
                   f"of fuel per km on this {t['km']:,.0f} km flight ({route}). Each kg of jet fuel makes "
                   f"3.16 kg of CO₂, shared over about {t['seats']} seats.")]
    body = "".join(f'<div class="tr-row"><div class="tr-ic">{ic}</div><div>{tx}</div></div>' for ic, tx in rows)
    return (title + f'<div class="tr-big">{t["co2_kg"] / 1000:,.1f} t CO<span class="tr-sub">2</span></div>'
            f'<div class="tr-l">for the whole flight {route} · about {t["co2_pp"]:,.0f} kg for your seat</div>'
            + body)


def box(key, html=None):
    c = st.container(key="pgc_" + key)
    if html:
        c.markdown(html, unsafe_allow_html=True)
    return c


def leg_row(origin, dest, airline, fn, dep, qp, d):
    """Schedule-like row for a sold leg (from the link parameters) so predict_rows() can score it."""
    from core import ignav as ig
    try:
        arr, blk = int(qp.get("arr")), int(qp.get("blk"))
    except (TypeError, ValueError):
        return None
    code = qp.get("code") or airline
    name = pr.carrier_name(code) or pr.carrier_name(airline) or code
    act = ig._ac_icao(qp.get("ac"))
    fam = pr.icao_family(act) if act else None
    if fam not in pr._load()[2]["fam_list"]:
        fam = None

    def hh(v):
        return f"{v // 100:02d}:{v % 100:02d}"
    base = {"origin": origin, "dest": dest, "airline": airline, "flight_number": fn, "dep_hhmm": dep,
            "dep_time": hh(dep), "arr_hhmm": arr, "arr_time": hh(arr), "block_min": blk,
            "airline_name": str(name), "n_flights": 1, "family": fam}
    us, _ = ig._us()
    if origin in us and dest in us:
        dist = pr.route_distance(origin, dest)
        return None if dist is None else pd.Series(dict(base, distance=float(dist), region="US"))
    ref = ig._ref()
    oi, di = ref["ap"].get(origin), ref["ap"].get(dest)
    if not oi or not di or origin not in ref["ll"] or dest not in ref["ll"]:
        return None
    nm = ig._gc_nm(ref["ll"][origin], ref["ll"][dest])
    return pd.Series(dict(base, airline_icao=ref["al"].get(airline, ref["al"].get(code, airline)),
                          origin_icao=oi, dest_icao=di, dep_min=dep // 100 * 60 + dep % 100,
                          weekday=d.weekday(), month=d.month, dist_nm=nm, distance=nm * 1.15078,
                          ac_type=act, Fuel_Flow_Idle_kg_sec=float("nan"),
                          Engine_Count=float("nan"), region="EU"))


def au_override(f, d):
    from core import build_au as au
    from core import ignav as ig
    import datetime as _dt
    if not (au.is_au(f["origin"]) and au.is_au(f["dest"])):
        return f
    dep = _dt.datetime.combine(d, _dt.time(int(f["dep_hhmm"]) // 100, int(f["dep_hhmm"]) % 100))
    res = ig._predict(f["origin"], f["dest"], f["airline"], dep)[0]
    if not res:
        return f
    res = dict(res, distance=f["res"].get("distance"))
    probs = res["probs"]
    m_late = pr.typical_late_minutes(probs, "US")
    lo, hi = pr.delay_co2_range_pp(None, m_late)
    p_late = 1 - probs[0]
    name = f["airline_name"]
    try:
        import os
        r = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "au_routes.csv"),
                        usecols=["airline", "airline_name", "Sectors_Flown"])
        nm = r[r.airline == f["airline"]].groupby("airline_name").Sectors_Flown.sum()
        if len(nm):
            name = str(nm.idxmax())
    except Exception:
        pass
    return dict(f, res=res, p0=probs[0], m_late=m_late, exp_delay=p_late * m_late,
                co2_lo=lo, co2_hi=hi, exp_co2=p_late * hi, au=True, airline_name=name)


def render_flight_page():
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    qp = st.query_params
    try:
        origin, dest, airline, fn, dep = qp.get("flight").split("-")
        fn, dep = int(fn), int(dep)
    except Exception:
        st.info("Flight not found.")
        return
    try:
        d = date.fromisoformat(qp.get("date"))
    except Exception:
        d = date.today()
    base = {"page": "predict", "from": qp.get("from") or origin, "to": qp.get("to") or dest, "date": d.isoformat()}
    list_href = "?" + urlencode(base)
    st.markdown(f'<div class="back"><a href="{list_href}" target="_self">← All flights</a></div>', unsafe_allow_html=True)
    route = day_predictions(origin, dest, d.isoformat())
    f = next((x for x in route if x["airline"] == airline and x["flight_number"] == fn and x["dep_hhmm"] == dep), None)
    if f is None and qp.get("leg"):
        row = leg_row(origin, dest, airline, fn, dep, qp, d)
        if row is not None:
            try:
                f = au_override(predict_rows(pd.DataFrame([row]), d)[0], d)
                route = list(route) + [f]
            except Exception as e:
                print(f"[leg page] {origin}-{dest} {airline}{fn}: {type(e).__name__} {e}")
                f = None
    if f is None:
        st.info(f"{airline} {fn} does not operate on {d.strftime('%A')}s in our schedule.")
        return
    for x in route:
        x["href"] = "?" + urlencode(dict(base, flight=x["key"]))
    with loading():
        wx = {"_date": d, origin: get_weather(origin, d.isoformat()), dest: get_weather(dest, d.isoformat())}

    box("head", header_html(f, d))

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.container(key="pgs_status").markdown(status_card(f, wx, list_href), unsafe_allow_html=True)
    with c2:
        c = box("track", track_card(f))
        tl = timeline_chart(f)
        if tl is not None:
            c.altair_chart(tl, use_container_width=True, theme=None)
    with c3:
        top, chart, link = airport_card(f, d)
        c = box("hour", top or f'<div class="ct">{IC_UP} {city_of(origin)} departures</div>'
                                '<div class="cs">No airport data for this month.</div>')
        if chart is not None:
            c.altair_chart(chart, use_container_width=True, theme=None)
            c.markdown(link, unsafe_allow_html=True)

    c4, c5 = st.columns([1, 2], gap="medium")
    with c4:
        box("wx", weather_card(f, wx) or f'<div class="ct">{IC_THERM} Weather</div>'
                                        '<div class="cs">Weather is unavailable right now.</div>')
        box("trip", trip_card(f))
    with c5:
        box("fc", forecast_card(f, route, list_href))
