"""Rule-first extractor: notes -> claims with status, quote, field, char span.
Usage: python src/extract.py data/india10k.csv NOTES_COL [NOTES_COL2 ...]
Statuses: supported | mentioned_only | contradicted   (unknown = no claim row at all)"""
import re, sys, json, yaml, pandas as pd

CFG = yaml.safe_load(open("config/lexicons.yaml"))
CAPS, NEG, HEDGE = CFG["capabilities"], CFG["negation"], CFG["hedge"]
STAFF, DETAIL = CFG["staffing"], CFG["detail_cues"]

def term_re(terms):
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(t.lower()) for t in terms) + r")(?![a-z0-9])")

CAP_RE = {k: term_re(v) for k, v in CAPS.items()}
NEG_RE, HEDGE_RE, DETAIL_RE = term_re(NEG), term_re(HEDGE), term_re(DETAIL)
STAFF_RE = {k: term_re(v) for k, v in STAFF.items()}

def sentences(text):
    """Yield (start, end, unit). Dataset fields are JSON lists of short facts, so each
    list item is one citable unit (offsets point into the raw cell text)."""
    t = text.strip()
    if t.startswith("["):
        try:
            items = json.loads(t)
            pos = 0
            for it in items:
                it = str(it)
                i = text.find(it, pos)
                if i < 0: i = pos
                pos = i + len(it)
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

def classify(sl, m):
    before = sl[max(0, m.start() - 30): m.start()]
    after = sl[m.end(): m.end() + 15]
    if NEG_RE.search(before) or NEG_RE.search(after) or HEDGE_RE.search(sl):
        return "contradicted"
    if re.search(r"\d", sl) or DETAIL_RE.search(sl):
        return "supported"
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
        for cap, rx in CAP_RE.items():
            m = rx.search(sl)
            if m:
                claims.append(dict(row_id=row_id, capability=cap, status=classify(sl, m),
                                   quote=sent.strip(), field=field, char_start=s, char_end=e,
                                   staffing_mode=staffing(sl), method="rule"))
    return claims

def run(df, cols):
    out = []
    for rid, row in df.iterrows():
        for c in cols: out += extract_text(rid, c, row[c])
    return pd.DataFrame(out)

if __name__ == "__main__":
    path, cols = sys.argv[1], sys.argv[2:]
    df = pd.read_csv(path, low_memory=False)
    df = df.reset_index(drop=True)
    df.index.name = "row_id"
    claims = run(df, cols)
    claims.to_csv("data/claims.csv", index=False)
    print(claims.status.value_counts(), "\n", claims.capability.value_counts())
