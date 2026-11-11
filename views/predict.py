from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core import data as dl
from core import predict as pr

PREDICT_CSS = """
<style>
.hero{padding:36px 0 8px 0;}
.hero-title{font-size:2.5rem;font-weight:700;color:#111418;letter-spacing:-.02em;}
.hero-sub{color:#111418;font-size:1.05rem;margin-top:6px;max-width:760px;}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:10px;}
.pred-level{font-size:1.5rem;font-weight:600;color:#111418;margin-bottom:16px;}
.pred-sub{font-size:1.05rem;color:#111418;margin-top:22px;line-height:1.5;}
</style>
"""

LEVEL_COLORS = {"Low": "#2C9A69", "Moderate": "#D99019", "High": "#D45252"}
AX = dict(domain=False, gridColor="#E2E6EC", labelColor="#5B6880", titleColor="#5B6880", tickColor="#E2E6EC")


def hour_text(h):
    return str(h % 12 or 12) + ":00 " + ("AM" if h < 12 else "PM")


def airport_label(code):
    return code + "  ·  " + dl.airport_info(code)["name"]


@st.cache_data(show_spinner=False)
def hourly_profile(origin, dest, airline, family, date_iso):
    d = date.fromisoformat(date_iso)
    rows = []
    for h in range(5, 24):
        r = pr.predict(origin, dest, airline, d, h, family)
        rows.append({"hour": h, "label": dl.hour_label(h), "prob": r["prob_delay15"] * 100})
    return pd.DataFrame(rows)


def minutes_text(m):
    if abs(m) < 1:
        return "about on time"
    if m < 0:
        return "about " + format(abs(m), ".0f") + " min early"
    return "about " + format(m, ".0f") + " min late"


