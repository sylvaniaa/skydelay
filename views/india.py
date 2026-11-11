import html
import os
from urllib.parse import quote

import altair as alt
import pandas as pd
import streamlit as st

from views.home import fmt, risk

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE, "data", "india_monthly.csv")
ROUTES = os.path.join(BASE, "data", "india_routes.csv")
PALETTE = ["#0055A0", "#12284B", "#D99019", "#D45252", "#6C7BD9", "#2C9A69", "#9B6BC4", "#8896A3"]
METRICS = {"On-time %": "otp_pct", "Expected delay (min)": "exp_delay_min", "CO₂ (t)": "co2_tonnes"}

DETAIL_CSS = """
<style>
.in-back{margin:28px 0 4px 0;font-size:.9rem;}
.in-back a{color:#0055A0 !important;text-decoration:none !important;font-weight:600;}
.in-tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:16px;}
.in-tile{background:#FFFFFF;border-radius:20px;box-shadow:0 12px 32px rgba(11,31,51,.08);padding:20px 22px;}
.in-tile .k{color:#111418;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;font-weight:600;}
.in-tile .v{color:#111418;font-size:1.9rem;font-weight:700;letter-spacing:-.02em;margin-top:6px;}
.in-tile .s{color:#111418;font-size:.8rem;margin-top:2px;}
@media (max-width:900px){.in-tiles{grid-template-columns:repeat(2,1fr);}}
</style>
"""


@st.cache_data(show_spinner=False)
def _load():
    df = pd.read_csv(PATH)
    df["date"] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1))
    return df


@st.cache_data(show_spinner=False)
def _routes():
    r = pd.read_csv(ROUTES)
    return r[r.pax > 0].copy()


@st.cache_data(show_spinner=False)
def _cities():
    r = _routes()
    a = r.rename(columns={"city1": "city", "city2": "other"})[["city", "other", "pax", "mult"]]
    b = r.rename(columns={"city2": "city", "city1": "other"})[["city", "other", "pax", "mult"]]
    x = pd.concat([a, b]).sort_values("pax", ascending=False)
    x["w"] = x.mult * x.pax
    g = x.groupby("city").agg(pax=("pax", "sum"), routes=("other", "nunique"), w=("w", "sum"),
                              busiest=("other", "first"), busiest_pax=("pax", "first")).reset_index()
    g["mult"] = g.w / g.pax
    return g.sort_values("pax", ascending=False).reset_index(drop=True)


def _cong(m):
    if m >= 1.05:
        return "#D45252", "High"
    if m >= 0.9:
        return "#D99019", "Moderate"
    return "#2C9A69", "Low"


def india_months():
    try:
        df = _load()
    except Exception:
        return [], 0
    m = df[["Year", "Month", "date"]].drop_duplicates().sort_values("date", ascending=False)
    months = [(int(a), int(b)) for a, b in zip(m.Year, m.Month)]
    cover = df.groupby(["Year", "Month"]).n_days.median()
    default = 0
    for i, ym in enumerate(months):
        if cover.get(ym, 0) >= 20:
            default = i
            break
    return months, default


def render_india(year, month, q=""):
    view = st.segmented_control("View", ["Cities", "Airlines"], default="Cities",
                                key="in_view", label_visibility="collapsed")
    if view == "Airlines":
        _render_airlines(year, month, q)
    else:
        _render_cities(q)


