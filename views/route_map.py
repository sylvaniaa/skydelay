"""Where you can fly: real street map (Esri tiles via Leaflet) with curved routes from the hub,
ranked destination tiles and the airline on-time leaderboard (components/route_map/index.html)."""
import os

import streamlit as st
import streamlit.components.v1 as components

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_rm = components.declare_component("route_map", path=os.path.join(APP_DIR, "components", "route_map"))


def route_map_section(payload, key):
    v = _rm(data=payload, key=key, default=None)
    if isinstance(v, dict) and v.get("qp") and st.session_state.get("_rm_last") != v.get("t"):
        st.session_state["_rm_last"] = v.get("t")
        st.query_params.from_dict(v["qp"])
        st.rerun()
