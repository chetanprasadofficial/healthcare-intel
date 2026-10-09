"""Search: requirement JSON -> ranked, cited results + why-not table + unknowns.
Usage: python src/search.py "emergency appendectomy in rural Bihar with part-time doctors" """
import sys, json, pandas as pd
from geo import clean_geo, haversine
from query import parse

W = dict(match=0.40, prox=0.25, staff=0.15, fresh=0.10, complete=0.10)
FRESH = {"fresh": 1.0, "unknown": 0.6, "stale": 0.4}
GATE = 50          # minimum MatchTrust for the verified list (project rule)

class Index:
    def __init__(self):
        self.fac = clean_geo(pd.read_csv("data/facilities.csv", low_memory=False)).set_index("row_id")
        self.caps = pd.read_csv("data/facility_caps.csv")
        self.flags = pd.read_csv("data/flags.csv")
    def centroid(self, req):
        f = self.fac
        if req["pin"]:
            for n in (6, 5, 4, 3):
                s = f[f.pin.str.startswith(req["pin"][:n], na=False)]
                if len(s) >= 1: return s.latitude.mean(), s.longitude.mean(), f"PIN {req['pin'][:n]}*"
        if req["city"]:
            s = f[f.address_city.str.lower().str.contains(req["city"], na=False)]
            if len(s): return s.latitude.mean(), s.longitude.mean(), f"city '{req['city']}'"
        return None

def citations(caps_rows):
    return [dict(capability=r.capability, status=r.label, quote=r.quote, row_id=int(r.row_id), field=r.quote_field,
                 chars=[int(r.char_start), int(r.char_end)]) for r in caps_rows.itertuples()]

