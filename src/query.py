"""Rule-based query parser: text (English + a few Hindi words) -> structured requirement JSON.
The UI shows this BEFORE searching so the user can catch misreadings."""
import re
from geo import CANON, ALIAS

CAP_TERMS = {   # phrase -> list of required capabilities
 "appendectomy": ["surgery", "emergency"], "appendix": ["surgery", "emergency"],
 "dialysis": ["dialysis"], "डायलिसिस": ["dialysis"], "kidney": ["dialysis"],
 "icu": ["icu"], "intensive care": ["icu"], "critical care": ["icu"], "आईसीयू": ["icu"], "ventilator": ["icu"],
 "trauma": ["trauma"], "fracture": ["trauma"], "ट्रॉमा": ["trauma"],
 "cancer": ["oncology"], "oncology": ["oncology"], "chemotherapy": ["oncology"], "radiotherapy": ["oncology"], "कैंसर": ["oncology"],
 "surgery": ["surgery"], "operation": ["surgery"], "सर्जरी": ["surgery"], "ऑपरेशन": ["surgery"],
 "anaesthesia": ["anaesthesia"], "anesthesia": ["anaesthesia"],
 "emergency": ["emergency"], "casualty": ["emergency"], "इमरजेंसी": ["emergency"], "आपातकालीन": ["emergency"], "accident": ["emergency"],
}
HINDI_STATES = {"बिहार": "Bihar", "दिल्ली": "Delhi", "उत्तर प्रदेश": "Uttar Pradesh", "महाराष्ट्र": "Maharashtra", "राजस्थान": "Rajasthan",
                "गुजरात": "Gujarat", "केरल": "Kerala", "पंजाब": "Punjab", "हरियाणा": "Haryana", "झारखंड": "Jharkhand", "मध्य प्रदेश": "Madhya Pradesh"}
CITY_STOP = {"me", "my area", "my city", "an emergency", "emergency", "case of emergency", "need", "urgent", "time", "hurry"}

def has(term, t):
    """Whole-word match for Latin terms (so 'icu' does not match 'Calicut'); plain match for Devanagari."""
    if not term.isascii():
        return term in t
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?:s|es)?(?![a-z0-9])", t) is not None

def parse(text):
    t = text.lower()
    req = {"raw": text, "capabilities": [], "state": None, "city": None, "pin": None, "staffing_mode": None,
           "urgency": "normal", "rural": False, "sort": "score", "unparsed_notes": []}
    for term in sorted(CAP_TERMS, key=len, reverse=True):
        if has(term, t):
            for c in CAP_TERMS[term]:
                if c not in req["capabilities"]: req["capabilities"].append(c)
    m = re.search(r"\b(\d{6})\b", t)
    if m: req["pin"] = m.group(1)
    for hi, st in HINDI_STATES.items():
        if hi in text: req["state"] = st
    for st in sorted(CANON, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(st.lower()) + r"(?![a-z])", t): req["state"] = st; break
    if not req["state"]:
        for a, st in ALIAS.items():
            if len(a) > 3 and re.search(r"(?<![a-z])" + re.escape(a) + r"(?![a-z])", t): req["state"] = st; break
    cm = re.search(r"\b(?:in|near|around|at)\s+([a-z][a-z .-]{2,25}?)(?:,|\s+(?:with|that|who|and|for|having|which)\b|$)", t)
    if cm and not req["pin"]:
        cand = cm.group(1).strip()
        if (cand not in {s.lower() for s in CANON} and cand not in ALIAS and cand not in CITY_STOP
                and not cand.startswith(("rural", "urban", "the ", "an ", "a ", "my "))):
            req["city"] = cand
    if re.search(r"part[- ]time|visiting|on[- ]call|consultant visits", t): req["staffing_mode"] = "part_time"
    elif re.search(r"full[- ]time|resident|24 ?x ?7 doctor", t): req["staffing_mode"] = "full_time"
    if re.search(r"urgent|emergency|immediately|right now|severe|आपातकालीन|इमरजेंसी", t): req["urgency"] = "emergency"
    if re.search(r"rural|village|gaon|गाँव|ग्रामीण", t): req["rural"] = True
    if re.search(r"nearest|closest|near me|nearby|पास", t): req["sort"] = "nearest"
    if req["rural"]: req["unparsed_notes"].append("'rural' cannot be verified: the dataset has no urban/rural field, so it is not used as a filter")
    if not req["capabilities"]: req["unparsed_notes"].append("no capability recognised")
    return req
