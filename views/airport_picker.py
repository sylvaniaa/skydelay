"""Searchable city/airport picker (custom Streamlit component, plain HTML/JS).
Options: one per airport ("Chicago, United States" / airport name + state / code chip), plus a
'whole city' option for cities with 2+ airports (grouped by city AND state, so the two
Portlands stay separate). METRO lets an airport join a nearby city (EWR -> New York)."""
import os
import unicodedata

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_picker = components.declare_component(
    "airport_picker", path=os.path.join(APP_DIR, "components", "airport_picker"))

METRO = {"EWR": ("New York", "New York")}   # code -> (city, region) used for grouping


@st.cache_data(show_spinner=False)
def lookup():
    df = pd.read_csv(os.path.join(APP_DIR, "data", "airports_lookup.csv"), keep_default_na=False)
    return df.set_index("iata").to_dict("index")


def _norm(s):
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()


def _info(code):
    a = lookup().get(code)
    if a:
        return a
    return {"airport": code, "city": code, "region": "", "country": "", "country_code": "", "tz": ""}


def _group_key(code):
    a = _info(code)
    city, region = METRO.get(code, (a["city"], a["region"]))
    return city, region, a["country_code"]


def place(a):
    return a["city"] + (", " + a["country"] if a["country"] else "")


def _airport_opt(code, sub=False, parent=""):
    a = _info(code)
    t2 = a["airport"] + (" · " + a["region"] if a["region"] else "")
    return {"value": code, "kind": "airport", "t1": place(a), "t2": t2, "chip": code,
            "sub": sub, "parent": parent, "members": [code],
            "search": _norm(" ".join([a["city"], a["region"], a["country"], a["airport"], code]))}


@st.cache_data(show_spinner=False)
def build_options(codes):
    """codes: tuple of IATA codes, most-used first."""
    groups = {}
    for c in codes:
        groups.setdefault(_group_key(c), []).append(c)
    out, done = [], set()
    for c in codes:
        key = _group_key(c)
        members = groups[key]
        if len(members) < 2:
            out.append(_airport_opt(c))
            continue
        if key in done:
            continue
        done.add(key)
        city, region, cc = key
        country = _info(c)["country"]
        cv = "city:%s|%s|%s" % key
        out.append({"value": cv, "kind": "city", "t1": city + (", " + country if country else ""),
                    "t2": city + (" · " + region if region and region != city else ""), "chip": "All",
                    "sub": False, "parent": "", "members": members,
                    "search": _norm(" ".join([city, region, country] + members))})
        out.extend(_airport_opt(m, sub=True, parent=cv) for m in members)
    return out


def airport_picker(label, codes, selected, key):
    """Returns (value, list_of_iata_codes, option_dict)."""
    opts = build_options(tuple(codes))
    by_value = {o["value"]: o for o in opts}
    prev = st.session_state.get(key + "__sel")
    if prev in by_value:
        selected = prev
    elif selected not in by_value:
        selected = opts[0]["value"] if opts else None
    v = _picker(label=label, options=opts, selected=selected, key=key, default=None)
    if v in by_value and v != st.session_state.get(key + "__last_v"):
        selected = v
    st.session_state[key + "__last_v"] = v
    st.session_state[key + "__sel"] = selected
    o = by_value.get(selected)
    return selected, (o["members"] if o else []), o
