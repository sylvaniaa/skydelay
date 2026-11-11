"""Homepage: full-screen map (dots coloured by how busy each airport is), a flight search card
(same city/airport options as Check a flight) and an 'Explore airports' panel that slides up over it.
Custom component (MapLibre + OpenFreeMap, no API key)."""
import os

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import predict as pr
from views.airport_picker import build_options

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_home = components.declare_component("home_map", path=os.path.join(APP_DIR, "components", "home_map"))

FULLSCREEN_CSS = """
<style>
header[data-testid="stHeader"]{display:none !important;}
.topbar{display:none !important;}
[data-testid="stAppViewContainer"]{overflow:hidden !important;}
div[class*="st-key-homemap"] iframe{position:fixed !important;top:0 !important;left:0 !important;
  width:100vw !important;height:100vh !important;z-index:1000;border:none;}
</style>
"""


@st.cache_data(ttl=86400, show_spinner=False)
def airports():
    df = pd.read_csv(os.path.join(APP_DIR, "data", "home_airports.csv"))
    out = []
    for r in df.to_dict("records"):
        kind, val = str(r.pop("page")).split(":", 1)
        rec = {}
        for k, v in r.items():
            if isinstance(v, float) and pd.isna(v):
                v = None
            elif hasattr(v, "item"):
                v = v.item()
            rec[k] = v
        rec["qp"] = {"airport": val} if kind == "airport" else {"city": val, "region": "India"}
        out.append(rec)
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def flight_search():
    """Options for the From/To fields (same as Check a flight) + which destinations each origin reaches."""
    sched = pr.schedule()
    origins = [str(c) for c in pr.schedule_origins()]
    routes = sched.groupby(["origin", "dest"]).n_flights.sum().reset_index()
    dest_order = [str(c) for c in routes.groupby("dest").n_flights.sum().sort_values(ascending=False).index]
    reach = {str(o): [str(x) for x in g.sort_values("n_flights", ascending=False).dest]
             for o, g in routes.groupby("origin")}
    from core.connections import reach_one_stop
    for o, extra in reach_one_stop().items():
        have = set(reach.get(str(o), []))
        reach[str(o)] = reach.get(str(o), []) + sorted(str(x) for x in extra if str(x) not in have)
    try:   # Australia: reported BITRE routes
        au = pd.read_csv(os.path.join(APP_DIR, "data", "au_routes.csv"))
        au = au[au.airline == "ALL"].groupby(["origin", "dest"]).Sectors_Flown.sum().reset_index()
        for o in au.groupby("origin").Sectors_Flown.sum().sort_values(ascending=False).index:
            if str(o) not in origins:
                origins.append(str(o))
        for d in au.groupby("dest").Sectors_Flown.sum().sort_values(ascending=False).index:
            if str(d) not in dest_order:
                dest_order.append(str(d))
        for o, g in au.groupby("origin"):
            have = set(reach.get(str(o), []))
            reach[str(o)] = reach.get(str(o), []) + [str(x) for x in g.sort_values("Sectors_Flown", ascending=False).dest
                                                     if str(x) not in have]
    except Exception:
        pass
    return {"from": build_options(tuple(origins)), "to": build_options(tuple(dest_order)), "reach": reach}


def render_home_map():
    st.markdown(FULLSCREEN_CSS, unsafe_allow_html=True)
    with st.container(key="homemap"):
        v = _home(airports=airports(), search=flight_search(), key="home_map_c", default=None)
    if isinstance(v, dict) and v.get("qp") and v.get("t") != st.session_state.get("home_last_t"):
        st.session_state["home_last_t"] = v.get("t")
        if v["qp"].get("page") == "predict":
            # forget the last picks in Check a flight so the route from the homepage is used
            for k in ("from_pick__sel", "to_pick__sel"):
                st.session_state.pop(k, None)
        st.query_params.clear()
        for k, val in v["qp"].items():
            st.query_params[k] = val
        st.rerun()
