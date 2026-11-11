"""Airport page (Flighty style), built around five traveller questions:
is it on time (vs regional average), when to fly (time of day, month), what delays cost the climate
(extra CO2 from delays), which airlines are most reliable here, and where you can fly.
US = BTS (monthly.csv, hourly.csv, flight_history.csv).
Europe = EUROCONTROL (monthly_eu.csv, hourly_eu.csv in UTC -> local, eu_flight_history.csv.gz)."""
import os
from datetime import date, datetime
from functools import lru_cache
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st
from core.loader import loading

from core import predict as pr
from views.airport_picker import lookup
from views.flight import (CSS, IC_CLOCK, IC_CLOUD, IC_DOWN, IC_GAUGE, IC_LEAF, IC_UP, LEVEL_COLORS, LEVEL_HALO,
                          LEVEL_TEXT, PAGE_CSS, TINT, airport_card, box, city_of, dur_words, eu_hist,
                          flight_label, predict_rows,
                          eu_hourly_local, get_weather, hb_row, hourly_df, in_ten, logo_html, month_span, x_axis)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(APP_DIR, "data")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
BUSY = {0: ("Quiet", "Low"), 1: ("Moderate", "Low"), 2: ("Busy", "Moderate"), 3: ("Very busy", "High")}
EARTH_KM = 40075
PARTS = [("morning", 5, 12), ("afternoon", 12, 17), ("evening", 17, 24)]

AP_CSS = """
<style>
.ap-code{font-size:3.4rem;font-weight:700;letter-spacing:-.04em;color:#111418;line-height:1;}
a.ap-btn{display:inline-block;background:#0055A0;color:#fff !important;border-radius:999px;padding:9px 18px;
  font-weight:600;font-size:.92rem;text-decoration:none !important;white-space:nowrap;}
a.ap-btn:hover{filter:brightness(.92);}
.co2-big{font-size:2.6rem;font-weight:700;color:#2F7D4F;letter-spacing:-.03em;line-height:1;margin-top:16px;}
.co2-l{color:#111418;font-size:.92rem;font-weight:600;margin-top:4px;}
.co2-row{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid #E8F1F8;color:#111418;font-size:.93rem;}
.co2-row:last-of-type{border-bottom:none;}
.co2-ic{font-size:1.2rem;width:24px;flex:none;}
.co2-sub{font-size:.42em;vertical-align:baseline;margin-left:2px;letter-spacing:0;}
.ap-warn{color:#B42318;font-weight:700;margin-top:4px;}
.bd-list{max-height:560px;overflow-y:auto;margin-top:8px;}
a.bd-row{display:grid;grid-template-columns:4px 64px minmax(0,1fr) 170px 210px;align-items:center;gap:16px;padding:12px 8px;border-bottom:1px solid #E8F1F8;
  text-decoration:none !important;color:#111418 !important;border-radius:10px;}
a.bd-row:hover{background:#F7FAFC;}
.bd-bar{width:4px;height:34px;border-radius:2px;flex:none;}
.bd-time{font-size:1.15rem;font-weight:700;width:58px;flex:none;}
.bd-dest{flex:1;min-width:0;}
.bd-dest b{display:block;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bd-dest span{color:#111418;font-size:.82rem;}
.bd-air{display:flex;align-items:center;gap:8px;width:150px;flex:none;color:#111418;font-weight:600;font-size:.88rem;}
.bd-air .logo,.bd-air .al{width:24px;height:24px;}
.bd-chip{justify-self:end;border-radius:999px;padding:5px 12px;font-weight:600;font-size:.85rem;white-space:nowrap;flex:none;}
.bd-sum{margin-top:14px;color:#111418;font-weight:600;}
@media (max-width:700px){a.bd-row{grid-template-columns:4px 56px minmax(0,1fr) auto;}.bd-air{display:none;}}
.ap-hero{position:relative;min-height:300px;border-radius:18px;background-size:cover;background-position:center;
  padding:22px 26px;display:flex;flex-direction:column;justify-content:space-between;color:#fff;}
.ap-hero-top{display:flex;justify-content:flex-end;}
.ap-hero-b{display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap;}
.ap-hero .w{color:#fff !important;}
.ap-hero .pg-sub.w{color:rgba(255,255,255,.9) !important;}
.ap-hero a.ap-btn{margin-left:auto;background:#fff;color:#111418 !important;}
.ap-cred{position:absolute;left:16px;top:12px;font-size:.62rem;color:rgba(255,255,255,.8) !important;text-decoration:none !important;
  max-width:55%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 1px 2px rgba(0,0,0,.4);}
.st-key-pgc_ap_head:has(.ap-hero){padding:0 !important;background:transparent !important;border:none !important;box-shadow:none !important;}
.ap-kpi{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:6px 0 18px;}
.ap-k{background:#fff;border:1px solid #E2E6EC;border-radius:16px;padding:16px 18px;}
.ap-k b{display:block;font-size:2rem;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.15;}
.ap-k span{color:#111418;font-size:.85rem;font-weight:600;}
@media (max-width:800px){.ap-kpi{grid-template-columns:repeat(2,minmax(0,1fr));}}
.ap-ia{display:grid;grid-template-columns:repeat(5,26px);gap:8px 12px;margin:14px 0 12px;}
.ap-big{font-size:1.6rem;font-weight:600;color:#111418;letter-spacing:-.02em;margin-bottom:6px;}
.ap-big span{font-size:.9rem;color:#111418;font-weight:600;letter-spacing:0;}
.ap-kv{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:11px 0;border-top:1px solid rgba(18,40,75,.08);}
.ap-kv span{color:#111418;font-weight:600;font-size:.92rem;}
.ap-kv b{color:#111418;font-weight:700;font-size:1.05rem;text-align:right;}
.co2-t{display:flex;align-items:center;gap:14px;background:#F5F9FC;border-radius:12px;padding:12px 14px;margin-top:12px;}
.co2-ti{width:40px;height:40px;border-radius:10px;background:#E3F1E8;color:#2F7D4F;display:flex;align-items:center;justify-content:center;flex:none;}
.co2-t b{display:block;font-size:1.35rem;font-weight:600;color:#111418;letter-spacing:-.02em;}
.co2-t span{color:#111418;font-size:.85rem;font-weight:600;}
.ap-chips{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 8px;}
.rt-g{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:28px;margin-top:16px;}
@media (max-width:900px){.rt-g{grid-template-columns:minmax(0,1fr);}}
.rt-h{font-weight:700;color:#111418;font-size:1.05rem;margin-bottom:10px;}
.rt-ds{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}
a.rt-d{display:flex;align-items:center;gap:12px;background:#F5F9FC;border-radius:14px;padding:12px 14px;text-decoration:none !important;
  color:#111418 !important;transition:transform .15s,box-shadow .15s,background .15s;}
a.rt-d:hover{transform:translateY(-2px);box-shadow:0 8px 18px rgba(18,40,75,.08);background:#fff;}
.rt-rk{width:24px;height:24px;border-radius:50%;background:#0055A0;color:#fff;font-size:.75rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none;}
.rt-m{min-width:0;flex:1;}
.rt-m b{display:block;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.rt-m span,.rt-n span{color:#111418;font-size:.8rem;font-weight:600;}
.rt-n{text-align:right;flex:none;}
.rt-n b{font-size:1.3rem;font-weight:600;font-variant-numeric:tabular-nums;}
.rt-a{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #EEF1F5;}
.rt-a:last-child{border-bottom:none;}
.rt-lg{width:32px;height:32px;flex:none;display:flex;align-items:center;justify-content:center;}
.rt-lg img{max-width:32px;max-height:32px;object-fit:contain;border-radius:6px;}
.rt-am{flex:1;min-width:0;}
.rt-am b{font-weight:700;color:#111418;}
.rt-bar{height:6px;border-radius:999px;background:#E8EEF4;margin-top:6px;max-width:220px;}
.rt-bar i{display:block;height:100%;border-radius:999px;background:#0055A0;}
.rt-pc{font-size:1.3rem;font-weight:600;color:#111418;font-variant-numeric:tabular-nums;}
.rt-top{background:#DDF3E8;color:#1F7A52;border-radius:999px;padding:2px 8px;font-size:.66rem;font-weight:700;letter-spacing:.04em;margin-left:8px;vertical-align:2px;}
.st-key-ap_routes_v2{background:#fff;border:1px solid #E2E6EC;border-radius:20px;padding:28px 28px 20px;}
.ap-hero .fx{position:absolute;inset:0;pointer-events:none;border-radius:inherit;z-index:0;}
.ap-hero-top,.ap-hero-b{position:relative;z-index:2;}
.ap-hero .ap-cred{z-index:2;}
.fx-sun{background:radial-gradient(circle at 82% 10%,rgba(255,214,120,.55),rgba(255,214,120,.14) 22%,transparent 42%);animation:fxglow 5s ease-in-out infinite;}
@keyframes fxglow{50%{filter:brightness(1.15);}}
.fx-grey{background:rgba(90,105,125,.30);mix-blend-mode:multiply;}
.fx-clouds{background:radial-gradient(ellipse 30% 14% at 20% 16%,rgba(255,255,255,.55),transparent 70%),
  radial-gradient(ellipse 26% 12% at 60% 9%,rgba(255,255,255,.45),transparent 70%),
  radial-gradient(ellipse 34% 16% at 95% 22%,rgba(255,255,255,.5),transparent 70%);background-size:200% 100%;animation:fxdrift 45s linear infinite;}
@keyframes fxdrift{to{background-position:-200% 0;}}
.fx-rain{background-image:repeating-linear-gradient(105deg,rgba(255,255,255,0) 0 12px,rgba(255,255,255,.38) 12px 13px,rgba(255,255,255,0) 13px 26px);
  background-size:100% 120px;animation:fxfall .45s linear infinite;}
.fx-rain2{background-image:repeating-linear-gradient(105deg,rgba(255,255,255,0) 0 18px,rgba(255,255,255,.25) 18px 19px,rgba(255,255,255,0) 19px 36px);
  background-size:100% 90px;animation:fxfall .7s linear infinite;}
@keyframes fxfall{to{background-position:-30px 120px;}}
.fx-flash{background:#fff;opacity:0;animation:fxflash 7s infinite;}
@keyframes fxflash{0%,92%,100%{opacity:0;}93%{opacity:.6;}94%{opacity:.1;}95%{opacity:.45;}97%{opacity:0;}}
.fx-snow{background-image:radial-gradient(2.5px 2.5px at 20px 30px,#fff 50%,transparent 51%),radial-gradient(2px 2px at 80px 70px,#fff 50%,transparent 51%),
  radial-gradient(3px 3px at 140px 20px,#fff 50%,transparent 51%),radial-gradient(2px 2px at 200px 90px,#fff 50%,transparent 51%);
  background-size:220px 120px;animation:fxsnow 7s linear infinite;}
@keyframes fxsnow{to{background-position:40px 120px,-30px 120px,20px 120px,-10px 120px;}}
.fx-fog{background:linear-gradient(180deg,rgba(235,240,245,.10),rgba(235,240,245,.50) 60%,rgba(235,240,245,.70));animation:fxfog 12s ease-in-out infinite;}
@keyframes fxfog{50%{opacity:.75;}}
.fx-night{background:linear-gradient(180deg,rgba(6,14,36,.62),rgba(6,14,36,.30));}
.fx-stars{background-image:radial-gradient(1.5px 1.5px at 30px 20px,#fff 50%,transparent 51%),radial-gradient(1px 1px at 120px 50px,#fff 50%,transparent 51%),
  radial-gradient(1.5px 1.5px at 210px 30px,#fff 50%,transparent 51%),radial-gradient(1px 1px at 300px 60px,#fff 50%,transparent 51%);
  background-size:340px 120px;background-repeat:repeat-x;animation:fxtw 3s ease-in-out infinite;}
@keyframes fxtw{50%{opacity:.4;}}
@media (prefers-reduced-motion:reduce){.ap-hero .fx{animation:none !important;}}
</style>
"""


