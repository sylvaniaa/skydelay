"""Airport-style departures board (components/dep_board/index.html): scheduled flights, SkyDelay forecast, live clock."""
import os

import streamlit as st
import streamlit.components.v1 as components

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_db = components.declare_component("dep_board", path=os.path.join(APP_DIR, "components", "dep_board"))


def dep_board(payload, key):
    v = _db(data=payload, key=key, default=None)
    if isinstance(v, dict) and v.get("qp") and st.session_state.get("_db_last") != v.get("t"):
        st.session_state["_db_last"] = v.get("t")
        st.query_params.from_dict(v["qp"])
        st.rerun()