def _render_cities(q):
    g = _cities()
    if q and q.strip():
        g = g[g.city.str.lower().str.contains(q.strip().lower())]
    if g.empty:
        st.warning("No cities match your search.")
        return
    rows = []
    for _, r in g.head(60).iterrows():
        color, label = _cong(r.mult)
        rows.append(
            '<tr>'
            '<td><a class="ap-link" href="?city=' + quote(r.city) + '" target="_self"><span>'
            '<span class="ap-name">' + html.escape(r.city) + '</span>'
            '<span class="ap-city">' + str(int(r.routes)) + ' connected cities</span></span></a></td>'
            '<td><b>' + fmt(r.pax / 1e6, ",.1f", " M") + '</b><span class="sub">passengers per year</span></td>'
            '<td><b>' + html.escape(r.busiest) + '</b>'
            '<span class="sub">' + fmt(r.busiest_pax / 1e6, ",.1f", " M passengers") + '</span></td>'
            '<td><b>' + fmt(r.mult, ".2f", "×") + '</b><span class="sub">congestion index</span></td>'
            '<td><span class="dot" style="background:' + color + '"></span>' + label + '</td>'
            '</tr>')
    st.markdown(
        '<div class="ap-card"><table class="ap-table"><thead><tr>'
        '<th>Airport / city</th><th>Passengers</th><th>Busiest route to</th>'
        '<th>Congestion</th><th>Level</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table></div>'
        '<div class="legend">Showing ' + str(min(60, len(g))) + ' of ' + str(len(g)) + ' cities, busiest first. '
        'DGCA publishes delay per airline, not per airport, so delay and CO₂ are on the Airlines view. '
        'Passengers = all routes touching the city (domestic, last 12 months: Aug 2025–Jul 2026). '
        'Congestion = passenger-weighted route multiplier (≥1.05 high, 0.90–1.05 moderate, &lt;0.90 low).</div>',
        unsafe_allow_html=True)


def _render_airlines(year, month, q):
    df = _load()
    cur = df[(df.Year == year) & (df.Month == month)].copy()
    cur = cur.sort_values("departures", ascending=False)
    if q and q.strip():
        cur = cur[cur.Airline.str.lower().str.contains(q.strip().lower())]
    if cur.empty:
        st.warning("No airlines match your search.")
        return

    rows = []
    for _, r in cur.iterrows():
        color, label = risk(r.otp_pct / 100.0)
        partial = ""
        if r.n_days < r.days_in_month:
            partial = "{} of {} days of data".format(int(r.n_days), int(r.days_in_month))
        link = "?airline=" + quote(r.Airline)
        rows.append(
            '<tr>'
            '<td><a class="ap-link" href="' + link + '" target="_self"><span>'
            '<span class="ap-name">' + html.escape(r.Airline) + '</span>'
            '<span class="ap-city">' + partial + '</span></span></a></td>'
            '<td><b>' + fmt(r.departures, ",.0f") + '</b><span class="sub">flights in month</span></td>'
            '<td><b>' + fmt(r.exp_delay_min, ".0f", " min") + '</b>'
            '<span class="sub">' + fmt(r.otp_pct, ".1f", "% on time") + '</span></td>'
            '<td><b>' + fmt(r.co2_tonnes, ",.0f", " t") + '</b></td>'
            '<td><span class="dot" style="background:' + color + '"></span>' + label + '</td>'
            '</tr>')

    st.markdown(
        '<div class="ap-card"><table class="ap-table"><thead><tr>'
        '<th>Airline</th><th>Departures</th><th>Expected delay*</th>'
        '<th>Est. CO₂</th><th>Delay risk</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table></div>'
        '<div class="legend">*Proxy estimated from OTP. CO₂ = average daily extra CO₂ × days in month. '
        'Alliance Air is excluded from CO₂ (turboprop fleet). Click an airline for its monthly detail. '
        'Risk dot = on-time percentage (≥82% low, 75–82% moderate, &lt;75% high).</div>',
        unsafe_allow_html=True)

    st.markdown("&nbsp;")
    with st.container(key="card_in_trend"):
        st.markdown("**Trend by airline**")
        metric = st.segmented_control(
            "Metric", list(METRICS.keys()),
            default="On-time %", key="in_metric", label_visibility="collapsed")
        if metric is None:
            metric = "On-time %"
        col = METRICS[metric]
        t = df.dropna(subset=[col]).copy()
        order = sorted(t.Airline.unique())
        chart = (
            alt.Chart(t)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y", labelColor="#5B6880")),
                y=alt.Y(col + ":Q", title=None, scale=alt.Scale(zero=(col != "otp_pct")),
                        axis=alt.Axis(labelColor="#5B6880", gridColor="#E6ECEF")),
                color=alt.Color("Airline:N",
                                scale=alt.Scale(domain=order, range=PALETTE[:len(order)]),
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("Airline:N"),
                         alt.Tooltip("date:T", title="Month", format="%b %Y"),
                         alt.Tooltip(col + ":Q", title=metric, format=",.1f")],
            )
            .properties(height=320)
            .configure(background="transparent")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption("Coverage differs by year: 2021 (6 months), 2022 (8), 2023–2024 (12), 2025 (11), 2026 (6).")


