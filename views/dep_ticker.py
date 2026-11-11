"""Next departures ticker: next scheduled flights with a live countdown (components/dep_ticker/index.html)."""
import os

import streamlit as st
import streamlit.components.v1 as components

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tk = components.declare_component("dep_ticker", path=os.path.join(APP_DIR, "components", "dep_ticker"))


def dep_ticker(payload, key):
    v = _tk(data=payload, key=key, default=None)
    if isinstance(v, dict) and v.get("qp") and st.session_state.get("_tk_last") != v.get("t"):
        st.session_state["_tk_last"] = v.get("t")
        st.query_params.from_dict(v["qp"])
        st.rerun()
