"""Healthcare Intelligence (PS-03) - Streamlit app.
Run from the project root:  streamlit run app/streamlit_app.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd
import streamlit as st
from search import search, Index
from validator import validate

st.set_page_config(page_title="Healthcare Intelligence", page_icon="🏥", layout="centered")

@st.cache_resource
def load_index():
    return Index()

SAMPLES = [
    "dialysis near 110001",
    "emergency appendectomy in Bihar near 841428 with part-time doctors",
    "trauma care near Pune",
    "ICU in Delhi",
    "मुझे बिहार में डायलिसिस चाहिए",
]

st.title("🏥 Healthcare Intelligence")
st.caption("Evidence-first search over 10,000 facility listings. It shows what the records say, "
           "the exact quote behind it, and what it cannot verify.")
st.error("**In an emergency call 112 (or your local ambulance) first.** This is a decision-support prototype built on "
         "scraped listing data. It is not a clinical authority and does not show live beds or doctors. Always phone the facility before travelling.")

if "q" not in st.session_state:
    st.session_state.q = SAMPLES[0]

with st.sidebar:
    st.header("Try an example")
    for s in SAMPLES:
        if st.button(s, key="ex_" + s):
            st.session_state.q = s
    st.markdown("---")
    st.caption("Tip: add a PIN code or city for distances, e.g. *dialysis near 110001*.")

with st.form("search_form"):
    q = st.text_input("What do you need, and where?", value=st.session_state.q)
    go = st.form_submit_button("Search")
if go:
    st.session_state.q = q

idx = load_index()
query = st.session_state.q.strip()
if not query:
    st.stop()

out = validate(search(query, k=5, idx=idx))   # every claim passes the validator before display
p = out["parsed"]

# ---- 1. What we understood (shown BEFORE results) ----
st.subheader("1. What we understood")
chips = []
if p["capabilities"]: chips.append("Needs: " + " + ".join(p["capabilities"]))
if p["state"]: chips.append("State: " + p["state"])
if p["pin"]: chips.append("PIN: " + p["pin"])
if p["city"]: chips.append("City: " + p["city"])
if p["staffing_mode"]: chips.append("Staff: " + p["staffing_mode"].replace("_", "-"))
if p["urgency"] == "emergency": chips.append("Urgency: emergency")
if p["sort"] == "nearest": chips.append("Sort: nearest")
st.markdown("  ".join(f"`{c}`" for c in chips) if chips else "_nothing recognised, try e.g. “dialysis near 110001”_")
if not p["capabilities"]:
    st.stop()

c = out.get("counts", {})
st.caption(f"{c.get('in_scope', 0)} facilities in scope · {c.get('with_any_evidence', 0)} have any evidence · "
           f"{c.get('verified', 0)} verified · {c.get('unverified', 0)} unverified · {c.get('rejected', 0)} rejected"
           + (f" · searched within {out['radius_km']} km" if out.get("radius_km") else ""))
if out.get("anchor"):
    st.caption(f"Distances are measured from {out['anchor'].get('basis', 'the search area')} "
               "(the average position of listings there, so approximate).")

def place(item):
    city, state = item.get("city") or "", item.get("state") or ""
    if not city or city.strip().lower() == str(state).strip().lower():
        return str(state)
    return f"{city}, {state}"

def card(item, expanded=False, nested=False):
    tier = item.get("tier", "Unverified")
    icon = {"Verified": "✅", "Partially verified": "🟡"}.get(tier, "⚪")
    title = f"{icon} {item['name']}  ·  {place(item)}"
    if nested:
        box = st.container(border=True)
        box.markdown(f"**{title}**")
    else:
        box = st.expander(title, expanded=expanded)
    with box:
        m1, m2, m3 = st.columns([2, 1, 1])
        m1.markdown(f"**Status**  \n{icon} {tier}")
        if item["distance_km"] is None:
            m2.markdown("**Distance**  \nn/a")
        else:
            m2.metric("Distance", f"{item['distance_km']} km")
        m3.metric("Trust", f"{item['trust']:.0f}/100")
        if item["distance_km"] is None:
            st.caption("Add a PIN code or city to the search to see distance.")
        st.caption(f"{item['type']} · PIN {item['pin']} · staff evidence: {item['staff_fit']} · trust is a heuristic, not a probability")
        for z in item["citations"]:
            st.markdown(f"**{z['capability']}** · {item['labels'].get(z['capability'], '')}")
            st.markdown(f"> {z['quote']}")
            st.caption(f"Source: dataset row {z['row_id']} · field `{z['field']}` · characters {z['chars'][0]}–{z['chars'][1]}")
        for m in item["missing"]:
            st.info(f"No evidence in the record for **{m}** (unknown, not proof that it is absent).")
        for fl in item["flags"]:
            st.warning(fl)
        for n in item.get("validator_notes", []):
            st.caption("🛡️ Validator: " + n)

# ---- 2. Results ----
st.subheader("2. Best-supported matches")
if out["results"]:
    for i, item in enumerate(out["results"]):
        card(item, expanded=(i == 0))
else:
    st.warning("No facility in this area has enough evidence for everything you asked. "
               "That is a data gap, not proof that care is unavailable. See the unverified list below, and call ahead.")

# ---- Map ----
pts = [dict(lat=x["lat"], lon=x["lon"]) for x in out["results"] + out["unverified"][:3] if x.get("lat")]
if out.get("anchor"):
    pts.append(dict(lat=float(out["anchor"]["lat"]), lon=float(out["anchor"]["lon"])))
if pts:
    st.map(pd.DataFrame(pts), latitude="lat", longitude="lon")

# ---- Unverified + why not ----
with st.expander(f"Unverified options ({len(out['unverified'])}): shown separately, not recommended"):
    for item in out["unverified"]:
        card(item, nested=True)
st.subheader("3. Why not these?")
if out["why_not"]:
    for w in out["why_not"]:
        d = "" if w["distance_km"] is None else f" ({w['distance_km']} km)"
        st.markdown(f"- **{w['name']}**{d}: {w['verdict']}. " + "; ".join(w["reasons"]))
else:
    st.caption("No near-miss facilities to explain.")

# ---- Unknowns ----
st.subheader("4. What we could not verify")
for u in out["unknowns"]:
    st.markdown(f"- {u}")

st.subheader("5. Validator log")
v = out["validator"]
if v["edits"]:
    st.warning(v["summary"])
    for e in v["edits"]:
        st.markdown(f"- `{e['check']}` **{e['action']}** · {e['facility']} · {e['capability'] or ''} · {e['reason']}")
else:
    st.success(v["summary"] + " Nothing needed changing.")
st.caption("Checks: V1 citation present · V2 quote found in the raw source cell · V3 claim derivable from the quote · "
           "V5 no live-availability wording · V8 unknowns never shown as verified · V9 photo-caption evidence flagged.")

with st.expander("How is the trust score calculated?"):
    st.markdown(
        "Heuristic score, **not** a probability.\n\n"
        "`trust = 100 × (0.30 evidence + 0.30 dependencies + 0.20 consistency + 0.10 freshness + 0.10 record quality)`\n\n"
        "- A missing required item (for example anaesthesia for surgery) caps trust at 60.\n"
        "- A contradicted claim caps trust at 40.\n"
        "- A missing required capability scales trust down.\n"
        "- Dependency rules are project rules, not clinical standards.")