AIRLINE_IATA = {"indigo": "6E", "air india": "AI", "spicejet": "SG", "vistara": "UK",
    "akasa air": "QP", "air india express": "IX", "alliance air": "9I", "air asia": "I5",
    "airasia india": "I5", "go first": "G8", "goair": "G8", "star air": "S5",
    "fly91": "IC", "flybig": "S9"}


def _iata(a):
    return AIRLINE_IATA.get(str(a).strip().lower(), str(a)[:2].upper())


AIRLINE_NAME = {"indigo": "IndiGo", "spicejet": "SpiceJet", "air india": "Air India", "vistara": "Vistara",
    "akasa air": "Akasa Air", "air india express": "Air India Express", "alliance air": "Alliance Air",
    "air asia": "AirAsia India", "airasia india": "AirAsia India", "go first": "Go First", "goair": "Go First",
    "star air": "Star Air", "fly91": "Fly91", "flybig": "Flybig"}


def _aname(a):
    return AIRLINE_NAME.get(str(a).strip().lower(), str(a).strip().title())


def _pick_month(ev, name, key="in_month_sel"):
    try:
        pts = ev["selection"][name]
    except Exception:
        return
    if pts and isinstance(pts, list) and pts[0].get("Month") is not None:
        m = int(pts[0]["Month"])
        if m != st.session_state.get(key):
            st.session_state["_" + key.replace("_sel", "_pick")] = m
            st.rerun()


