"""LLM layer (Gemini). The LLM never adds facts: it (1) parses free-text queries into the requirement JSON,
(2) summarises ALREADY-VALIDATED results in the user's language. Everything it returns is checked."""
import os, re, json
from geo import CANON

MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
CAPS = ["icu", "emergency", "dialysis", "oncology", "trauma", "surgery", "anaesthesia"]

def _key():
    k = os.environ.get("GEMINI_API_KEY")
    if k: return k
    try:
        import streamlit as st
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None

def available():
    return bool(_key())

def _ask(system, user, max_tokens=600):
    try:
        from google import genai
        from google.genai import types
        c = genai.Client(api_key=_key())
        r = c.models.generate_content(
            model=MODEL, contents=user,
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max(max_tokens, 2048), temperature=0.2))
        return (r.text or "").strip()
    except Exception as e:
        if os.environ.get("LLM_DEBUG"):          # set LLM_DEBUG=1 in Terminal to see the real error
            print("LLM error:", type(e).__name__, str(e)[:300])
        return None

def parse_llm(text):
    """Free text (any language) -> requirement dict, or None. Output is validated against allowed values."""
    sysmsg = ("Convert a healthcare search request in any language into JSON only, no other text. Keys: "
              f"capabilities (list from {CAPS}), state (an Indian state name in English or null), city (English or null), "
              "pin (6 digits or null), staffing_mode ('part_time','full_time' or null), urgent (true/false). "
              "Use only what the user said. Do not guess.")
    raw = _ask(sysmsg, text, 300)
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m: return None
    try: j = json.loads(m.group(0))
    except Exception: return None
    caps = [c for c in (j.get("capabilities") or []) if c in CAPS]
    if not caps: return None
    state = j.get("state"); state = state if state in CANON else None
    pin = str(j.get("pin") or ""); pin = pin if re.fullmatch(r"\d{6}", pin) else None
    city = j.get("city"); city = city.lower().strip() if isinstance(city, str) and city.strip() else None
    return {"raw": text, "capabilities": caps, "state": state, "city": None if pin else city, "pin": pin,
            "staffing_mode": j.get("staffing_mode") if j.get("staffing_mode") in ("part_time", "full_time") else None,
            "urgency": "emergency" if j.get("urgent") else "normal", "rural": False, "sort": "score",
            "unparsed_notes": ["understood by the AI assistant, please check the chips above"]}

LANG_EN = {"हिन्दी": "Hindi", "বাংলা": "Bengali", "தமிழ்": "Tamil", "తెలుగు": "Telugu", "मराठी": "Marathi",
           "ગુજરાતી": "Gujarati", "ಕನ್ನಡ": "Kannada", "മലയാളം": "Malayalam"}

def summarize(out, lang_name="English"):
    """Short grounded summary of validated results, or None if the guard rejects it."""
    if lang_name in LANG_EN:                      # e.g. 'हिन्दी' -> 'Hindi (हिन्दी)' so the model is never unsure
        lang_name = f"{LANG_EN[lang_name]} ({lang_name})"
    items = (out.get("results", [])[:3] + out.get("unverified", [])[:2])
    if not items: return None
    ev = [dict(name=i["name"], place=f"{i.get('city')}, {i.get('state')}", status=i.get("tier", "Unverified"),
               distance_km=i.get("distance_km"), labels=i["labels"], missing=i["missing"],
               quotes=[z["quote"] for z in i["citations"]], notes=i.get("validator_notes", [])) for i in items]
    sysmsg = (f"LANGUAGE RULE: write the whole reply in {lang_name}. Do not write in English unless {lang_name} is English. "
              "Only facility names and exact quotes stay as in the evidence. "
              f"Write 3 to 5 plain sentences in {lang_name} summarising these facility search results for a worried person. "
              "Never state how many facilities exist in total or how many are verified overall; "
              f"instead say, in {lang_name}, that these are among the top results. "
              "Use ONLY the evidence JSON. Never invent facilities, services, numbers or availability. "
              "Say clearly which are verified and which are not. Never say a service is available now. "
              "If you quote a record, copy the quote exactly in double quotes. End by telling them to phone the facility first "
              "and to call 112 in an emergency.")
    txt = _ask(sysmsg, f"Reply language: {lang_name}\nEvidence JSON:\n" + json.dumps(ev, ensure_ascii=False), 700)
    if not txt: return None
    allowed = " ".join(q for e in ev for q in e["quotes"]).lower()
    for q in re.findall(r"[\"“]([^\"”]{6,})[\"”]", txt):          # guard: every quote must exist in the evidence
        if q.lower() not in allowed:
            if os.environ.get("LLM_DEBUG"): print("Summary rejected, quote not in evidence:", q)
            return None
    if re.search(r"available now|open now|right now", txt, re.I):
        if os.environ.get("LLM_DEBUG"): print("Summary rejected, live-availability wording")
        return None
    return txt