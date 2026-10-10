"""Healthcare Intelligence (PS-03) - Streamlit app.
Run from the project root:  streamlit run app/streamlit_app.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd
import streamlit as st
from search import search, Index
from validator import validate
from i18n import LANGS, t

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

LANG = st.selectbox("🌐 Language / भाषा", list(LANGS), format_func=lambda c: LANGS[c], key="lang")
st.title("🏥 " + t("title", LANG))
st.caption(t("caption", LANG))
st.error(t("emergency", LANG))

if "q" not in st.session_state:
    st.session_state.q = SAMPLES[0]

with st.sidebar:
    st.header(t("examples", LANG))
    for s in SAMPLES:
        if st.button(s, key="ex_" + s):
            st.session_state.q = s
    st.markdown("---")
    st.caption("Tip: add a PIN code or city for distances, e.g. *dialysis near 110001*.")

with st.form("search_form"):
    q = st.text_input(t("q_label", LANG), value=st.session_state.q)
    go = st.form_submit_button(t("search", LANG))
if go:
    st.session_state.q = q

idx = load_index()
query = st.session_state.q.strip()
if not query:
    st.stop()

out = validate(search(query, k=12, idx=idx), k=5)   # every claim passes the validator before display
p = out["parsed"]

# ---- 1. What we understood (shown BEFORE results) ----
st.subheader(t("s1", LANG))
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

if out.get("radius_note"):
    st.warning(out["radius_note"])

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
        tier_t = {"Verified": t("verified", LANG), "Partially verified": t("partial", LANG)}.get(tier, t("unverified", LANG))
        m1.markdown(f"**{t('status', LANG)}**  \n{icon} {tier_t}")
        if item["distance_km"] is None:
            m2.markdown(f"**{t('distance', LANG)}**  \nn/a")
        else:
            m2.metric(t("distance", LANG), f"{item['distance_km']} km")
        m3.metric(t("trust", LANG), f"{item['trust']:.0f}/100")
        if item["distance_km"] is None:
            st.caption(t("add_pin", LANG))
        st.caption(f"{item['type']} · PIN {item['pin']} · staff evidence: {item['staff_fit']} · trust is a heuristic, not a probability")
        for z in item["citations"]:
            st.markdown(f"**{z['capability']}** · {item['labels'].get(z['capability'], '')}")
            st.markdown(f"> {z['quote']}")
            st.caption(f"{t('source', LANG)} {z['row_id']} · field `{z['field']}` · characters {z['chars'][0]}–{z['chars'][1]}")
        for m in item["missing"]:
            st.info(f"No evidence in the record for **{m}** (unknown, not proof that it is absent).")
        for fl in item["flags"]:
            st.warning(fl)
        for n in item.get("validator_notes", []):
            st.caption("🛡️ Validator: " + n)

# ---- 2. Results ----
st.subheader(t("s2", LANG))
if out["results"]:
    for i, item in enumerate(out["results"]):
        card(item, expanded=(i == 0))
else:
    st.warning(t("no_results", LANG))

# ---- Map ----
pts = [dict(lat=x["lat"], lon=x["lon"]) for x in out["results"] + out["unverified"][:3] if x.get("lat")]
if out.get("anchor"):
    pts.append(dict(lat=float(out["anchor"]["lat"]), lon=float(out["anchor"]["lon"])))
if pts:
    st.map(pd.DataFrame(pts), latitude="lat", longitude="lon")

# ---- Unverified + why not ----
with st.expander(f"{t('unver_exp', LANG)} ({len(out['unverified'])})"):
    for item in out["unverified"]:
        card(item, nested=True)
st.subheader(t("s3", LANG))
if out["why_not"]:
    for w in out["why_not"]:
        d = "" if w["distance_km"] is None else f" ({w['distance_km']} km)"
        st.markdown(f"- **{w['name']}**{d}: {w['verdict']}. " + "; ".join(w["reasons"]))
else:
    st.caption("No near-miss facilities to explain.")

# ---- Unknowns ----
st.subheader(t("s4", LANG))
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