def render_city(name):
    """India city page, same layout as the US/Europe airport page. DGCA has no airport-level delays,
    so on-time = India on-time for the month / this city's route congestion, and delay CO2 =
    India total x this city's share of passengers (both labelled as estimates)."""
    from datetime import date, datetime
    from urllib.parse import urlencode
    from zoneinfo import ZoneInfo

    from core.weather import day_weather
    from views.airport import AP_CSS, BUSY, MONTHS, _deg, _home, climate_html, level_of, month_card
    from views.flight import (CSS, IC_CLOCK, IC_CLOUD, IC_UP, LEVEL_COLORS, LEVEL_HALO, LEVEL_TEXT, PAGE_CSS,
                              TINT, box, dur_words, hb_row, in_ten, logo_html, x_axis)

    st.markdown(CSS + PAGE_CSS + AP_CSS, unsafe_allow_html=True)
    g = _cities()
    row = g[g.city == name]
    if row.empty:
        st.info("No data for this city yet.")
        return
    c = row.iloc[0]
    mult = float(c.mult)
    share = float(c.pax) / float(g.pax.sum())
    hr = next((r for r in _home().values() if str(getattr(r, "page", "")) == "city:" + name), None)
    code = str(hr.code) if hr is not None else name[:3].upper()
    cong_lv = _cong(mult)[1]
    try:
        w = day_weather(float(hr.lat), float(hr.lon), date.today()) if hr is not None else None
    except Exception:
        w = None

    # ---------- header ----------
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    wx = f' · {w["icon"]} {_deg(w["t_max"])}° {w["text"]}' if w else ""
    pill = ""
    try:
        word, key = BUSY[int(float(hr.busy_level))]
        bt = str(getattr(hr, "busy_txt", "") or "")
        bt = f" · {bt}" if bt and bt != "nan" else ""
        pill = (f'<span class="risk-tag" style="background:{LEVEL_HALO[key]};color:{LEVEL_TEXT[key]}">'
                f'<span class="rdot" style="background:{LEVEL_COLORS[key]}"></span>{word.upper()}{bt}</span>')
    except Exception:
        pass
    box("in_head", f'<div class="h-row"><div class="ap-code">{html.escape(code)}</div>'
                   f'<div><div class="pg-title">{html.escape(name)}</div>'
                   '<div class="pg-sub">India</div></div>'
                   f'<div style="margin-left:auto">{pill}</div></div>'
                   f'<div class="h-row" style="margin-top:14px"><div class="pg-sub">🕐 {now:%H:%M} India time{wx}</div></div>')

    today = date.today()
    if "_in_month_pick" in st.session_state:
        st.session_state["in_month_sel"] = st.session_state.pop("_in_month_pick")
    st.session_state.setdefault("in_month_sel", today.month)
    c0, _ = st.columns([1, 3])
    with c0:
        month = st.selectbox("Month", list(range(1, 13)),
                             format_func=lambda m: MONTHS[m - 1], key="in_month_sel")
    mname = MONTHS[month - 1]

    # ---------- India by month (full months only, scaled to the whole month) ----------
    df = _load()
    full = df[df.n_days >= 20].copy()
    full["dep_full"] = full.departures * full.days_in_month / full.n_days
    nat = (full.assign(w_ot=full.dep_full * full.otp_pct / 100, w_ed=full.dep_full * full.exp_delay_min,
                       w_pd=full.dep_full * full.p_delay)
           .groupby(["Year", "Month"]).agg(n=("dep_full", "sum"), w_ot=("w_ot", "sum"), w_ed=("w_ed", "sum"),
                                           w_pd=("w_pd", "sum"), co2=("co2_tonnes", "sum")).reset_index())
    nat["ot"] = nat.w_ot / nat.n
    sel = nat[nat.Month == month]
    if sel.empty:
        sel = nat
    ot_m = min(1.0, float(sel.w_ot.sum() / sel.n.sum()) / mult)
    late_m = float(sel.w_ed.sum() / sel.w_pd.sum()) if sel.w_pd.sum() > 0 else float("nan")
    co2_m = float(sel.co2.mean()) * share

    # ---------- card 1: status ----------
    level = level_of(ot_m)
    head = {"Low": "Departures usually on time", "Moderate": "Departures mostly on time",
            "High": "Delays are common"}[level]
    bg, foot, dot, link = TINT[level]
    srows = [(IC_UP, "On time", f"{in_ten(ot_m)} departures leave within 15 min in {mname}.")]
    if late_m == late_m:
        srows.append((IC_CLOCK, "Typical delay", f"Typically late about {dur_words(late_m)}."))
    if w:
        wtxt = f'{w["text"]}, {_deg(w["t_max"])}° / {_deg(w["t_min"])}°C.'
        if w.get("warnings"):
            wtxt += f'<div class="ap-warn">⚠️ {", ".join(w["warnings"])}</div>'
        srows.append((IC_CLOUD, "Weather today", wtxt))
    body = "".join(f'<div class="st-row"><div class="st-ic">{ic}</div><div><div class="st-k">{k}</div>'
                   f'<div class="st-v">{v}</div></div></div>' for ic, k, v in srows)
    status = (f'<div class="status" style="background:{bg}"><div class="st-body">'
              f'<div class="st-title"><span class="st-dot" style="background:{dot};box-shadow:0 0 0 5px {foot}"></span>'
              f'{head}</div>{body}</div>'
              '</div>')

    # ---------- card 2: traffic ----------
    stats = ('<div class="stats4">'
             '<div class="s4"><div class="s4-l"><span class="vb" style="background:#0055A0"></span>Passengers / year</div>'
             f'<div class="s4-v">{c.pax / 1e6:,.0f}M</div></div>'
             '<div class="s4"><div class="s4-l"><span class="vb" style="background:#0055A0"></span>Routes</div>'
             f'<div class="s4-v">{int(c.routes)}</div></div>'
             '</div>')
    traffic = (f'<div class="ct">{IC_UP} {html.escape(name)} traffic</div>' + stats +
               '<div class="sub-h">Flights across India by month</div>')
    order = [mo[:3] for mo in MONTHS]
    tr = nat.groupby("Month").n.mean().reset_index()
    tr["mo"] = tr.Month.map(lambda x: MONTHS[int(x) - 1][:3])
    tr["c"] = ["#0055A0" if int(x) == month else "#C9DEEE" for x in tr.Month]
    tr["txt"] = tr.n.map(lambda x: f"{x:,.0f} flights")
    hv_in = alt.selection_point(on="pointerover", clear="pointerout", fields=["mo"], empty=False)
    ck_in = alt.selection_point(on="click", fields=["Month"], name="ck_in")
    tch = alt.Chart(tr).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, cursor="pointer").encode(
        x=alt.X("mo:N", sort=order, scale=alt.Scale(domain=order, paddingInner=0.3), axis=x_axis()),
        y=alt.Y("n:Q", axis=alt.Axis(orient="right", format="~s", title=None, gridDash=[3, 3], gridColor="#D5DEE8",
                                     domain=False, ticks=False, labelColor="#8592A6", labelFontSize=12, tickCount=3)),
        color=alt.condition(hv_in, alt.value("#003F7A"), alt.Color("c:N", scale=None)),
        tooltip=[alt.Tooltip("mo:N", title="Month"), alt.Tooltip("txt:N", title="Flights in India")],
    ).add_params(hv_in, ck_in).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)

    # ---------- card 3: climate ----------
    climate = climate_html({"co2": co2_m}, mname, "", None, "")

    # ---------- bottom left: month by month (estimate for this city) ----------
    rows_m = pd.DataFrame({"Year": nat.Year, "Month": nat.Month,
                           "pct_dep_ontime": (nat.ot / mult).clip(upper=1.0), "n_dep": nat.n})
    mhead, mch = month_card(rows_m, month, "")

    # ---------- bottom right: where you can fly ----------
    rt = _routes()
    mm = rt[(rt.city1 == name) | (rt.city2 == name)].copy()
    mm["other"] = [b if a == name else a for a, b in zip(mm.city1, mm.city2)]
    mm = mm.sort_values("pax", ascending=False).head(8)
    codes = {str(getattr(r, "page", ""))[5:]: str(r.code) for r in _home().values()
             if str(getattr(r, "page", "")).startswith("city:")}
    mx = float(mm.pax.max()) if len(mm) else 1.0
    drows = "".join(
        hb_row("?" + urlencode({"city": x.other}), "",
               html.escape(codes.get(x.other, x.other[:3].upper())), html.escape(x.other[:18]),
               6 + 94 * x.pax / mx, "#0055A0", f"{x.pax / 1e6:.1f}M",
               f"<b>{html.escape(name)} ⇄ {html.escape(x.other)}</b>{x.pax / 1e6:,.2f} M passengers a year · tap for city", False)
        for x in mm.itertuples())
    am = full[full.Month == month]
    if am.empty:
        am = full[full.date == full.date.max()]
    am = am[am.Year == am.Year.max()].sort_values("otp_pct", ascending=False).head(6)
    alabel = f"{MONTHS[int(am.Month.iloc[0]) - 1][:3]} {int(am.Year.iloc[0])}" if len(am) else ""
    arows = "".join(
        hb_row("?" + urlencode({"airline": r.Airline}), logo_html(_iata(r.Airline)), html.escape(_aname(r.Airline)[:18]), "",
               max(6.0, min(100.0, 6 + 94 * (r.otp_pct / 100 - 0.5) / 0.5)), LEVEL_COLORS[level_of(r.otp_pct / 100)],
               f"{r.otp_pct:.0f}%", f"<b>{html.escape(_aname(r.Airline))}</b>{r.otp_pct:.1f}% on time across India in {alabel}",
               False)
        for r in am.itertuples()) or '<div class="cs">Not enough data to compare airlines.</div>'
    routes = (f'<div class="ct">{IC_UP} Where you can fly</div>'
              '<div class="lists2">'
              '<div><div class="hb-h"><span class="hb-t">Top destinations</span></div>' + drows + '</div>'
              '<div><div class="hb-h"><span class="hb-t">Most reliable airlines</span></div>' + arows + '</div></div>')

    # ---------- layout (same as the US/Europe airport page) ----------
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.container(key="pgs_in_status").markdown(status, unsafe_allow_html=True)
    with c2:
        cc = box("in_dep", traffic)
        ev = cc.altair_chart(tch, use_container_width=True, theme=None, on_select="rerun",
                             selection_mode=["ck_in"], key=f"in_tch_{month}")
        _pick_month(ev, "ck_in")
    with c3:
        box("in_co2", climate)
    c4, c5 = st.columns([1, 2], gap="medium")
    with c4:
        cc = box("in_mon", mhead)
        if mch is not None:
            ev2 = cc.altair_chart(mch, use_container_width=True, theme=None, on_select="rerun",
                                  selection_mode=["ck_m"], key=f"in_mch_{month}")
            _pick_month(ev2, "ck_m")
    with c5:
        box("in_routes", routes)