def _deg(v):
    """Temperature as text; '–' when the weather service returned no value."""
    try:
        return f"{float(v):.0f}"
    except (TypeError, ValueError):
        return "–"


def level_of(ot):
    return "Low" if ot >= 0.85 else ("Moderate" if ot >= 0.75 else "High")


# ---------------- data ----------------
@lru_cache(maxsize=1)
@lru_cache(maxsize=1)
def _monthly_au():
    p = os.path.join(DATA, "monthly_au.csv")
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=["airport", "Year", "Month"])


def _monthly():
    us = pd.read_csv(os.path.join(DATA, "monthly.csv"))
    eu = pd.read_csv(os.path.join(DATA, "monthly_eu.csv"))
    return us, eu


@lru_cache(maxsize=1)
def _ref():
    return pd.read_csv(os.path.join(DATA, "ref", "airports.csv"), keep_default_na=False,
                       usecols=["ident", "iata_code", "name", "municipality", "iso_country"])


@lru_cache(maxsize=1)
def _home():
    h = pd.read_csv(os.path.join(DATA, "home_airports.csv"), keep_default_na=False)
    return {str(r.code): r for r in h.itertuples(index=False)}


@lru_cache(maxsize=1)
def _us_history():
    return pd.read_csv(os.path.join(DATA, "flight_history.csv"))


def resolve(code):
    """US airports by IATA code; European airports by ICAO (EGLL) or IATA (LHR) code."""
    us, eu = _monthly()
    code = (code or "").strip().upper()
    if not code:
        return None
    if code not in set(us.airport) and code not in set(eu.airport) and not (_ref().iata_code == code).any():
        q = code.lower()   # typed a city / airport name instead of a code
        rows = [(c, r) for c, r in _home().items() if str(getattr(r, "region", "")) in ("US", "EU", "AU")]
        hit = (next((c for c, r in rows if str(r.city).lower() == q), None)
               or next((c for c, r in rows if q in str(r.name).lower() or q in str(r.city).lower()), None))
        if hit:
            code = hit.upper()
    if code in set(us.airport):
        return {"region": "US", "iata": code, "icao": "", "rows": us[us.airport == code]}
    au = _monthly_au()
    if code in set(au.airport):
        return {"region": "AU", "iata": code, "icao": "", "rows": au[au.airport == code]}
    ref = _ref()
    eu_codes = set(eu.airport)
    icao = code if code in eu_codes else None
    if icao is None:
        cand = ref[(ref.iata_code == code) & ref.ident.isin(eu_codes)]
        if cand.empty:
            return None
        icao = cand.ident.iloc[0]
    hit = ref[ref.ident == icao]
    iata = hit.iata_code.iloc[0] if len(hit) and hit.iata_code.iloc[0] else icao
    return {"region": "EU", "iata": iata, "icao": icao, "rows": eu[eu.airport == icao]}


