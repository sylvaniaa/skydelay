import altair as alt
import pandas as pd
import streamlit as st

from core import data as dl

st.set_page_config(page_title="SkyDelay", layout="wide", initial_sidebar_state="collapsed")
from core.loader import HTML as _LOADER_HTML
_boot = st.empty()
_boot.markdown(_LOADER_HTML, unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] *, button, input, label { font-family: 'Plus Jakarta Sans', sans-serif !important; }
.fc-time,.bk-t b,.s4-v,.go-n{font-weight:600 !important;font-variant-numeric:tabular-nums;letter-spacing:-.02em;}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; max-width: 1280px; }

.stApp{overflow-x:hidden;background:#F3F8FB;}
.topbar{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;background:#12284B;
  border-radius:999px;height:56px;padding:0 28px;margin:14px 0 10px 0;}
[data-testid="stMainBlockContainer"], .block-container{padding-top:0 !important;}
.topbar a{text-decoration:none !important;}
.sd-side{display:flex;align-items:center;gap:26px;}
.sd-side.r{justify-content:flex-end;}
.sd-link{color:#fff !important;font-size:.72rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  padding:4px 0;border-bottom:1.5px solid transparent;opacity:.85;}
.sd-link:hover{opacity:1;}
.sd-link.on{opacity:1;border-bottom-color:#fff;}
.sd-brand{color:#fff !important;font-size:1.65rem;font-weight:700;letter-spacing:-.04em;line-height:1;}
.sd-search{display:flex;align-items:center;gap:6px;margin:0;}
.sd-search svg{width:14px;height:14px;color:#fff;flex:none;}
.sd-search input{border:none;background:transparent;outline:none;color:#fff;font-size:.72rem;font-weight:600;
  letter-spacing:.14em;text-transform:uppercase;width:90px;transition:width .2s;}
.sd-search input::placeholder{color:rgba(255,255,255,.85);opacity:1;}
.sd-search input:focus{width:170px;text-transform:none;letter-spacing:0;font-size:.85rem;}
@media (max-width:800px){.topbar{display:flex;flex-wrap:wrap;justify-content:center;gap:10px 18px;height:auto;
  padding:12px 18px;border-radius:24px;}.sd-brand{width:100%;text-align:center;order:-1;}}
.back{margin:20px 0 12px 0;font-weight:600;font-size:.9rem;}
.airport-head{display:flex;align-items:center;gap:24px;margin-bottom:8px;}
.airport-code{font-size:5rem;font-weight:700;letter-spacing:-.04em;color:#111418;line-height:1;}
.divider{width:1px;height:64px;background:#DCE4E8;}
.airport-name{font-size:1.5rem;font-weight:600;color:#111418;}
.airport-city{color:#111418;font-size:1rem;margin-top:2px;}
.badge{display:inline-block;margin-top:8px;background:#DCEAF6;color:#003F7A;
       border-radius:999px;padding:4px 12px;font-size:.75rem;font-weight:600;}

.card{background:#FFFFFF;border-radius:20px;box-shadow:0 12px 32px rgba(11,31,51,.08);
      padding:28px 32px;margin:20px 0;}
.card.cream{background:#F5F9FC;}
[class*="st-key-card"]{background:#FFFFFF;border-radius:20px;box-shadow:0 12px 32px rgba(11,31,51,.08);
      padding:28px 32px;margin-bottom:8px;}
.card-title{font-size:1.5rem;font-weight:600;color:#111418;margin:0 0 20px 0;}
.sum-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:32px;}
.sum-item{display:flex;gap:16px;align-items:flex-start;}
.sum-icon{flex:none;width:44px;height:44px;border-radius:50%;background:#DCEAF6;color:#003F7A;
          display:flex;align-items:center;justify-content:center;font-size:1.2rem;font-weight:700;}
.sum-text{font-size:1.05rem;line-height:1.5;color:#111418;}
.sum-link{display:inline-block;margin-top:20px;font-weight:600;font-size:.9rem;}
.card a, .back a { color:#0055A0 !important; text-decoration:none !important; }
.stat-row{display:flex;gap:40px;flex-wrap:wrap;margin-bottom:4px;}
.stat{font-size:3rem;font-weight:700;color:#111418;line-height:1.1;letter-spacing:-.02em;}
.stat-label{font-size:.6875rem;font-weight:600;letter-spacing:.08em;color:#111418;margin-top:4px;}
.bar{display:flex;height:10px;border-radius:999px;overflow:hidden;background:#DCE4E8;margin-top:20px;}
.bar span{display:block;height:100%;}
.note{font-size:.8rem;color:#111418;margin-top:10px;}
.chart-title{font-size:.95rem;font-weight:600;color:#111418;margin:24px 0 4px 0;}
</style>
""", unsafe_allow_html=True)


def fmt(v, spec=",.0f", suffix=""):
    if v is None or pd.isna(v):
        return "–"
    return format(v, spec) + suffix


AX = dict(domain=False, gridColor="#E2E6EC", labelColor="#5B6880", titleColor="#5B6880", tickColor="#E2E6EC")


def bar_chart(df, x, y, color, ytitle, tip):
    ch = (alt.Chart(df)
          .mark_bar(color=color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
          .encode(x=alt.X(x + ":N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
                  y=alt.Y(y + ":Q", title=ytitle),
                  tooltip=[alt.Tooltip(x + ":N", title="Period"),
                           alt.Tooltip(y + ":Q", title=tip, format=",.1f")])
          .properties(height=240)
          .configure(background="transparent")
          .configure_view(strokeWidth=0)
          .configure_axis(**AX))
    st.altair_chart(ch, theme=None, use_container_width=True)


def stats_html(ontime, avg_late, n, kind):
    ok = ontime * 100
    late = 100 - ok
    return (
        '<div class="stat-row">'
        '<div><div class="stat">' + fmt(ok, ".1f", "%") + '</div><div class="stat-label">ON TIME</div></div>'
        '<div><div class="stat">' + fmt(late, ".1f", "%") + '</div><div class="stat-label">DELAYED (&gt;15 MIN)</div></div>'
        '<div><div class="stat">' + fmt(avg_late, ".0f") + '<span style="font-size:1.25rem"> min</span></div>'
        '<div class="stat-label">AVG WHEN DELAYED</div></div>'
        '</div>'
        '<div class="bar"><span style="width:' + str(round(ok, 1)) + '%;background:#2C9A69"></span>'
        '<span style="width:' + str(round(late, 1)) + '%;background:#D99019"></span></div>'
        '<div class="note">' + fmt(n, ",.0f") + ' ' + kind + ' this month · cancelled flights are not in the data</div>'
    )


# ---------------- top bar ----------------
@st.cache_data(show_spinner=False)
def _airport_options():
    import html
    import os
    try:
        h = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "home_airports.csv"))
        h = h[h.region.isin(["US", "EU"])].drop_duplicates("code")
        if "sort" in h.columns:
            h = h.sort_values("sort", ascending=False)
        return "".join(f'<option value="{html.escape(str(c))}" label="{html.escape(str(ci))} · {html.escape(str(n))}"></option>'
                       for c, ci, n in zip(h["code"], h["city"], h["name"]))
    except Exception:
        return ""


_qp = st.query_params
_cur = "predict" if _qp.get("page") in ("flight", "predict") else ("about" if _qp.get("page") == "about" else "airports")
_on = lambda k: " on" if _cur == k else ""
_mag = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/>'
        '<path d="M20 20l-3.5-3.5"/></svg>')
st.markdown(
    '<div class="topbar">'
    '<div class="sd-side">'
    f'<a class="sd-link{_on("airports")}" href="/" target="_self">Airports</a>'
    '</div>'
    '<a class="sd-brand" href="/" target="_self">skydelay</a>'
    '<div class="sd-side r">'
    f'<form class="sd-search" action="/" method="get" target="_self">{_mag}'
    '<input name="airport" list="sd-ap" placeholder="Search" autocomplete="off"></form>'
    f'<datalist id="sd-ap">{_airport_options()}</datalist>'
    f'<a class="sd-link{_on("predict")}" href="?page=predict" target="_self">Check a flight</a></div>'
    '</div>', unsafe_allow_html=True)

# ---------------- router ----------------
def _route():
    if st.query_params.get("page") == "go":
        from views.book import render_go
        render_go()
        return
    if st.query_params.get("page") == "book":
        from views.book import render_book
        render_book()
        return
    if st.query_params.get("page") in ("flight", "predict"):
        from views.flight import render_flight
        render_flight()
        return
    if st.query_params.get("page") == "predict":
        from views.predict import render_predict
        render_predict()
        return
    if "airport" not in st.query_params:
        from views.home import render_home
        if any(k in st.query_params for k in ("airline", "city", "region", "list")):
            render_home()
        else:
            from views.home_map import render_home_map
            render_home_map()
        return
    from views.airport import render_airport
    render_airport()


@st.cache_resource(show_spinner=False)
def _warm_boards_daily(day_iso):
    """Once per day per server: pre-compute departures boards (today + tomorrow) for the 40 busiest US/EU airports
    in a background thread, so boards and tickers open instantly. Already-cached airports are skipped quickly."""
    import threading

    def run():
        try:
            from core.warm_boards import main
            main(40)
        except Exception as e:
            print("[warm] failed:", type(e).__name__, e)
    threading.Thread(target=run, daemon=True).start()
    return True


from datetime import date as _date_w
import os as _os_w
if not (_os_w.getcwd().startswith("/mount/") or _os_w.environ.get("SKYDELAY_WARM") == "0"):
    _warm_boards_daily(_date_w.today().isoformat())

try:
    _route()
finally:
    _boot.empty()
st.stop()