def render_airline(name):
    """India airline page, same card layout as the city / airport pages (DGCA monthly data)."""
    from datetime import date
    from urllib.parse import urlencode

    from views.airport import AP_CSS, MONTHS, climate_html, level_of, month_card
    from views.flight import (CSS, IC_CLOCK, IC_UP, LEVEL_COLORS, LEVEL_HALO, LEVEL_TEXT, PAGE_CSS,
                              TINT, box, dur_words, hb_row, in_ten, logo_html, x_axis)

    st.markdown(CSS + PAGE_CSS + AP_CSS, unsafe_allow_html=True)
    df = _load()
    d = df[df.Airline.astype(str).str.strip().str.lower() == str(name).strip().lower()]
    if d.empty:
        st.info("No data for this airline yet.")
        return
    raw = d.Airline.iloc[0]
    code, title = _iata(raw), _aname(raw)

    full = df[df.n_days >= 20].copy()
    full["dep_full"] = full.departures * full.days_in_month / full.n_days
    mine = full[full.Airline == raw].copy()
    if mine.empty:
        mine = d.copy()
        mine["dep_full"] = mine.departures

    # ---------- header ----------
    ym = mine.Year * 12 + mine.Month
    rec = mine[ym > ym.max() - 12]
    ot_rec = float((rec.otp_pct * rec.dep_full).sum() / rec.dep_full.sum() / 100)
    lv = level_of(ot_rec)
    word = {"Low": "Usually on time", "Moderate": "Mostly on time", "High": "Often late"}[lv]
    pill = (f'<span class="risk-tag" style="background:{LEVEL_HALO[lv]};color:{LEVEL_TEXT[lv]}">'
            f'<span class="rdot" style="background:{LEVEL_COLORS[lv]}"></span>{ot_rec:.0%} ON TIME</span>')
    box("al_head", f'<div class="h-row"><div style="transform:scale(2.2);transform-origin:left center;margin-right:64px">{logo_html(code)}</div>'
                   f'<div><div class="pg-title">{html.escape(title)}</div>'
                   '<div class="pg-sub">Indian airline</div></div>'
                   f'<div style="margin-left:auto">{pill}</div></div>')

    # ---------- month selector (also set by clicking a bar) ----------
    today = date.today()
    if "_al_month_pick" in st.session_state:
        st.session_state["al_month_sel"] = st.session_state.pop("_al_month_pick")
    st.session_state.setdefault("al_month_sel", today.month)
    c0, _ = st.columns([1, 3])
    with c0:
        month = st.selectbox("Month", list(range(1, 13)), format_func=lambda m: MONTHS[m - 1], key="al_month_sel")
    mname = MONTHS[month - 1]

    sel = mine[mine.Month == month]
    if sel.empty:
        sel = mine
    w = sel.dep_full
    ot_m = float((sel.otp_pct * w).sum() / w.sum() / 100)
    pdw = float((sel.p_delay * w).sum())
    late_m = float((sel.exp_delay_min * w).sum()) / pdw if pdw > 0 else float("nan")
    dep_m = float(sel.groupby("Year").dep_full.sum().mean())
    co2_m = float(sel.co2_tonnes.mean()) if sel.co2_tonnes.notna().any() else None
    allm = full[(full.Month == month) & (full.Year.isin(sel.Year))]
    share = float(sel.dep_full.sum() / allm.dep_full.sum()) if len(allm) else float("nan")

    # ---------- card 1: status ----------
    level = level_of(ot_m)
    head = {"Low": "Usually on time", "Moderate": "Mostly on time", "High": "Delays are common"}[level]
    bg, foot, dot, link = TINT[level]
    srows = [(IC_UP, "On time", f"{in_ten(ot_m)} {html.escape(title)} flights leave within 15 min in {mname}.")]
    if late_m == late_m:
        srows.append((IC_CLOCK, "Typical delay", f"When late, typically about {dur_words(late_m)}."))
    body = "".join(f'<div class="st-row"><div class="st-ic">{ic}</div><div><div class="st-k">{k}</div>'
                   f'<div class="st-v">{v}</div></div></div>' for ic, k, v in srows)
    status = (f'<div class="status" style="background:{bg}"><div class="st-body">'
              f'<div class="st-title"><span class="st-dot" style="background:{dot};box-shadow:0 0 0 5px {foot}"></span>'
              f'{head}</div>{body}</div>'
              '</div>')

    # ---------- card 2: flights ----------
    sh = f"{share:.0%}" if share == share else "–"
    stats = ('<div class="stats4">'
             '<div class="s4"><div class="s4-l"><span class="vb" style="background:#0055A0"></span>Flights</div>'
             f'<div class="s4-v">{dep_m / 1000:,.1f}k</div></div>'
             '<div class="s4"><div class="s4-l"><span class="vb" style="background:#0055A0"></span>Market share</div>'
             f'<div class="s4-v">{sh}</div></div></div>')
    traffic = f'<div class="ct">{IC_UP} {html.escape(title)} flights</div>' + stats + '<div class="sub-h">Flights by month</div>'
    order = [mo[:3] for mo in MONTHS]
    tr = mine.groupby("Month").dep_full.mean().reset_index().rename(columns={"dep_full": "n"})
    tr["mo"] = tr.Month.map(lambda x: MONTHS[int(x) - 1][:3])
    tr["c"] = ["#0055A0" if int(x) == month else "#C9DEEE" for x in tr.Month]
    tr["txt"] = tr.n.map(lambda x: f"{x:,.0f} flights")
    hv = alt.selection_point(on="pointerover", clear="pointerout", fields=["mo"], empty=False)
    ck = alt.selection_point(on="click", fields=["Month"], name="ck_al")
    tch = alt.Chart(tr).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, cursor="pointer").encode(
        x=alt.X("mo:N", sort=order, scale=alt.Scale(domain=order, paddingInner=0.3), axis=x_axis()),
        y=alt.Y("n:Q", axis=alt.Axis(orient="right", format="~s", title=None, gridDash=[3, 3], gridColor="#D5DEE8",
                                     domain=False, ticks=False, labelColor="#8592A6", labelFontSize=12, tickCount=3)),
        color=alt.condition(hv, alt.value("#003F7A"), alt.Color("c:N", scale=None)),
        tooltip=[alt.Tooltip("mo:N", title="Month"), alt.Tooltip("txt:N", title="Flights")],
    ).add_params(hv, ck).properties(height=170).configure(font="Plus Jakarta Sans", background="#FFFFFF").configure_view(strokeWidth=0)

    # ---------- card 3: climate ----------
    if co2_m is not None and co2_m == co2_m:
        climate = climate_html({"co2": co2_m}, mname, "", None, "")
    else:
        climate = (f'<div class="ct">Climate cost of delays</div><div class="cs">Not estimated for {html.escape(title)}: '
                   'its turboprop fleet is not in the ICAO engine emissions databank.</div>')

    # ---------- bottom left: month by month ----------
    rows_m = pd.DataFrame({"Year": mine.Year, "Month": mine.Month,
                           "pct_dep_ontime": (mine.otp_pct / 100).clip(upper=1.0), "n_dep": mine.dep_full})
    mhead, mch = month_card(rows_m, month, "")

    # ---------- bottom right: how it compares ----------
    cur = full[full.Month == month]
    if cur.empty:
        cur = full
    cur = cur[cur.Year == cur.Year.max()]
    lbl = f"{MONTHS[int(cur.Month.iloc[0]) - 1][:3]} {int(cur.Year.iloc[0])}"
    arows = "".join(
        hb_row("?" + urlencode({"airline": r.Airline}), logo_html(_iata(r.Airline)), html.escape(_aname(r.Airline)[:18]), "",
               max(6.0, min(100.0, 6 + 94 * (r.otp_pct / 100 - 0.5) / 0.5)), LEVEL_COLORS[level_of(r.otp_pct / 100)],
               f"{r.otp_pct:.0f}%", f"<b>{html.escape(_aname(r.Airline))}</b>{r.otp_pct:.1f}% on time in {lbl}",
               False)
        for r in cur.sort_values("otp_pct", ascending=False).itertuples())
    mx = float(cur.dep_full.max()) or 1.0
    frows = "".join(
        hb_row("?" + urlencode({"airline": r.Airline}), logo_html(_iata(r.Airline)), html.escape(_aname(r.Airline)[:18]), "", 6 + 94 * r.dep_full / mx, "#0055A0",
               f"{r.dep_full / 1000:.1f}k", f"<b>{html.escape(_aname(r.Airline))}</b>{r.dep_full:,.0f} flights in {lbl}",
               False)
        for r in cur.sort_values("dep_full", ascending=False).itertuples())
    compare = (f'<div class="ct">{IC_UP} How it compares</div>'
               '<div class="lists2">'
               '<div><div class="hb-h"><span class="hb-t">Most on time</span></div>' + arows + '</div>'
               '<div><div class="hb-h"><span class="hb-t">Most flights</span></div>' + frows + '</div></div>')

    # ---------- layout ----------
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.container(key="pgs_al_status").markdown(status, unsafe_allow_html=True)
    with c2:
        cc = box("al_dep", traffic)
        ev = cc.altair_chart(tch, use_container_width=True, theme=None, on_select="rerun",
                             selection_mode=["ck_al"], key=f"al_tch_{month}")
        _pick_month(ev, "ck_al", "al_month_sel")
    with c3:
        box("al_co2", climate)
    c4, c5 = st.columns([1, 2], gap="medium")
    with c4:
        cc = box("al_mon", mhead)
        if mch is not None:
            ev2 = cc.altair_chart(mch, use_container_width=True, theme=None, on_select="rerun",
                                  selection_mode=["ck_m"], key=f"al_mch_{month}")
            _pick_month(ev2, "ck_m", "al_month_sel")
    with c5:
        box("al_cmp", compare)
