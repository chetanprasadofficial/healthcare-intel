"""Desert map page: where is care missing, and where is the data just missing?"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd
import streamlit as st
from deserts import compute, CAPS, LABELS, COLORS

st.set_page_config(page_title="Desert map", page_icon="🗺️", layout="centered")
st.title("🗺️ Medical desert vs data desert")
st.caption("A place with no evidence is not always a place with no care. This map separates the two.")
st.error("**In an emergency call 112 first.** This map is built from listing data, not from a health-system census.")

@st.cache_data
def get(cap, prefix, radius, min_listings):
    return compute(cap, prefix=prefix, radius=radius, min_listings=min_listings)

c1, c2 = st.columns(2)
cap = c1.selectbox("Capability", CAPS, index=0)
prefix = c2.radio("Area size", [3, 4], format_func=lambda n: f"PIN prefix, {n} digits", horizontal=True)
radius = c1.slider("Coverage radius (km)", 10, 100, 25, step=5)
min_listings = c2.slider("Listings needed to call it a data desert", 1, 20, 5)

areas = get(cap, prefix, float(radius), int(min_listings))
n = len(areas)
counts = areas.kind.value_counts()
m1, m2, m3 = st.columns(3)
for col, k in zip((m1, m2, m3), ("covered", "data_desert", "medical_desert")):
    v = int(counts.get(k, 0))
    col.metric(LABELS[k], v, f"{100 * v / max(n, 1):.0f}% of {n} areas", delta_color="off")

st.markdown(" &nbsp; ".join(f"<span style='color:{COLORS[k]}'>●</span> {LABELS[k]}" for k in COLORS), unsafe_allow_html=True)
st.map(areas[["lat", "lon", "color"]], latitude="lat", longitude="lon", color="color", size=9000)

st.markdown(f"""
- 🟢 **Covered:** a listing with supported evidence for **{cap}** lies within {radius} km.
- 🟠 **Data desert:** at least {min_listings} listings within {radius} km, but none with evidence for {cap}. Care may exist; the records are silent.
- 🔴 **Likely medical desert:** no evidence and fewer than {min_listings} listings nearby. This may also mean the dataset samples that area lightly.
""")

cols = {"area": "PIN prefix", "state": "State", "city": "Main city", "listings_nearby": "Listings nearby",
        "mentions": "Mentions only", "nearest_evidence_km": "Nearest evidence (km)"}
st.subheader("Biggest data deserts")
st.caption("Many facilities listed, none with evidence. These are the best places to collect better data.")
dd = areas[areas.kind == "data_desert"].sort_values("listings_nearby", ascending=False).head(10)
st.dataframe(dd[list(cols)].rename(columns=cols), hide_index=True, use_container_width=True) if len(dd) else st.caption("None with these settings.")

st.subheader("Likely medical deserts")
st.caption("Evidence is farthest away and listings are few. These are the best places to check for real care gaps.")
md = areas[areas.kind == "medical_desert"].sort_values("nearest_evidence_km", ascending=False).head(10)
st.dataframe(md[list(cols)].rename(columns=cols), hide_index=True, use_container_width=True) if len(md) else st.caption("None with these settings.")

with st.expander("By state"):
    t = pd.crosstab(areas.state.replace("", "Unknown"), areas.label)
    st.dataframe(t, use_container_width=True)

with st.expander("Method and limits"):
    st.markdown(
        "- Each area is a PIN prefix; its centre is the average position of its listings.\n"
        "- Evidence means a capability marked *supported* by the extractor and verifier, including partially supported. "
        "Mentioned-only and conflicting records do not count.\n"
        "- The data has about 10,000 listings, so thinly listed areas can be sampling gaps, not real gaps. That is why red says *likely*.\n"
        "- Distances are straight-line from the area centre, not road distance.\n"
        "- The thresholds are project choices you can change with the sliders.")
