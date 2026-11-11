"""Full-screen loading animation: a plane circling with a dotted trail (no text)."""
import math
from contextlib import contextmanager

import streamlit as st


def _html():
    cx = cy = 100
    r = 68
    dots = []
    for i in range(16):
        a = math.radians(-90 - (i + 1) * 13)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{max(1.2, 5.5 - i * 0.28):.1f}" '
                    f'fill="#8CC1E9" opacity="{max(0.15, 1 - i * 0.06):.2f}"/>')
    plane = ('<path transform="translate(100 32) rotate(90) scale(1.4) translate(-12 -12)" fill="#438BC4" '
             'd="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 '
             '3.5 1v-1.5L13 19v-5.5l8 2.5z"/>')
    return ('<style>.sd-load{position:fixed;inset:0;z-index:999999;display:flex;align-items:center;'
            'justify-content:center;background:#F3F8FB;'
            'opacity:0;animation:sd-in .2s .35s forwards;}'
            '@keyframes sd-in{to{opacity:1;}}'
            '.sd-orbit{transform-box:view-box;transform-origin:50% 50%;animation:sd-spin 1.6s linear infinite;}'
            '@keyframes sd-spin{to{transform:rotate(360deg);}}</style>'
            '<div class="sd-load"><svg viewBox="0 0 200 200" width="150" height="150" aria-hidden="true">'
            '<g class="sd-orbit">' + "".join(dots) + plane + '</g></svg></div>')


HTML = _html()


@contextmanager
def loading():
    ph = st.empty()
    ph.markdown(HTML, unsafe_allow_html=True)
    try:
        yield
    finally:
        ph.empty()