def search(text, k=5, idx=None):
    idx = idx or Index()
    req = parse(text)
    out = dict(parsed=req, results=[], unverified=[], why_not=[], unknowns=[], anchor=None)
    if not req["capabilities"]: return out
    f = idx.fac
    pool = f
    if req["state"]: pool = pool[pool.state_clean == req["state"]]
    anchor = idx.centroid(req)
    if anchor: out["anchor"] = dict(lat=anchor[0], lon=anchor[1], basis=anchor[2])
    caps = idx.caps[idx.caps.row_id.isin(pool.index) & idx.caps.capability.isin(req["capabilities"])]
    if req["urgency"] == "emergency" and "emergency" not in req["capabilities"]:
        pass   # urgency is shown to the user; it does not silently add requirements
    cands = []
    for rid, g in caps.groupby("row_id"):
        have = {r.capability: r for r in g.itertuples()}
        row = f.loc[rid]
        dist = haversine(anchor[0], anchor[1], row.latitude, row.longitude) if anchor else None
        missing = [c for c in req["capabilities"] if c not in have]
        contradicted = [c for c, r in have.items() if r.status == "contradicted"]
        mentioned = [c for c, r in have.items() if r.status == "mentioned_only"]
        found = len(have) / len(req["capabilities"])
        trust = min((r.trust for r in have.values()), default=0) * found   # a missing required capability lowers trust
        staff_modes = [r.staffing_mode for r in have.values() if r.staffing_mode != "unknown"]
        want = req["staffing_mode"]
        S = 0.5 if not want else (1.0 if want in staff_modes else (0.0 if staff_modes else 0.5))
        fresh = FRESH.get(g.freshness.iloc[0], 0.6)
        P = 1 / (1 + dist / 25) if dist is not None else 0.5
        score = 100 * (W["match"] * trust / 100 + W["prox"] * P + W["staff"] * S + W["fresh"] * fresh + W["complete"] * 1.0)
        fl = idx.flags[(idx.flags.row_id == rid) & idx.flags.capability.isin(req["capabilities"])]
        item = dict(row_id=int(rid), name=row["name"], type=row.facilityTypeId, city=row.address_city, state=row.state_clean,
                    pin=row.pin, distance_km=None if dist is None else round(dist, 1), trust=round(trust, 1), score=round(score, 1),
                    labels={c: r.label for c, r in have.items()}, citations=citations(g),
                    flags=[f"{a.flag}: {a.detail}" for a in fl.itertuples()], staff_fit={1.0: "evidenced", 0.5: "unknown", 0.0: "conflicting"}[S],
                    missing=missing, contradicted=contradicted, mentioned_only=mentioned)
        cands.append(item)
    radius_note = None
    if anchor:   # keep results near the user; widen only if nothing is found, and say so
        for R in (50, 150, 300, 600):
            near = [c for c in cands if c["distance_km"] is not None and c["distance_km"] <= R]
            if any(not c["missing"] and not c["contradicted"] and not c["mentioned_only"] and c["trust"] >= GATE for c in near) or R == 600:
                break
        cands = near
        out["radius_km"] = R
        if not any(not c["missing"] and not c["contradicted"] for c in cands):
            radius_note = f"no verified match within {R} km"
        elif R > 50:
            radius_note = f"nothing verified within 50 km, so the search was widened to {R} km"
    verified = [c for c in cands if not c["missing"] and not c["contradicted"] and not c["mentioned_only"] and c["trust"] >= GATE]
    for c in verified:
        c["tier"] = "Verified" if all(v == "Supported" for v in c["labels"].values()) else "Partially verified"
    unverified = [c for c in cands if not c["contradicted"] and c not in verified]
    rejected = [c for c in cands if c["contradicted"]]
    key = (lambda c: (c["distance_km"] is None, c["distance_km"] or 0)) if req["sort"] == "nearest" else (lambda c: -c["score"])
    verified.sort(key=key); unverified.sort(key=lambda c: -c["score"])
    out["results"], out["unverified"] = verified[:k], unverified[:k]
    for c in unverified[:3]:
        why = [f"{x}: only mentioned, no supporting detail" for x in c["mentioned_only"]] + [f"{x}: no evidence in record (unknown)" for x in c["missing"]]
        out["why_not"].append(dict(name=c["name"], distance_km=c["distance_km"], verdict="Unverified, not recommended", reasons=why))
    for c in rejected[:3]:
        why = [f"{x}: contradicted: \"{next(z['quote'] for z in c['citations'] if z['capability']==x)[:80]}\"" for x in c["contradicted"]]
        out["why_not"].append(dict(name=c["name"], distance_km=c["distance_km"], verdict="Rejected", reasons=why))
    out["counts"] = dict(in_scope=len(pool), with_any_evidence=len(cands), verified=len(verified), unverified=len(unverified), rejected=len(rejected))
    if req["sort"] == "nearest" and not anchor:
        req["unparsed_notes"].append("'nearest' needs a location: give a PIN code or city (or share device location in the app); distances are not shown without it")
    if radius_note: req["unparsed_notes"].append(radius_note)
    out["unknowns"] = ["Live bed / doctor / oxygen availability is not in the data. Call the facility before travelling.",
                       "Most records have no update date, so freshness is mostly unknown."] + req["unparsed_notes"]
    return out

def show(o):
    p = o["parsed"]
    print("PARSED:", {k: v for k, v in p.items() if k not in ("raw", "unparsed_notes") and v not in (None, [], False)})
    print("ANCHOR:", o["anchor"]); print("COUNTS:", o.get("counts"))
    for title, lst in (("VERIFIED", o["results"]), ("UNVERIFIED (shown separately)", o["unverified"])):
        print(f"\n== {title} ==")
        for c in lst[:3]:
            print(f"- {c.get('tier','Unverified')}: {c['name']} | {c['city']}, {c['state']} {c['pin']} | {c['distance_km']} km | trust {c['trust']} | score {c['score']} | {c['labels']}")
            for z in c["citations"][:2]: print(f"    [{z['capability']}] row {z['row_id']} {z['field']}{z['chars']}: \"{z['quote'][:90]}\"")
            for fl in c["flags"][:2]: print("    flag:", fl)
    print("\n== WHY NOT ==")
    for w in o["why_not"]: print(f"- {w['name']} ({w['distance_km']} km) {w['verdict']}: {'; '.join(w['reasons'])[:170]}")
    print("\nUNKNOWNS:", *o["unknowns"], sep="\n  - ")

if __name__ == "__main__":
    show(search(" ".join(sys.argv[1:])))