def info(a):
    lk = lookup().get(a["iata"]) or {}
    ref = _ref()
    hit = ref[ref.ident == a["icao"]] if a["icao"] else ref.iloc[0:0]
    name = lk.get("airport") or (hit["name"].iloc[0] if len(hit) else a["iata"])
    city = lk.get("city") or (hit["municipality"].iloc[0] if len(hit) else a["iata"])
    return {"airport": name, "city": city, "country": lk.get("country", ""), "tz": lk.get("tz") or "UTC"}


def month_stats(rows, m):
    r = rows if m is None else rows[rows.Month == m]
    if r.empty:
        return None

    def wavg(v, w):
        d = r.dropna(subset=[v, w])
        tot = d[w].sum()
        return float((d[v] * d[w]).sum() / tot) if tot > 0 else float("nan")

    return {"dep_ot": wavg("pct_dep_ontime", "n_dep"), "dep_late": wavg("avg_dep_when_late", "n_dep"),
            "arr_ot": wavg("pct_arr_ontime", "n_arr"),
            "co2": float(r.co2_tonnes.mean()) if "co2_tonnes" in r.columns else float("nan"),
            "years": sorted(int(y) for y in r.Year.unique())}


def hour_profile(a, month):
    if a["region"] == "EU":
        h, m = eu_hourly_local(a["icao"], a["iata"]), pr.EU_MONTH_MAP[month]
    else:
        h = hourly_df()
        h, m = h[h.airport == a["iata"]], month
    if h.empty:
        return None
    x = h[h.Month == m]
    if x.empty:
        x = h
    x = x.assign(w=x.n * x.avg_dep_delay.clip(lower=0))
    return x.groupby("hour").agg(n=("n", "sum"), w=("w", "sum"))


def best_time(prof):
    """('morning', sentence) comparing average takeoff delay across parts of the day."""
    if prof is None:
        return None, ""
    vals = []
    for name, a0, a1 in PARTS:
        p = prof[(prof.index >= a0) & (prof.index < a1)]
        if p.n.sum() >= 30:
            vals.append((p.w.sum() / p.n.sum(), name))
    if len(vals) < 2:
        return None, ""
    best, worst = min(vals), max(vals)
    if worst[0] - best[0] < 3:
        return None, "Delays are about the same all day."
    return best[1], (f"<b>Fly in the {best[1]}.</b> Departures are about {best[0]:.0f} min late on average, "
                     f"vs {worst[0]:.0f} min in the {worst[1]}.")


def worst_time(prof):
    """Worst 3-hour window for departures at this airport (average takeoff delay)."""
    if prof is None:
        return ""
    p = prof[prof.n >= 30]
    worst_v, worst_h = -1.0, None
    for h in p.index:
        win = p[(p.index >= h) & (p.index < h + 3)]
        if len(win) < 3:
            continue
        v = win.w.sum() / win.n.sum()
        if v > worst_v:
            worst_v, worst_h = v, int(h)
    if worst_h is None:
        return ""
    part = next((nm for nm, a0, a1 in PARTS if a0 <= worst_h < a1), "night")
    return (f"{part}, {worst_h:02d}:00–{(worst_h + 3) % 24:02d}:00 "
            f"(departures about {worst_v:.0f} min late on average)")


def reliable_airlines(a):
    if a["region"] == "US":
        h = _us_history()
        h = h[h.origin == a["iata"]]
        if h.empty:
            return h, ""
        g = h.groupby("airline").agg(n=("n", "sum"), ok=("on_time", "sum"))
        g["code"] = g.index
        g["name"] = [pr.carrier_name(c) for c in g.index]
        period = month_span(str(h["first"].min()), str(h["last"].max()))
    else:
        hh, _ = eu_hist()
        h = hh[hh.origin_icao == a["icao"]]
        if h.empty:
            return h, ""
        g = (h.assign(ok=h.arr_delay_min <= 15).groupby("airline_icao")
             .agg(n=("ok", "size"), ok=("ok", "sum")))
        m = pr.eu_schedule().drop_duplicates("airline_icao").set_index("airline_icao")
        g["code"] = [m.airline.get(c, c) for c in g.index]
        g["name"] = [m.airline_name.get(c, c) for c in g.index]
        period = "2023–24 samples"
    g = g[g.n >= 30].copy()
    g["ot"] = g.ok / g.n
    return g.sort_values("ot", ascending=False).head(6), period


# ---------------- cards ----------------
CAR_SVG = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
           'stroke-linejoin="round"><path d="M5 17H3v-6l2-5h9l4 5h1a2 2 0 0 1 2 2v4h-2M9 17h6M3 11h15M12 11V6"/>'
           '<circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg>')
CAL_SVG = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
           'stroke-linejoin="round"><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M16 3v4M8 3v4M4 11h16"/></svg>')
PLANE_PATH = "M2 16.5l20-6.5-2-2-7 2L8 4H6l2.5 7.2L5 12.5 3 11H2l1 3.2z"


@st.cache_data(show_spinner=False)
def _photos():
    try:
        d = pd.read_csv(os.path.join(DATA, "city_photos.csv"))
    except Exception:
        return {}
    clean = lambda v: "" if pd.isna(v) else str(v)
    return {str(r.code): {"url": clean(r.url), "page": clean(r.page), "author": clean(r.author), "license": clean(r.license)}
            for r in d.itertuples(index=False)}


def _plane(color, size=26):
    return f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true"><path d="{PLANE_PATH}" fill="{color}"/></svg>'


def _chip(word, lab, val, good):
    bg, fg = ("#DDF3E8", "#1F7A52") if good else ("#FEE4E2", "#B42318")
    return (f'<span style="background:{bg};color:{fg};border-radius:999px;padding:4px 11px;font-size:.78rem;'
            f'font-weight:700;white-space:nowrap">{word} {lab} · {val}</span>')


def _mins(x):
    return f"{x:.0f} min" if x < 60 else f"{x / 60:.1f} h"


def kpi_html(a, s, best, mname):
    tiles = []
    b = _home().get(a["iata"]) or _home().get(a["icao"])
    if b is not None and a["region"] != "IN":
        try:
            tiles.append((f"{float(b.sort):,.0f}", "departures a day", "#12284B"))
        except (TypeError, ValueError, AttributeError):
            pass
    ot = s.get("dep_ot")
    if ot is not None and ot == ot:
        tiles.append((in_ten(ot), f"leave on time in {mname}", LEVEL_COLORS[level_of(ot)]))
    late = s.get("dep_late")
    if late is not None and late == late:
        tiles.append((_mins(late), "typical delay if late", "#12284B"))
    if best:
        tiles.append((str(best)[:1].upper() + str(best)[1:], "best time to depart", "#12284B"))
    if not tiles:
        return ""
    return ('<div class="ap-kpi">' + "".join(f'<div class="ap-k"><b style="color:{c}">{v}</b><span>{l}</span></div>'
                                             for v, l, c in tiles) + '</div>')


