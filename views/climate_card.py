"""Highlighted climate cost card (components/climate_card/index.html): count-up, live since-midnight counter."""
import os

import streamlit.components.v1 as components

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cc = components.declare_component("climate_card", path=os.path.join(APP_DIR, "components", "climate_card"))


def climate_card(payload, key):
    _cc(data=payload, key=key, default=None)