def render_predict():
    st.markdown(PREDICT_CSS, unsafe_allow_html=True)
    st.markdown('<div class="back"><a href="/" target="_self">← All airports</a></div>', unsafe_allow_html=True)
    st.markdown('<div class="hero"><div class="hero-title">Check a flight</div>'
                '<div class="hero-sub">Delay risk for a scheduled US domestic flight, estimated from historical '
                'patterns (Jan 2023 – Mar 2025). Uses only what is known when a flight is scheduled — '
                'no weather and no live data.</div></div>', unsafe_allow_html=True)

    origins = pr.origins()
    with st.container(key="card_form"):
        c1, c2, c3, c4 = st.columns([1.3, 1.3, 1, 1])
        with c1:
            origin = st.selectbox("From", origins, index=origins.index("ORD") if "ORD" in origins else 0,
                                  format_func=airport_label)
        dests = pr.destinations(origin)
        with c2:
            dest = st.selectbox("To", dests, index=dests.index("LAX") if "LAX" in dests else 0,
                                format_func=airport_label, key="dest_" + origin)
        with c3:
            flight_date = st.date_input("Date", value=date.today() + timedelta(days=30),
                                        min_value=date.today(),
                                        max_value=date.today() + timedelta(days=365))
        with c4:
            hour = st.selectbox("Scheduled departure", list(range(5, 24)), index=4, format_func=hour_text)

        c5, c6, _ = st.columns([1.3, 1.3, 2])
        airlines = pr.airlines_for(origin, dest)
        with c5:
            airline = st.selectbox("Airline", airlines,
                                   format_func=lambda a: pr.carrier_name(a) + " (" + a + ")",
                                   key="air_" + origin + dest)
        with c6:
            family = st.selectbox("Aircraft", [None] + pr.families(),
                                  format_func=lambda f: "Any / not sure" if f is None else f)

    res = pr.predict(origin, dest, airline, flight_date, hour, family)
    if res is None:
        st.warning("No data for this route.")
        return

    p = res["prob_delay15"] * 100
    base = res["base_rate"] * 100
    color = LEVEL_COLORS[res["level"]]

    left, right = st.columns([1, 1.3])
    with left:
        with st.container(key="card_result"):
            st.markdown(
                '<div class="pred-level"><span class="dot" style="background:' + color + '"></span>'
                + res["level"] + ' delay risk</div>'
                '<div class="stat">' + format(p, ".0f") + '%</div>'
                '<div class="stat-label">CHANCE OF ARRIVING MORE THAN 15 MIN LATE</div>'
                '<div class="bar"><span style="width:' + format(min(p, 100), ".1f") + '%;background:' + color + '"></span></div>'
                '<div class="note">Average for US domestic flights: ' + format(base, ".0f") + '% · this flight is '
                + format(res["ratio"], ".1f") + '× the average</div>'
                '<div class="pred-sub">The model\'s typical expectation for this flight is to arrive <b>'
                + minutes_text(res["expected_minutes"]) + '</b> (low confidence).</div>'
                '<div class="note">' + format(res["distance"], ",.0f") + ' miles · '
                + dl.airport_info(origin)["city"] + ' → ' + dl.airport_info(dest)["city"] + '</div>',
                unsafe_allow_html=True)
    with right:
        with st.container(key="card_profile"):
            st.markdown('<div class="card-title">Same flight, other departure times</div>'
                        '<div class="note">Chance of arriving more than 15 min late. Teal = your selection, '
                        'dashed line = US average.</div>', unsafe_allow_html=True)
            prof = hourly_profile(origin, dest, airline, family, flight_date.isoformat())
            base_df = pd.DataFrame({"y": [base]})
            bars = (alt.Chart(prof).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                    .encode(x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("prob:Q", title="Chance (%)"),
                            color=alt.condition(alt.datum.hour == hour, alt.value("#0055A0"), alt.value("#DCE4E8")),
                            tooltip=[alt.Tooltip("label:N", title="Departure"),
                                     alt.Tooltip("prob:Q", title="Chance (%)", format=".1f")]))
            rule = alt.Chart(base_df).mark_rule(color="#D99019", strokeDash=[5, 4]).encode(y="y:Q")
            chart = (alt.layer(bars, rule).properties(height=260)
                     .configure(background="transparent").configure_view(strokeWidth=0).configure_axis(**AX))
            st.altair_chart(chart, theme=None, use_container_width=True)

    # ---------------- CO2 if delayed ----------------
    with st.container(key="card_co2p"):
        st.markdown('<div class="card-title">CO₂ if delayed</div>', unsafe_allow_html=True)
        delay_min = st.slider("If the flight ends up delayed by (minutes)", 15, 180, 35, step=5)
        kg = pr.delay_co2_kg(family, delay_min)
        exp_kg = kg * res["prob_delay15"]
        fuel = pr.fuel_rate(family)
        aircraft_text = "average of common aircraft" if family is None else family
        st.markdown(
            '<div class="stat-row">'
            '<div><div class="stat">' + format(kg, ",.0f") + ' kg</div>'
            '<div class="stat-label">EXTRA CO₂ IF DELAYED ' + str(delay_min) + ' MIN</div></div>'
            '<div><div class="stat">' + format(exp_kg, ",.0f") + ' kg</div>'
            '<div class="stat-label">RISK-WEIGHTED EXPECTATION PER FLIGHT</div></div>'
            '</div>'
            '<div class="note">Fuel burn ' + format(fuel, ",.0f") + ' kg/h (' + aircraft_text + ') × delay × '
            '3.16 kg CO₂ per kg fuel. Upper-bound: assumes engines run for the whole delay. '
            'A typical late US flight is delayed about 35 min.</div>', unsafe_allow_html=True)

    meta = pr._load()[2]
    st.caption("How to read this: the model separates riskier from safer flights only modestly "
               "(AUC " + format(meta["metrics"]["clf_auc"], ".2f") + " on a Jan–Mar 2025 hold-out). "
               "It does not know the weather or whether the aircraft arrives late from an earlier flight, so "
               "treat it as a risk indicator, not a promise.")