def _wx_fx(w, now):
    """Animated weather layers for the hero photo, from today's weather text and the airport's local hour."""
    t = str((w or {}).get("text", "")).lower()
    k = set()
    if "thunder" in t or "storm" in t:
        k |= {"grey", "clouds", "rain", "rain2", "flash"}
    elif any(x in t for x in ("rain", "drizzle", "shower")):
        k |= {"grey", "clouds", "rain", "rain2"}
    elif any(x in t for x in ("snow", "sleet", "flurr")):
        k |= {"snow"}
    elif any(x in t for x in ("fog", "mist", "haze")):
        k |= {"fog"}
    elif "cloud" in t or "overcast" in t:
        k |= {"grey", "clouds"}
    elif t:
        k |= {"sun"}
    if now.hour < 6 or now.hour >= 19:
        k.discard("sun")
        k.add("night")
        if not (k & {"rain", "snow", "fog", "clouds"}):
            k.add("stars")
    order = ["sun", "night", "grey", "clouds", "rain", "rain2", "flash", "snow", "fog", "stars"]
    return "".join(f'<div class="fx fx-{c}"></div>' for c in order if c in k)


def header_html(a, inf):
    now = datetime.now(ZoneInfo(inf["tz"]))
    w = get_weather(a["iata"], date.today().isoformat())
    wx = f' · {w["icon"]} {_deg(w["t_max"])}° {w["text"]}' if w else ""
    pill = ""
    b = _home().get(a["iata"]) or _home().get(a["icao"])
    if b is not None:
        try:
            lvl = int(float(b.busy_level))
        except (TypeError, ValueError):
            lvl = None
        if lvl in BUSY:
            word, key = BUSY[lvl]
            pill = (f'<span class="risk-tag" style="background:{LEVEL_HALO[key]};color:{LEVEL_TEXT[key]}">'
                    f'<span class="rdot" style="background:{LEVEL_COLORS[key]}"></span>{word.upper()} · {b.busy_txt}</span>')
    place = inf["city"] + (", " + inf["country"] if inf["country"] else "")
    icao = f' · {a["icao"]}' if a["icao"] and a["icao"] != a["iata"] else ""
    href = "?" + urlencode({"page": "predict", "from": a["iata"]})
    ph = _photos().get(a["iata"])
    if ph and ph["url"]:
        import html as _h
        cred = _h.escape(ph["author"] or "Wikimedia Commons") + (" · " + _h.escape(ph["license"]) if ph["license"] else "")
        url = ph["url"].replace("'", "%27").replace('"', "%22")
        return (f'<div class="ap-hero" style="background-image:linear-gradient(180deg,rgba(11,25,48,.10) 0%,'
                f'rgba(11,25,48,.30) 45%,rgba(11,25,48,.82) 100%),url(\'{url}\')">'
                f'{_wx_fx(w, now)}'
                f'<a class="ap-cred" href="{_h.escape(ph["page"])}" target="_blank" rel="noopener">Photo: {cred}</a>'
                f'<div class="ap-hero-top">{pill}</div>'
                f'<div class="ap-hero-b"><div class="ap-code w">{a["iata"]}</div>'
                f'<div><div class="pg-title w">{inf["airport"]}</div>'
                f'<div class="pg-sub w">{place}{icao} · 🕐 {now:%H:%M} {now.strftime("%Z")}{wx}</div></div>'
                f'<a class="ap-btn" href="{href}" target="_self">Check a flight from here</a></div></div>')
    return (f'<div class="h-row"><div class="ap-code">{a["iata"]}</div>'
            f'<div><div class="pg-title">{inf["airport"]}</div><div class="pg-sub">{place}{icao}</div></div>'
            f'<div style="margin-left:auto">{pill}</div></div>'
            f'<div class="h-row" style="margin-top:14px"><div class="pg-sub">🕐 {now:%H:%M} {now.strftime("%Z")}{wx}</div>'
            f'<a class="ap-btn" style="margin-left:auto" href="{href}" target="_self">Check a flight from here</a></div>')


def status_html(a, inf, s, mname):
    ot = s["dep_ot"]
    level = level_of(ot)
    head = {"Low": "Departures usually on time", "Moderate": "Departures mostly on time",
            "High": "Delays are common"}[level]
    bg, foot, dot, link = TINT[level]
    n = max(0, min(10, int(round(ot * 10))))
    ia = '<div class="ap-ia">' + "".join(_plane("#2C9A69" if k < n else "#D3DCE6") for k in range(10)) + '</div>'
    rows = []
    if s["arr_ot"] == s["arr_ot"]:
        rows.append(("Arrivals on time", in_ten(s["arr_ot"])))
    if s["dep_late"] == s["dep_late"]:
        rows.append(("Typical delay if late", _mins(s["dep_late"])))
    w = get_weather(a["iata"], date.today().isoformat())
    warn = ""
    if w:
        rows.append(("Weather today", f'{w["text"]} · {_deg(w["t_max"])}° / {_deg(w["t_min"])}°'))
        if w.get("warnings"):
            warn = f'<div class="ap-warn">⚠️ {", ".join(w["warnings"])}</div>'
    body = (ia + f'<div class="ap-big">{in_ten(ot)} <span>departures on time in {mname}</span></div>'
            + "".join(f'<div class="ap-kv"><span>{k}</span><b>{v}</b></div>' for k, v in rows) + warn)
    return (f'<div class="status" style="background:{bg}"><div class="st-body">'
            f'<div class="st-title"><span class="st-dot" style="background:{dot};box-shadow:0 0 0 5px {foot}"></span>'
            f'{head}</div>{body}</div>'
            f'<div class="st-foot" style="background:{foot}"><a href="?airport={a["iata"]}&view=departures" target="_self" style="color:{link}">'
            f'See departures from {inf["city"]} ›</a></div></div>')


def climate_payload(a, s, mname, tz, deps_per_day=None):
    """Numbers for the highlighted climate card; same maths as climate_html."""
    try:
        co2 = float(s["co2"])
    except (TypeError, ValueError, KeyError):
        return None
    if not co2 == co2 or co2 <= 0:
        return None
    km = co2 * 1000 / pr.CAR_KG_PER_KM
    laps = km / EARTH_KM
    day_t = co2 / 30.4
    if laps >= 1.5:
        ln, lsuf, ll = round(laps), "×", "around the Earth by car"
    else:
        ln, lsuf, ll = round(km), " km", "driven by car"
    per_dep = round(day_t * 1000 / deps_per_day) if deps_per_day and deps_per_day > 0 else None
    return {"total_t": round(co2), "day_t": round(day_t, 1), "laps_num": ln, "laps_suffix": lsuf,
            "laps_label": ll, "per_dep_kg": per_dep, "tz": tz,
            "sub": f"extra from delays at {a['iata']} in a typical {mname}"}


def climate_html(s, mname, note, best, worst=""):
    title = f'<div class="ct">{IC_LEAF} Climate cost of delays</div>'
    co2 = s["co2"]
    if not co2 == co2 or co2 <= 0:
        return title + '<div class="cs">No delay-emission data for this airport.</div>'
    km = co2 * 1000 / pr.CAR_KG_PER_KM
    laps = km / EARTH_KM
    car_v, car_l = (f"{laps:,.0f}×", "around the Earth by car") if laps >= 1.5 else (f"{km:,.0f} km", "driven by car")
    tiles = [(CAR_SVG, car_v, car_l), (CAL_SVG, f"{co2 / 30.4:,.1f} t", "every day")]
    body = "".join(f'<div class="co2-t"><div class="co2-ti">{ic}</div><div><b>{v}</b><span>{l}</span></div></div>'
                   for ic, v, l in tiles)
    return (title + f'<div class="co2-big">{co2:,.0f} t CO<span class="co2-sub">2</span></div>'
            f'<div class="co2-l">extra from delays in a typical {mname}</div>' + body)


