"""Booking options for one itinerary (Ignav booking-links) and the redirect screen."""
import html
import json
from datetime import date, datetime
from functools import lru_cache
from urllib.parse import urlencode

import streamlit as st
import streamlit.components.v1 as components

from core.ignav import booking_links
from core.loader import loading

PATH = "M2 16.5l20-6.5-2-2-7 2L8 4H6l2.5 7.2L5 12.5 3 11H2l1 3.2z"
CSS = """<style>
.bk-wrap{max-width:1080px;margin:18px auto 0;}
.bk-back{display:inline-flex;align-items:center;gap:8px;font-weight:700;color:#0055A0 !important;text-decoration:none !important;margin-bottom:12px;}
.bk-back:hover{color:#00447F !important;}
.bk-hd{background:#12284B;border-radius:18px;padding:22px 26px;margin-bottom:18px;}
.bk-route{font-size:1.7rem;font-weight:700;color:#fff;letter-spacing:-.02em;}
.bk-sub{color:#B8CBE3;font-weight:600;margin-top:4px;}
.bk-g{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:18px;align-items:start;}
@media (max-width:860px){.bk-g{grid-template-columns:minmax(0,1fr);}}
.bk-lab{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#111418;margin:18px 4px 8px;}
.bk-lab.f{margin-top:0;}
.bk-row{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #E2E6EC;border-radius:14px;padding:14px 18px;margin-bottom:10px;transition:transform .15s,box-shadow .15s;}
.bk-row:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(18,40,75,.08);}
.bk-row.best{border:2px solid #2C9A69;}
.bk-name{font-weight:700;color:#111418;font-size:1.02rem;}
.bk-s{color:#111418;font-size:.82rem;margin-top:3px;}
.bk-tag{display:inline-block;font-size:.64rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:999px;margin-left:8px;vertical-align:2px;}
.bk-air{background:#DCEAF6;color:#003F7A;}.bk-ota{background:#EEF5FA;color:#111418;}.bk-chp{background:#E3F4EC;color:#1F6B49;}
.bk-pr{margin-left:auto;text-align:right;white-space:nowrap;}
.bk-pr b{display:block;font-weight:700;font-size:1.15rem;color:#111418;}
.bk-pr span{font-size:.78rem;color:#111418;font-weight:600;}
.bk-go{display:inline-block;padding:8px 16px;border-radius:999px;background:#0055A0;color:#fff !important;font-weight:700;text-decoration:none !important;white-space:nowrap;}
.bk-go:hover{background:#00447F;}
.bk-lg{width:32px;height:32px;flex:none;display:flex;align-items:center;justify-content:center;}
.bk-lg img{max-width:32px;max-height:32px;object-fit:contain;border-radius:6px;}
.bk-card{background:#fff;border:1px solid #E2E6EC;border-radius:16px;padding:18px 20px;}
.bk-fl{display:flex;align-items:center;gap:8px;font-weight:700;color:#111418;font-size:.92rem;}
.bk-fl img{height:22px;width:auto;}
.bk-t{display:flex;align-items:flex-start;gap:12px;margin:12px 0 4px;}
.bk-t b{display:block;font-size:1.35rem;font-weight:700;color:#111418;}
.bk-t .c{color:#111418;font-weight:600;font-size:.85rem;}
.bk-ln{flex:1;text-align:center;color:#111418;font-size:.78rem;font-weight:600;border-top:2px dotted #C9DEEE;padding-top:4px;margin-top:14px;}
.bk-risk{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px;font-size:.72rem;font-weight:700;letter-spacing:.04em;margin-top:14px;}
.bk-dot{width:7px;height:7px;border-radius:50%;display:inline-block;}
.bk-ia{display:flex;gap:4px;margin:10px 0 4px;}
.bk-ot{font-weight:700;color:#111418;}
.bk-st{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;}
.bk-st div{background:#F5F9FC;border-radius:10px;padding:8px 10px;}
.bk-st b{display:block;font-weight:700;color:#111418;}
.bk-st span{font-size:.75rem;color:#111418;}
.bk-lay{margin:14px 0;background:#EEF5FA;border-radius:10px;padding:7px 12px;font-size:.82rem;color:#111418;font-weight:600;}
.bk-none{background:#fff;border:1px solid #E2E6EC;border-radius:14px;padding:22px;color:#111418;font-weight:600;}
</style>"""
GO_CSS = """<style>
.topbar,header[data-testid="stHeader"]{display:none !important;}
.go-wrap{min-height:72vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#111418;}
.go-rot{transform-origin:60px 60px;animation:go-spin 1.6s linear infinite;}
@keyframes go-spin{to{transform:rotate(360deg);}}
.go-k{color:#111418;font-weight:600;margin-top:18px;}
.go-n{font-size:2rem;font-weight:700;letter-spacing:-.02em;margin-top:6px;display:flex;align-items:center;justify-content:center;gap:14px;}
.go-lg{display:flex;align-items:center;}.go-lg img{height:52px;width:auto;max-width:180px;object-fit:contain;border-radius:8px;}
.go-bar{width:min(320px,70vw);height:6px;background:#E2E6EC;border-radius:999px;overflow:hidden;margin-top:22px;}
.go-bar div{height:100%;width:0;background:#0055A0;border-radius:999px;animation:go-fill 1.6s ease-out forwards;}
@keyframes go-fill{to{width:100%;}}
.go-alt{margin-top:18px;color:#0055A0 !important;font-weight:700;text-decoration:none !important;opacity:0;animation:go-in .3s 3s forwards;}
@keyframes go-in{to{opacity:1;}}
</style>"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _dt(x):
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None


def _fc(s):
    out = []
    for part in (s or "").split(";"):
        v = part.split(",") if part else []
        if len(v) >= 3 and _num(v[0]) is not None and v[2]:
            out.append({"p0": _num(v[0]), "m": _num(v[1]), "lvl": v[2],
                        "lo": _num(v[3]) if len(v) > 3 else None, "hi": _num(v[4]) if len(v) > 4 else None})
        else:
            out.append(None)
    return out


def _money(a, cur):
    return ("&#36;" if cur == "USD" else cur + " ") + f"{a:,.0f}"


def _plane(color):
    return f'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="{PATH}" fill="{color}"/></svg>'


COMMON = {"united": "UA", "american": "AA", "delta": "DL", "alaska": "AS", "jetblue": "B6", "southwest": "WN",
          "air canada": "AC", "westjet": "WS", "lufthansa": "LH", "austrian": "OS", "swiss": "LX", "brussels": "SN",
          "british airways": "BA", "virgin atlantic": "VS", "aer lingus": "EI", "klm": "KL", "air france": "AF",
          "iberia": "IB", "finnair": "AY", "sas": "SK", "tap": "TP", "icelandair": "FI", "condor": "DE",
          "turkish": "TK", "emirates": "EK", "qatar": "QR", "etihad": "EY", "singapore": "SQ", "cathay": "CX",
          "malaysia": "MH", "qantas": "QF", "jetstar": "JQ", "virgin australia": "VA", "air new zealand": "NZ",
          "japan airlines": "JL", "ana": "NH", "all nippon": "NH", "korean": "KE", "eva": "BR", "air india": "AI",
          "indigo": "6E"}


@lru_cache(maxsize=1)
def _name_map():
    import glob, os
    from core import ignav as ig
    m = {}
    for p in glob.glob(os.path.join(ig.CACHE, "*.json")):
        if os.path.basename(p).startswith("book_"):
            continue
        try:
            d = json.load(open(p))
        except Exception:
            continue
        for it in d.get("itineraries", []):
            for sg in (it.get("outbound") or {}).get("segments", []):
                n = (sg.get("operating_carrier_name") or "").strip().lower()
                if n and n not in m:
                    try:
                        c = ig._op_code(sg)
                    except Exception:
                        c = None
                    if c:
                        m[n] = c
    return m


def _airline_code(name, segs):
    """Provider name ("Austrian") -> IATA code ("OS") for the logo."""
    n = (name or "").strip().lower()
    if not n:
        return None
    from core import ignav as ig
    for sg in segs:
        on = (sg.get("operating_carrier_name") or "").lower()
        if on and (on == n or on.startswith(n) or n.startswith(on)):
            try:
                return ig._op_code(sg)
            except Exception:
                pass
    for table in (_name_map(), COMMON):
        if n in table:
            return table[n]
        for k, c in table.items():
            if k.startswith(n) or n.startswith(k):
                return c
    return None


def render_book():
    from views.flight import LEVEL_COLORS, LEVEL_HALO, LEVEL_TEXT, in_ten, logo_html, city_of
    q = st.query_params
    o, d = q.get("o", ""), q.get("d", "")
    fns = [x for x in q.get("f", "").split(",") if x]
    try:
        day = date.fromisoformat(q.get("date", ""))
    except ValueError:
        day = None
    shift = int(_num(q.get("s")) or 0)
    st.markdown(CSS, unsafe_allow_html=True)
    back = urlencode({"page": "predict", "from": q.get("bf") or o, "to": q.get("bt") or d,
                      "date": q.get("bd") or (day.isoformat() if day else "")})
    backa = f'<a class="bk-back" href="?{html.escape(back)}" target="_self">&larr; Back to results</a>'
    if not (o and d and fns and day):
        st.markdown(f'<div class="bk-wrap">{backa}<div class="bk-none">Booking link not available.</div></div>', unsafe_allow_html=True)
        return
    with loading():
        data = booking_links(o, d, day, fns, q.get("id") or None, shift)
    itin = (data or {}).get("itinerary") or {}
    segs = (itin.get("outbound") or {}).get("segments") or []
    cur = (itin.get("price") or {}).get("currency") or "USD"

    def cty(c):
        try:
            n = city_of(c)
        except Exception:
            n = None
        return f"{html.escape(n)} {c}" if n and n != c else c

    head = (f'<div class="bk-hd"><div class="bk-route">{cty(o)} &rarr; {cty(d)}</div>'
            f'<div class="bk-sub">{day:%a}, {day.day} {day:%b %Y} · 1 adult · One way · Prices in {html.escape(cur)}</div></div>')
    rows = []
    for opt in (data or {}).get("booking_options", []):
        for ln in opt.get("links", []):
            url = (ln.get("url") or "").strip()
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://" + url
            p = ln.get("price") if isinstance(ln.get("price"), dict) else {}
            a = _num(p.get("amount")) if p.get("status") != "unverified" else None
            rows.append({"typ": ln.get("provider_type"), "name": ln.get("provider_name") or "Book", "fare": ln.get("fare_name"),
                         "url": url, "amt": a if a and a > 0 else None, "cur": p.get("currency") or cur})
    priced = [r for r in rows if r["amt"] is not None]
    best = min(priced, key=lambda r: r["amt"]) if priced else None
    opname = segs[0].get("operating_carrier_name") if len(segs) == 1 else None

    def row(r, is_best=False):
        tags = ('<span class="bk-tag bk-air">Airline</span>' if r["typ"] == "airline"
                else '<span class="bk-tag bk-ota">Agency</span>' if r["typ"] else "")
        if is_best:
            tags += '<span class="bk-tag bk-chp">Cheapest</span>'
        sub = [html.escape(r["fare"])] if r["fare"] else []
        if opname:
            first = r["name"].lower().split()[0] if r["name"] else ""
            if r["typ"] == "airline" and first and first in opname.lower():
                sub.append("Operates this flight")
            else:
                sub.append(f"{'Codeshare · ' if r['typ'] == 'airline' else ''}Operated by {html.escape(opname)}")
        sub = f'<div class="bk-s">{" · ".join(sub)}</div>' if sub else ""
        price = _money(r["amt"], r["cur"]) if r["amt"] is not None else ""
        diff = ""
        if not is_best and best and r["amt"] is not None and r["amt"] - best["amt"] >= 1:
            diff = f'<span>+{_money(r["amt"] - best["amt"], r["cur"])}</span>'
        lg = ""
        if r["typ"] == "airline":
            c = _airline_code(r["name"], segs)
            if c:
                try:
                    lg = f'<span class="bk-lg">{logo_html(c)}</span>'
                except Exception:
                    lg = ""
        go = urlencode({"page": "go", "u": r["url"], "n": r["name"],
                        "c": (_airline_code(r["name"], segs) or "") if r["typ"] == "airline" else ""})
        return (f'<div class="bk-row{" best" if is_best else ""}">{lg}<div><div class="bk-name">{html.escape(r["name"])}{tags}</div>{sub}</div>'
                f'<div class="bk-pr"><b>{price}</b>{diff}</div>'
                f'<a class="bk-go" href="?{html.escape(go)}" target="_blank" rel="noopener">Go &#8599;</a></div>')

    INF = float("inf")
    rest = [r for r in rows if r is not best]
    air = sorted([r for r in rest if r["typ"] == "airline"], key=lambda r: r["amt"] if r["amt"] is not None else INF)
    ota = sorted([r for r in rest if r["typ"] != "airline"], key=lambda r: r["amt"] if r["amt"] is not None else INF)
    left, first = "", True
    for lab, grp in (("Cheapest", [best] if best else []), ("Book with the airline", air), ("Agencies", ota)):
        if grp:
            left += f'<div class="bk-lab{" f" if first else ""}">{lab}</div>' + "".join(row(r, lab == "Cheapest") for r in grp)
            first = False
    if not left:
        left = '<div class="bk-none">Booking link not available.</div>'
    fc = _fc(q.get("fc"))
    right, prev = "", None
    for i, s in enumerate(segs):
        dep, arr = _dt(s.get("departure_time_local")), _dt(s.get("arrival_time_local"))
        if not dep or not arr:
            continue
        du, au_ = _dt(s.get("departure_time_utc")), _dt(s.get("arrival_time_utc"))
        if prev and du:
            lay = int((du - prev).total_seconds() // 60)
            right += f'<div class="bk-lay">{lay // 60}h {lay % 60:02d}m connection in {cty(s.get("departure_airport", ""))}</div>'
        prev = au_
        code, fn = s.get("marketing_carrier_code") or "", s.get("flight_number") or ""
        try:
            lg = logo_html(code)
        except Exception:
            lg = ""
        dm = s.get("duration_minutes")
        dur = f"{int(dm) // 60}h {int(dm) % 60:02d}m" if dm else ""
        plus = (arr.date() - dep.date()).days
        sup = f'<sup style="font-size:.65rem">+{plus}</sup>' if plus > 0 else ""
        leg = (f'<div class="bk-fl">{lg}<span>{html.escape(s.get("operating_carrier_name") or code)} · {html.escape(code + fn)}</span></div>'
               f'<div class="bk-t"><div><b>{dep:%H:%M}</b><div class="c">{html.escape(s.get("departure_airport", ""))}</div></div>'
               f'<div class="bk-ln">{dur}</div>'
               f'<div style="text-align:right"><b>{arr:%H:%M}{sup}</b><div class="c">{html.escape(s.get("arrival_airport", ""))}</div></div></div>')
        f = fc[i] if i < len(fc) else None
        if f and f["lvl"] in LEVEL_COLORS:
            lab = {"Low": "LOW RISK", "Moderate": "MEDIUM RISK", "High": "HIGH RISK"}[f["lvl"]]
            n = max(0, min(10, int(round(f["p0"] * 10))))
            leg += (f'<span class="bk-risk" style="background:{LEVEL_HALO[f["lvl"]]};color:{LEVEL_TEXT[f["lvl"]]}">'
                    f'<span class="bk-dot" style="background:{LEVEL_COLORS[f["lvl"]]}"></span>{lab}</span>'
                    f'<div class="bk-ia">' + "".join(_plane("#2C9A69" if k < n else "#D3DCE6") for k in range(10)) + '</div>'
                    f'<div class="bk-ot">{in_ten(f["p0"])} flights like this arrive on time</div>')
            st_ = []
            if f["m"]:
                st_.append(f'<div><b>{f["m"]:.0f} min</b><span>typical delay</span></div>')
            if f["lo"] is not None and f["hi"] is not None:
                st_.append(f'<div><b>{f["lo"]:.1f}–{f["hi"]:.1f} kg</b><span>delay CO₂ for your seat</span></div>')
            if st_:
                leg += '<div class="bk-st">' + "".join(st_) + '</div>'
        right += f'<div class="bk-leg">{leg}</div>'
    right = f'<div class="bk-card">{right}</div>' if right else ""
    body = f'<div class="bk-g"><div>{left}</div><div>{right}</div></div>'
    st.markdown(f'<div class="bk-wrap">{backa}{head}{body}</div>', unsafe_allow_html=True)


def render_go():
    q = st.query_params
    url, name = q.get("u", ""), q.get("n", "") or "the booking site"
    st.markdown(GO_CSS, unsafe_allow_html=True)
    if not url.startswith(("http://", "https://")):
        st.markdown('<div class="go-wrap"><div class="go-n">Booking link not available.</div></div>', unsafe_allow_html=True)
        return
    lg, c = "", q.get("c", "")
    if c:
        try:
            from views.flight import logo_html
            lg = f'<span class="go-lg">{logo_html(c)}</span>'
        except Exception:
            lg = ""
    spin = ('<svg viewBox="0 0 120 120" width="120" height="120" aria-hidden="true">'
            '<circle cx="60" cy="60" r="46" fill="none" stroke="#C9DEEE" stroke-width="2.5" stroke-dasharray="1 7" stroke-linecap="round"/>'
            f'<g class="go-rot"><g transform="translate(48 2)"><path d="{PATH}" fill="#0055A0"/></g></g></svg>')
    st.markdown(f'<div class="go-wrap">{spin}<div class="go-k">Taking you to</div><div class="go-n">{lg}<span>{html.escape(name)}</span></div>'
                f'<div class="go-bar"><div></div></div>'
                f'<a class="go-alt" href="{html.escape(url)}" target="_self">Continue to {html.escape(name)} &#8599;</a></div>',
                unsafe_allow_html=True)
    js = json.dumps(url).replace("</", "<\\/")
    components.html("<script>setTimeout(function(){try{var d=window.parent.document,s=d.createElement('script');"
                    "s.text='window.location.replace('+JSON.stringify(" + js + ")+')';d.body.appendChild(s);}catch(e){}},1600);</script>",
                    height=0)
