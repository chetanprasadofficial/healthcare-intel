"""Desert map page: where is care missing, and where is the data just missing?"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd
import streamlit as st
from deserts import compute, CAPS, LABELS, COLORS
from i18n import lang_selector
from desert_i18n import TR

st.set_page_config(page_title="Desert map", page_icon="🗺️", layout="centered")
LANG = lang_selector("map")

def T(key, **kw):
    s = TR.get(LANG, {}).get(key) or TR["en"][key]      # falls back to English if a key is missing
    return s.format(**kw) if kw else s

st.title(T("title"))
st.caption(T("caption"))
st.error(T("emerg"))

@st.cache_data
def get(cap, prefix, radius, min_listings):
    return compute(cap, prefix=prefix, radius=radius, min_listings=min_listings)

c1, c2 = st.columns(2)
cap = c1.selectbox(T("cap"), CAPS, index=0)
prefix = c2.radio(T("area_size"), [3, 4], format_func=lambda n: T("prefix", n=n), horizontal=True)
radius = c1.slider(T("radius"), 10, 100, 25, step=5)
min_listings = c2.slider(T("minl"), 1, 20, 5)

areas = get(cap, prefix, float(radius), int(min_listings))
n = len(areas)
counts = areas.kind.value_counts()
m1, m2, m3 = st.columns(3)
for col, k in zip((m1, m2, m3), ("covered", "data_desert", "medical_desert")):
    v = int(counts.get(k, 0))
    col.metric(T(k), v, T("of_areas", pct=f"{100 * v / max(n, 1):.0f}", n=n), delta_color="off")

st.markdown(" &nbsp; ".join(f"<span style='color:{COLORS[k]}'>●</span> {T(k)}" for k in COLORS), unsafe_allow_html=True)
st.map(areas[["lat", "lon", "color"]], latitude="lat", longitude="lon", color="color", size=9000)

st.markdown("\n".join([T("b_cov", cap=cap, radius=radius),
                       T("b_dd", cap=cap, radius=radius, minl=min_listings),
                       T("b_md", minl=min_listings)]))

cols = {"area": T("c_area"), "state": T("c_state"), "city": T("c_city"), "listings_nearby": T("c_list"),
        "mentions": T("c_ment"), "nearest_evidence_km": T("c_near")}

st.subheader(T("h_dd"))
st.caption(T("s_dd"))
dd = areas[areas.kind == "data_desert"].sort_values("listings_nearby", ascending=False).head(10)
if len(dd):
    st.dataframe(dd[list(cols)].rename(columns=cols), hide_index=True, use_container_width=True)
else:
    st.caption(T("none"))

st.subheader(T("h_md"))
st.caption(T("s_md"))
md = areas[areas.kind == "medical_desert"].sort_values("nearest_evidence_km", ascending=False).head(10)
if len(md):
    st.dataframe(md[list(cols)].rename(columns=cols), hide_index=True, use_container_width=True)
else:
    st.caption(T("none"))

with st.expander(T("by_state")):
    tbl = pd.crosstab(areas.state.replace("", "Unknown"), areas.label)
    st.dataframe(tbl, use_container_width=True)

with st.expander(T("method")):
    st.markdown(T("m_text"))