def month_card(rows, sel, note, upto=12):
    hv_m = alt.selection_point(on="pointerover", clear="pointerout", empty=False)
    ck_m = alt.selection_point(on="click", fields=["Month"], name="ck_m")
    d = rows.dropna(subset=["pct_dep_ontime", "n_dep"])
    g = (d.assign(w=d.n_dep * d.pct_dep_ontime).groupby("Month")
         .agg(n=("n_dep", "sum"), w=("w", "sum")).reset_index())
    g = g[(g.n > 0) & (g.Month <= upto)]
    if g.empty:
        return f'<div class="ct">{IC_GAUGE} Month by month</div><div class="cs">No data.</div>', None
    g["ot"] = g.w / g.n
    g["m"] = g.Month.map(lambda x: MONTHS[int(x) - 1][:3])
    g["c"] = ["#0055A0" if int(x) == sel else "#C9DEEE" for x in g.Month]
    g["txt"] = g.ot.map(lambda x: f"{x:.0%} on time")
    head = f'<div class="ct">{IC_GAUGE} Month by month</div>'
    if len(g) > 1:
        bm, wm = g.loc[g.ot.idxmax()], g.loc[g.ot.idxmin()]
        head += ('<div class="ap-chips">' + _chip("Best", bm.m, f"{bm.ot:.0%} on time", True)
                 + _chip("Worst", wm.m, f"{wm.ot:.0%} on time", False) + '</div>')
    ch = alt.Chart(g).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, cursor="pointer").encode(
        x=alt.X("m:N", sort=[mo[:3] for mo in MONTHS],
                scale=alt.Scale(domain=[mo[:3] for mo in MONTHS], paddingInner=0.3), axis=x_axis()),
        y=alt.Y("ot:Q", scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(orient="right", format="%", title=None, gridDash=[3, 3], gridColor="#D5DEE8",
                              domain=False, ticks=False, labelColor="#8592A6", labelFontSize=12, tickCount=3)),
        color=alt.condition(hv_m, alt.value("#003F7A"), alt.Color("c:N", scale=None)),
        tooltip=[alt.Tooltip("m:N", title="Month"), alt.Tooltip("txt:N", title="Departures")])
    return head, ch.add_params(hv_m, ck_m).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)


def _routes_html_au(a, inf, month):
    import calendar
    title = f'<div class="ct">{IC_UP} Where you can fly</div>'
    try:
        r = pd.read_csv(os.path.join(DATA, "au_routes.csv"))
    except Exception:
        return title + '<div class="cs">No regular nonstop flights in our schedule.</div>'
    r = r[(r.ym > r.ym.max() - 100) & (r.origin == a["iata"])]
    if r.empty:
        return title + '<div class="cs">No regular nonstop flights in our schedule.</div>'
    m = r[r.Month_Num == month]
    if m.empty:
        m = r
    days = sum(calendar.monthrange(int(y), int(mo))[1]
               for y, mo in m[["Year", "Month_Num"]].drop_duplicates().itertuples(index=False))
    al = m[(m.airline != "ALL") & (m.Sectors_Flown > 0)]
    dests = m[m.airline == "ALL"].groupby("dest").Sectors_Flown.sum().div(max(days, 1)).to_frame("per_day")
    dests["n_air"] = al.groupby("dest").airline.nunique()
    dests["n_air"] = dests.n_air.fillna(1).clip(lower=1).astype(int)
    dests = dests[dests.per_day > 0].sort_values("per_day", ascending=False).head(8)
    if dests.empty:
        return title + '<div class="cs">No regular nonstop flights in our schedule.</div>'
    mx = float(dests.per_day.max()) or 1.0
    drows = "".join(
        hb_row("?" + urlencode({"page": "predict", "from": a["iata"], "to": dest}), f'<span class="al">{dest}</span>',
               city_of(dest)[:16], f'{dest} · {int(r_.n_air)} airline{"s" if r_.n_air > 1 else ""}',
               6 + 94 * r_.per_day / mx, "#0055A0",
               f"{r_.per_day:.0f}/day" if r_.per_day >= 1 else f"{r_.per_day * 7:.0f}/wk",
               f"<b>{city_of(dest)} · {dest}</b>About {r_.per_day:.1f} flights a day · tap to compare", False)
        for dest, r_ in dests.iterrows())
    g = al.groupby("airline").agg(n=("Sectors_Flown", "sum"), ok=("Arrivals_On_Time", "sum")).reset_index()
    top_nm = (al.groupby(["airline", "airline_name"]).Sectors_Flown.sum().reset_index()
              .sort_values("Sectors_Flown").drop_duplicates("airline", keep="last").set_index("airline").airline_name)
    g["nm"] = g.airline.map(top_nm)
    g = g[g.n >= 50]
    g["ot"] = g.ok / g.n
    g = g.sort_values("ot", ascending=False).head(8)
    href = "?" + urlencode({"page": "predict", "from": a["iata"]})
    arows = "".join(
        hb_row(href, logo_html(r_.airline), r_.airline, str(r_.nm)[:18],
               max(6.0, min(100.0, 6 + 94 * (r_.ot - 0.5) / 0.5)), LEVEL_COLORS[level_of(r_.ot)],
               f"{r_.ot:.0%}", f"<b>{r_.nm}</b>{int(r_.ok):,} of {int(r_.n):,} flights on time", False)
        for r_ in g.itertuples(index=False)) or '<div class="cs">Not enough flights to compare airlines.</div>'
    return (title + f'<div class="cs">Regular nonstop flights from {inf["city"]}</div><div class="lists2">'
            '<div><div class="hb-h"><span class="hb-t">Top destinations</span></div>' + drows + '</div>'
            '<div><div class="hb-h"><span class="hb-t">Most reliable airlines</span></div>' + arows + '</div></div>')


def _top_dests(a, month):
    s = pr.schedule()
    s = s[s.origin == a["iata"]]
    us = s[s.region == "US"].copy()
    eu = s[(s.region == "EU") & (s.month == pr.EU_MONTH_MAP[month])].copy()
    if len(us):
        try:
            p0, p1 = str(us.period.iloc[0]).split(" to ")
            days = (date.fromisoformat(p1.strip()) - date.fromisoformat(p0.strip())).days + 1
        except Exception:
            days = 61
        us["per_day"] = us.n_flights / days
    if len(eu):
        eu["per_day"] = eu.n_flights / 30.4
    s = pd.concat([us, eu])
    if s.empty:
        return None
    return (s.groupby("dest").agg(per_day=("per_day", "sum"), n_air=("airline", "nunique"))
            .sort_values("per_day", ascending=False).head(8))


