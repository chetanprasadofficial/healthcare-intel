"""Rule-first extractor v2.2: notes -> claims with status, quote, field, char span.
Usage: python src/extract.py data/<file>.csv NOTES_COL [NOTES_COL2 ...]
Statuses: supported | mentioned_only | contradicted   (unknown = no claim row at all)
v2.1: direct assertions ("ICU available") count as supported; short "A, B and C" lists are list-like.
v2.2: whole-word marketing/list cues; "24x7" alone is not emergency care; correct char spans for JSON items."""
import re, sys, json, yaml, pandas as pd

CFG = yaml.safe_load(open("config/lexicons.yaml"))
CAPS, NEG, HEDGE = CFG["capabilities"], CFG["negation"], CFG["hedge"]
STAFF, DETAIL = CFG["staffing"], CFG["detail_cues"]
EXCL, LIST_CUES = CFG.get("exclude_context", {}), CFG["list_cues"]
MARKETING = CFG.get("marketing_cues", [])
KEEP = set(CFG["keep_facility_types"])

def term_re(terms):
    if not terms: return None
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(str(t).lower()) for t in terms) + r")(?![a-z0-9])")

STRONG = {k: term_re(v["strong"]) for k, v in CAPS.items()}
WEAK = {k: term_re(v["weak"]) for k, v in CAPS.items()}
EXCL_RE = {k: term_re(v) for k, v in EXCL.items()}
NEG_RE, HEDGE_RE = term_re(NEG), term_re(HEDGE)
DETAIL_RE = term_re([d for d in DETAIL if not str(d).startswith("24")])   # "24x7" is not equipment/detail
MARKETING_RE, LIST_RE = term_re(MARKETING), term_re(LIST_CUES)
ASSERT_RE = term_re(["available", "offers", "provides", "has", "equipped"])
STAFF_RE = {k: term_re(v) for k, v in STAFF.items()}
NO_NUMBER = re.compile(r"\bno\.?\s*(1|one|\d+)\b|\bnumber\s*1\b")   # "India's No 1 ..." is marketing
EMERG_CTX = re.compile(r"emergency|casualty|accident|trauma")

def sentences(text):
    """Yield (start, end, unit). Dataset fields are JSON lists of short facts, so each
    list item is one citable unit (offsets point into the raw cell text)."""
    t = text.strip()
    if t.startswith("["):
        try:
            pos = 0
            for it in json.loads(t):
                it = str(it)
                i, n = -1, len(it)
                for cand in (json.dumps(it, ensure_ascii=False)[1:-1], json.dumps(it)[1:-1], it):
                    i = text.find(cand, pos)
                    if i >= 0: n = len(cand); break
                if i < 0: i = pos
                pos = i + n
                yield i, pos, it
            return
        except Exception:
            pass
    pos = 0
    for part in re.split(r"(?<=[.;\n])\s+", text):
        i = text.find(part, pos)
        if i < 0: continue
        pos = i + len(part)
        yield i, pos, part

def is_list_like(sl, n_caps):
    return (n_caps >= 3 or sl.count("|") >= 2 or sl.count(",") >= 4
            or sl.count(",") + sl.count(" and ") >= 2
            or bool(LIST_RE and LIST_RE.search(sl)))

def negated(sl, m):
    before = " ".join(sl[:m.start()].split()[-4:])
    rest = re.sub(r"\bwithout (any )?(extra|additional|delay|waiting|appointment)\w*", " ", sl[m.end():])
    after = " ".join(rest.split()[:3])
    before = NO_NUMBER.sub(" ", before)
    return bool(NEG_RE.search(before) or NEG_RE.search(after))

def hedged(sl, m):
    window = " ".join(sl[:m.start()].split()[-5:]) + " | " + " ".join(sl[m.end():].split()[:5])
    return bool(HEDGE_RE.search(window))

BOILER = re.compile(r"call 911|emergency information|emergency appointments?|has performed|performed \d|sessions? (?:last|are)|we are seeking")
SHORT_FIELDS = {"capability", "procedure", "equipment"}
BED_RE = re.compile(r"\b\d+[- ]?(?:bed|beds|machine|machines)\b")

def classify(sl, m, strong, list_like, field=""):
    if negated(sl, m) or hedged(sl, m): return "contradicted"
    if BOILER.search(sl): return "mentioned_only"
    if not strong or list_like or (MARKETING_RE and MARKETING_RE.search(sl)): return "mentioned_only"
    if DETAIL_RE.search(sl) or ASSERT_RE.search(sl) or BED_RE.search(sl): return "supported"
    if field in SHORT_FIELDS and len(sl.split()) <= 8: return "supported"   # short direct item, e.g. "Day care chemotherapy centre"
    return "mentioned_only"

def staffing(sl):
    for mode, rx in STAFF_RE.items():
        if rx.search(sl): return mode
    return "unknown"

def extract_text(row_id, field, text):
    claims = []
    if not isinstance(text, str): return claims
    for s, e, sent in sentences(text):
        sl = sent.lower()
        hits = {}
        for cap in CAPS:
            if cap in EXCL_RE and EXCL_RE[cap] and EXCL_RE[cap].search(sl): continue
            m = STRONG[cap].search(sl)
            if m and cap == "emergency" and not EMERG_CTX.search(sl):
                m = None          # "24x7 pharmacy" / "round the clock lab" is not emergency care
            if m: hits[cap] = (m, True); continue
            if WEAK[cap]:
                m = WEAK[cap].search(sl)
                if m: hits[cap] = (m, False)
        list_like = is_list_like(sl, len(hits))
        for cap, (m, strong) in hits.items():
            claims.append(dict(row_id=row_id, capability=cap, status=classify(sl, m, strong, list_like, field),
                               quote=sent.strip(), field=field, char_start=s, char_end=e,
                               staffing_mode=staffing(sl), term_strength="strong" if strong else "weak",
                               list_like=list_like, method="rule"))
    return claims

def run(df, cols):
    out = []
    for rid, row in df.iterrows():
        for c in cols: out += extract_text(rid, c, row[c])
    return pd.DataFrame(out)

if __name__ == "__main__":
    path, cols = sys.argv[1], sys.argv[2:]
    df = pd.read_csv(path, low_memory=False).reset_index(drop=True)
    df.index.name = "row_id"
    n0 = len(df)
    df = df[df["facilityTypeId"].isin(KEEP)]            # drop dentist / pharmacy rows
    print(f"Rows kept: {len(df)} of {n0} (types: {sorted(KEEP)})")
    claims = run(df, cols)
    claims.to_csv("data/claims.csv", index=False)
    print(claims.status.value_counts(), "\n", claims.capability.value_counts())