def route_map(a, month):
    """Arcs from this airport to its top nonstop destinations (thicker = more flights a day)."""
    try:
        import pydeck as pdk
    except ImportError:
        return None
    dests = _top_dests(a, month)
    H = _home()
    o = H.get(a["iata"]) or H.get(a["icao"])
    if dests is None or o is None:
        return None
    rows = []
    for dest, r in dests.iterrows():
        d = H.get(dest)
        if d is None:
            continue
        v = float(r.per_day)
        rows.append({"src": [float(o.lon), float(o.lat)], "dst": [float(d.lon), float(d.lat)], "v": v, "code": dest,
                     "city": city_of(dest), "txt": f"{v:.0f} flights a day" if v >= 1 else f"{v * 7:.0f} flights a week"})
    if not rows:
        return None
    mx = max(r["v"] for r in rows) or 1.0
    for r in rows:
        r["w"] = 2 + 6 * r["v"] / mx
    vs = pdk.data_utils.compute_view([r["dst"] for r in rows] + [rows[0]["src"]], view_proportion=1)
    vs.zoom = max(1.0, float(vs.zoom) - 0.5)
    vs.pitch, vs.bearing = 0, 0
    me = {"dst": rows[0]["src"], "code": a["iata"], "city": city_of(a["iata"]), "txt": "you are here"}
    layers = [
        pdk.Layer("ArcLayer", data=rows, get_source_position="src", get_target_position="dst", get_width="w",
                  get_source_color=[18, 40, 75, 230], get_target_color=[0, 85, 160, 230], great_circle=True, pickable=True),
        pdk.Layer("ScatterplotLayer", data=rows, get_position="dst", get_radius=6, radius_units="pixels",
                  get_fill_color=[0, 85, 160], stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2, pickable=True),
        pdk.Layer("ScatterplotLayer", data=[me], get_position="dst", get_radius=9, radius_units="pixels",
                  get_fill_color=[18, 40, 75], stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2),
        pdk.Layer("TextLayer", data=rows + [me], get_position="dst", get_text="code", get_size=13,
                  get_color=[18, 40, 75], get_pixel_offset=[0, -16], font_weight=700,
                  font_family='"Plus Jakarta Sans", sans-serif', background=True, get_background_color=[255, 255, 255, 220],
                  background_padding=[4, 2])]
    return pdk.Deck(layers=layers, initial_view_state=vs, map_provider="carto", map_style="light",
                    views=[pdk.View(type="MapView", controller={"scrollZoom": False})],
                    tooltip={"html": "<b>{city} · {code}</b><br/>{txt}",
                             "style": {"background": "#12284B", "color": "#fff", "borderRadius": "8px",
                                       "fontFamily": "Plus Jakarta Sans, sans-serif", "padding": "8px 10px"}})


def routes_payload(a, inf, month):
    """Data for the route-map component (non-AU airports)."""
    dests = _top_dests(a, month)
    H = _home()
    o = H.get(a["iata"]) or H.get(a["icao"])
    if dests is None or o is None:
        return None
    D = []
    for dest, r in dests.iterrows():
        d = H.get(dest)
        v = float(r.per_day)
        D.append({"code": str(dest), "city": city_of(dest), "v": v, "n_air": int(r.n_air),
                  "lat": float(d.lat) if d is not None else None, "lon": float(d.lon) if d is not None else None,
                  "txt": f"{v:.0f}/day" if v >= 1 else f"{v * 7:.0f}/wk",
                  "num": f"{v:.0f}" if v >= 1 else f"{v * 7:.0f}", "unit": "/day" if v >= 1 else "/wk"})
    al, _ = reliable_airlines(a)
    A = []
    if len(al):
        best = float(al.ot.max())
        for _, r in al.iterrows():
            A.append({"code": str(r["code"]), "name": str(r["name"]), "ot": float(r.ot), "ok": int(r.ok), "n": int(r.n),
                      "logo": logo_html(r["code"]), "top": float(r.ot) == best})
    return {"hub": {"code": a["iata"], "lat": float(o.lat), "lon": float(o.lon)}, "dests": D, "airlines": A,
            "sub": f"{len(D)} popular routes from {inf['city']}"}


def routes_html(a, inf, month):
    if a["region"] == "AU":
        return _routes_html_au(a, inf, month)
    dests = _top_dests(a, month)
    if dests is None:
        return '<div class="cs">No regular nonstop flights in our schedule.</div>'
    tiles = ""
    for i, (dest, r) in enumerate(dests.iterrows(), 1):
        v, unit = (f"{r.per_day:.0f}", "/day") if r.per_day >= 1 else (f"{r.per_day * 7:.0f}", "/wk")
        href = "?" + urlencode({"page": "predict", "from": a["iata"], "to": dest})
        tiles += (f'<a class="rt-d" href="{href}" target="_self"><span class="rt-rk">{i}</span>'
                  f'<div class="rt-m"><b>{city_of(dest)}</b><span>{dest} · {int(r.n_air)} airline{"s" if r.n_air > 1 else ""}</span></div>'
                  f'<div class="rt-n"><b>{v}</b><span>{unit}</span></div></a>')
    al, period = reliable_airlines(a)
    if len(al):
        best_ot = float(al.ot.max())
        arows = "".join(
            f'<div class="rt-a" title="{int(r.ok)} of {int(r.n)} flights on time"><span class="rt-lg">{logo_html(r["code"])}</span>'
            f'<div class="rt-am"><b>{r["name"]}</b>{"<span class=rt-top>MOST ON TIME</span>" if float(r.ot) == best_ot else ""}'
            f'<div class="rt-bar"><i style="width:{100 * float(r.ot):.0f}%"></i></div></div>'
            f'<span class="rt-pc">{r.ot:.0%}</span></div>'
            for _, r in al.iterrows())
    else:
        arows = '<div class="cs">Not enough flights to compare airlines.</div>'
    return ('<div class="rt-g"><div><div class="rt-h">Top destinations</div><div class="rt-ds">' + tiles + '</div></div>'
            '<div><div class="rt-h">Airlines on time</div>' + arows + '</div></div>')


# ---------------- departure forecast board ----------------
WINDOWS = {"Morning": (5, 12), "Afternoon": (12, 17), "Evening": (17, 24), "Night": (0, 5)}
WHEN = {"Next 3 hours": "in the next 3 hours", "Morning": "in the morning", "Afternoon": "in the afternoon",
        "Evening": "in the evening", "Night": "at night"}
CHIP = {"Low": "Likely on time", "Moderate": "May be late ~{m} min", "High": "Often late ~{m} min"}


@st.cache_data(show_spinner=False)
def board_predictions(iata, date_iso, h0, h1):
    """Scheduled departures with forecasts, computed in 3-hour blocks kept on disk (data/board_cache),
    so the board, the ticker and app restarts reuse them and only new blocks are ever computed."""
    import glob, pickle, time as _t
    cdir = os.path.join(DATA, "board_cache")
    os.makedirs(cdir, exist_ok=True)
    d = date.fromisoformat(date_iso)
    sched, out = None, []
    for b in range((h0 // 3) * 3, h1, 3):
        path = os.path.join(cdir, f"{iata}_{date_iso}_{b:02d}.pkl")
        rows = None
        if os.path.exists(path):
            try:
                with open(path, "rb") as fh:
                    rows = pickle.load(fh)
            except Exception:
                rows = None
        if rows is None:
            if sched is None:
                sched = pr.flights_on(iata, None, d)
            df = sched[(sched.dep_hhmm >= b * 100) & (sched.dep_hhmm < (b + 3) * 100)]
            rows = predict_rows(df, d)
            try:
                with open(path, "wb") as fh:
                    pickle.dump(rows, fh)
            except Exception:
                pass
        out += rows
    try:
        for old in glob.glob(os.path.join(cdir, "*.pkl")):
            if _t.time() - os.path.getmtime(old) > 3 * 86400:
                os.remove(old)
    except Exception:
        pass
    return [f for f in out if h0 * 100 <= int(f["dep_hhmm"]) < h1 * 100]


def board_row(f, a, iso):
    level = f["res"]["level"]
    chip = CHIP[level].format(m=int(round(f["m_late"])))
    href = "?" + urlencode({"page": "predict", "from": a["iata"], "to": f["dest"], "date": iso, "flight": f["key"]})
    return (f'<a class="bd-row" href="{href}" target="_self">'
            f'<span class="bd-bar" style="background:{LEVEL_COLORS[level]}"></span>'
            f'<div class="bd-time">{f["dep_time"]}</div>'
            f'<div class="bd-dest"><b>{city_of(f["dest"])}</b><span>{f["dest"]}</span></div>'
            f'<div class="bd-air">{logo_html(f["airline"])}<span>{flight_label(f)}</span></div>'
            f'<span class="bd-chip" style="background:{LEVEL_HALO[level]};color:{LEVEL_TEXT[level]}">● {chip}</span></a>')


def board_summary(flights, win):
    n, nh = len(flights), sum(f["res"]["level"] == "High" for f in flights)
    when = WHEN[win]
    if nh == 0:
        return f"None of the {n} departures {when} has a high delay risk."
    if nh / n < 0.15:
        return f"Most departures {when} run on time: only {nh} of {n} have a high delay risk."
    return f"{nh} of {n} departures {when} have a high delay risk."


def board_payload(a, inf, flights, day):
    """Rows for the airport-style board. Logos are sent once per airline."""
    tz = ZoneInfo(inf["tz"])
    out, logos = [], {}
    for f in flights:
        hh, mm = divmod(int(f["dep_hhmm"]), 100)
        t = datetime(day.year, day.month, day.day, hh % 24, mm, tzinfo=tz)
        level = f["res"]["level"]
        al = str(f["airline"])
        if al not in logos:
            logos[al] = logo_html(al)
        out.append({"t": int(t.timestamp() * 1000), "time": f"{hh % 24:02d}:{mm:02d}", "fl": flight_label(f), "al": al,
                    "dest": f["dest"], "city": city_of(f["dest"]), "lvl": {"Low": "g", "Moderate": "a", "High": "r"}[level],
                    "risk": CHIP[level].format(m=int(round(f["m_late"]))).upper(),
                    "qp": {"page": "predict", "from": a["iata"], "to": f["dest"], "date": day.isoformat(), "flight": f["key"]}})
    return {"flights": out, "logos": logos, "tz": inf["tz"], "now_ms": int(datetime.now(tz).timestamp() * 1000),
            "title": f"{inf['city']} · {a['iata']}".upper(), "date_label": day.strftime("%a %d %b").upper()}


def board_payload24(a, inf, items, now, win=None):
    """Rolling board: last hour (shown as departed) to 24 hours ahead. Logos are sent once per airline."""
    from datetime import timedelta as _td
    tz = ZoneInfo(inf["tz"])
    lo, hi = now - _td(hours=1), now + _td(hours=24)
    out, logos = [], {}
    for f, d in items:
        hh, mm = divmod(int(f["dep_hhmm"]), 100)
        t = datetime(d.year, d.month, d.day, hh % 24, mm, tzinfo=tz)
        if not (lo <= t < hi):
            continue
        level = f["res"]["level"]
        al = str(f["airline"])
        if al not in logos:
            logos[al] = logo_html(al)
        out.append({"t": int(t.timestamp() * 1000), "time": f"{hh % 24:02d}:{mm:02d}", "h": hh % 24,
                    "plus1": d > now.date(), "fl": flight_label(f), "al": al,
                    "dest": f["dest"], "city": city_of(f["dest"]), "lvl": {"Low": "g", "Moderate": "a", "High": "r"}[level],
                    "risk": CHIP[level].format(m=int(round(f["m_late"]))).upper(),
                    "qp": {"page": "predict", "from": a["iata"], "to": f["dest"], "date": d.isoformat(), "flight": f["key"]}})
    out.sort(key=lambda x: (x["t"], x["fl"]))
    nxt = now + _td(days=1)
    return {"flights": out, "logos": logos, "tz": inf["tz"], "now_ms": int(now.timestamp() * 1000),
            "win": [0, 24], "title": f"{inf['city']} · {a['iata']}".upper(),
            "date_label": f"{now:%a %d %b} – {nxt:%a %d %b}".upper()}


def render_departures(a, inf):
    back = "?" + urlencode({"airport": a["iata"]})
    st.markdown(f'<div class="back"><a href="{back}" target="_self">← {inf["city"]} airport</a></div>',
                unsafe_allow_html=True)
    live_header(a, inf)
    now = datetime.now(ZoneInfo(inf["tz"]))
    today = now.date()
    from datetime import timedelta as _td
    items = []
    with loading():
        items += [(f, today) for f in board_predictions(a["iata"], today.isoformat(), max(0, now.hour - 1), 24)]
        tm = today + _td(days=1)
        items += [(f, tm) for f in board_predictions(a["iata"], tm.isoformat(), 0, now.hour + 1)]
    from views.dep_board import dep_board
    dep_board(board_payload24(a, inf, items, now), key=f"db_{a['iata']}")


# ---------------- page ----------------
@st.fragment(run_every=30)
def live_header(a, inf):
    box("ap_head", header_html(a, inf))


def au_cancel_html(code, month, note):
    try:
        r = pd.read_csv(os.path.join(DATA, "au_routes.csv"))
    except Exception:
        return ""
    r = r[(r.origin == code) & (r.airline == "ALL")]
    x = r[r.Month_Num == month] if (r.Month_Num == month).any() else r
    sch, can = x.Sectors_Scheduled.sum(), x.Cancellations.sum()
    if not sch:
        return ""
    pct = 100 * can / sch
    odds = f"1 in {max(2, round(sch / can))}" if can else "None"
    return (f'<div class="ct">{IC_UP} Cancellations</div><div class="cs">{note}</div>'
            f'<div style="font-size:2.6rem;font-weight:700;color:#111418;margin-top:14px">{pct:.1f}%</div>'
            f'<div class="cs">{odds} departures cancelled · {int(can):,} of {int(sch):,}</div>'
            '<div class="sub-h">Cancellations by month</div>')


def au_cancel_chart(code, month):
    try:
        r = pd.read_csv(os.path.join(DATA, "au_routes.csv"))
    except Exception:
        return None
    r = r[(r.origin == code) & (r.airline == "ALL")]
    g = r.groupby("Month_Num").agg(c=("Cancellations", "sum"), s=("Sectors_Scheduled", "sum")).reset_index()
    g = g[g.s > 0]
    if g.empty:
        return None
    g["v"] = 100 * g.c / g.s
    g["mo"] = g.Month_Num.map(lambda x: MONTHS[int(x) - 1][:3])
    g["col"] = ["#0055A0" if int(x) == month else "#C9DEEE" for x in g.Month_Num]
    g = g[g.Month_Num <= date.today().month]
    g["txt"] = g.v.map(lambda x: f"{x:.1f}% cancelled")
    order = [mo[:3] for mo in MONTHS]
    return alt.Chart(g).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("mo:N", sort=order, scale=alt.Scale(domain=order, paddingInner=0.3), axis=x_axis()),
        y=alt.Y("v:Q", axis=alt.Axis(orient="right", title=None, gridDash=[3, 3], gridColor="#D5DEE8", domain=False, ticks=False, labelColor="#8592A6", labelFontSize=12, tickCount=3, labelExpr="datum.value + '%'")),
        color=alt.Color("col:N", scale=None),
        tooltip=[alt.Tooltip("mo:N", title="Month"), alt.Tooltip("txt:N", title="Departures")]
    ).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)


def ticker_payload(a, inf):
    """Next scheduled departures (today, rolling past midnight) for the live ticker."""
    from datetime import timedelta as _td
    tz = ZoneInfo(inf["tz"])
    now = datetime.now(tz)
    spans = [(now.date(), now.hour, min(24, now.hour + 3))]
    if now.hour + 3 > 24:
        spans.append((now.date() + _td(days=1), 0, now.hour + 3 - 24))
    out = []
    for d, h0, h1 in spans:
        if h1 <= h0:
            continue
        try:
            fl = board_predictions(a["iata"], d.isoformat(), h0, h1)
        except Exception:
            fl = []
        for f in fl:
            hh, mm = divmod(int(f["dep_hhmm"]), 100)
            t = datetime(d.year, d.month, d.day, hh % 24, mm, tzinfo=tz)
            if t < now - _td(minutes=1):
                continue
            level = f["res"]["level"]
            out.append({"t": int(t.timestamp() * 1000), "time": f"{hh % 24:02d}:{mm:02d}", "fl": flight_label(f),
                        "dest": f["dest"], "city": city_of(f["dest"]), "color": LEVEL_COLORS[level],
                        "risk": CHIP[level].format(m=int(round(f["m_late"]))), "logo": logo_html(f["airline"]),
                        "qp": {"page": "predict", "from": a["iata"], "to": f["dest"], "date": d.isoformat(), "flight": f["key"]}})
    out.sort(key=lambda x: x["t"])
    return {"flights": out[:24], "now_ms": int(now.timestamp() * 1000),
            "all_qp": {"airport": a["iata"], "view": "departures"}}


@st.fragment(run_every=600)
def live_ticker(a, inf):
    pl = ticker_payload(a, inf)
    if pl["flights"]:
        from views.dep_ticker import dep_ticker
        dep_ticker(pl, key=f"tk_{a['iata']}")


def render_airport():
    st.markdown(CSS + PAGE_CSS + AP_CSS, unsafe_allow_html=True)
    st.markdown("""<style>
div[data-testid="stHorizontalBlock"]:has(.st-key-pgs_ap_status){align-items:stretch !important;}
div[data-testid="stHorizontalBlock"]:has(.st-key-pgs_ap_status) > div[data-testid="stColumn"],
div[data-testid="stHorizontalBlock"]:has(.st-key-pgs_ap_status) > div[data-testid="stColumn"] div:has([class*="st-key-pg"]){
  display:flex !important;flex-direction:column !important;flex:1 1 auto !important;height:auto !important;}
.st-key-pgs_ap_status,.st-key-pgc_ap_dep,.st-key-pgc_ap_co2{flex:1 1 auto !important;}
.st-key-pgs_ap_status div:has(.status){display:flex !important;flex-direction:column !important;flex:1 1 auto !important;}
.st-key-pgs_ap_status .status{flex:1 1 auto !important;display:flex !important;flex-direction:column !important;}
.st-key-pgs_ap_status .st-body{flex:1 1 auto !important;}
</style>""", unsafe_allow_html=True)
    a = resolve(st.query_params.get("airport"))
    if a is not None and not a["rows"].empty and st.query_params.get("view") == "departures":
        render_departures(a, info(a))
        return
    if a is None or a["rows"].empty:
        st.info("No data for this airport yet.")
        return
    inf = info(a)
    live_header(a, inf)

    today = date.today()
    if "_ap_month_pick" in st.session_state:
        st.session_state["ap_month_sel"] = st.session_state.pop("_ap_month_pick")
    st.session_state.setdefault("ap_month_sel", today.month)
    c0, _ = st.columns([1, 3])
    with c0:
        month = st.selectbox("Month", list(range(1, 13)),
                             format_func=lambda m: MONTHS[m - 1], key="ap_month_sel")
    dm = pr.EU_MONTH_MAP[month] if a["region"] == "EU" else month
    s = month_stats(a["rows"], dm) or month_stats(a["rows"], None)
    yrs = s["years"]
    yr = str(yrs[0]) if len(yrs) == 1 else f"{yrs[0]}–{yrs[-1]}"
    note = (f"BTS · {MONTHS[dm - 1]} {yr}" if a["region"] == "US" else
            f"BITRE · {MONTHS[dm - 1]} {yr}" if a["region"] == "AU" else f"EUROCONTROL · {MONTHS[dm - 1]} {yr}")
    prof = hour_profile(a, month)
    best, _ = best_time(prof)
    worst_txt = worst_time(prof)

    st.markdown(kpi_html(a, s, best, MONTHS[month - 1]), unsafe_allow_html=True)
    live_ticker(a, inf)
    _cols = st.columns(3 if a["region"] == "AU" else 2, gap="medium")
    c1, c2 = _cols[0], _cols[1]
    c3 = _cols[2] if a["region"] == "AU" else st.container()
    with c1:
        st.container(key="pgs_ap_status").markdown(status_html(a, inf, s, MONTHS[month - 1]), unsafe_allow_html=True)
    with c2:
        now_h = datetime.now(ZoneInfo(inf["tz"])).hour
        f = {"origin": a["iata"], "dep_hhmm": now_h * 100, "region": a["region"], "svc": (None, a["icao"])}
        top, chart, _ = airport_card(f, date(today.year, month, 15))
        c = box("ap_dep", top if top else f'<div class="ct">{IC_UP} {inf["city"]} departures</div>'
                                          '<div class="cs">No hourly data for this month.</div>')
        if chart is not None:
            c.altair_chart(chart, use_container_width=True, theme=None)
    with c3:
        if a["region"] == "AU":
            c = box("ap_co2", au_cancel_html(a["iata"], month, note))
            ch = au_cancel_chart(a["iata"], month)
            if ch is not None:
                c.altair_chart(ch, use_container_width=True, theme=None)
        else:
            _cp = climate_payload(a, s, MONTHS[month - 1], inf["tz"])
            if _cp:
                from views.climate_card import climate_card
                climate_card(_cp, key=f"cc_{a['iata']}_{month}")
            else:
                box("ap_co2", climate_html(s, MONTHS[month - 1], note, best, worst_txt))

    c4, c5 = st.container(), st.container()
    with c4:
        head, ch = month_card(a["rows"], dm, note, today.month if a["region"] == "AU" else 12)
        c = box("ap_mon", head)
        if ch is not None:
            ev = c.altair_chart(ch, use_container_width=True, theme=None, on_select="rerun",
                                selection_mode=["ck_m"], key=f"ap_mch_{a['iata']}_{month}")
            try:
                pts = ev["selection"]["ck_m"]
            except Exception:
                pts = []
            if pts and pts[0].get("Month") is not None:
                k = int(pts[0]["Month"])
                if a["region"] == "EU":
                    cand = [m for m, v in pr.EU_MONTH_MAP.items() if v == k]
                    k = k if k in cand else (cand[0] if cand else k)
                if k != month:
                    st.session_state["_ap_month_pick"] = k
                    st.rerun()
    with c5:
        pl = None if a["region"] == "AU" else routes_payload(a, inf, month)
        if pl is None:
            box("ap_routes", routes_html(a, inf, month))
        else:
            from views.route_map import route_map_section
            with st.container(key="ap_routes_v2"):
                route_map_section(pl, key=f"rm_{a['iata']}_{month}")
