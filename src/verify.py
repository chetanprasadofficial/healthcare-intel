"""Verify: claims.csv + raw data -> facility table, per-facility capability verdicts, flags.
Usage: python src/verify.py data/<file>.csv
Writes: data/facilities.csv, data/facility_caps.csv, data/flags.csv
Trust is a HEURISTIC score (not a calibrated probability).
A capability that is both supported AND contradicted in the same record becomes 'Conflicting notes' (never verified)."""
import re, sys, json, yaml, pandas as pd

RULES = yaml.safe_load(open("config/capability_rules.yaml"))
W, FRESH_M = RULES["weights"], RULES["freshness_months"]
TEXT_COLS = ["capability", "procedure", "equipment", "description", "specialties"]

def rx(words):
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z0-9])")

DEP_RX = {cap: {kind: {name: rx(ws) for name, ws in d.items()}
                for kind, d in spec.items()} for cap, spec in RULES["rules"].items()}

def row_text(row):
    parts = []
    for c in TEXT_COLS:
        v = row.get(c)
        if isinstance(v, str):
            try: parts += [str(x) for x in json.loads(v)]
            except Exception: parts.append(v)
    return " | ".join(parts).lower()

def freshness(row, ref):
    d = pd.to_datetime(row.get("recency_of_page_update"), errors="coerce")
    if pd.isna(d): return 0.6, "unknown"
    months = (ref - d).days / 30.4
    return (1.0, "fresh") if months <= FRESH_M else (0.4, "stale")

def quality(row):
    ok = [pd.notna(row.get("latitude")), pd.notna(row.get("address_zipOrPostcode")),
          pd.notna(row.get("facilityTypeId")), len(row_text(row)) > 150]
    return sum(ok) / len(ok)

def main(path):
    df = pd.read_csv(path, low_memory=False).reset_index(drop=True)
    df.index.name = "row_id"
    claims = pd.read_csv("data/claims.csv")
    ref = pd.to_datetime(df["recency_of_page_update"], errors="coerce").max()

    fac_out = df.loc[df.facilityTypeId.isin(["hospital", "clinic", "doctor"]),
        ["name", "facilityTypeId", "operatorTypeId", "address_city", "address_stateOrRegion",
         "address_zipOrPostcode", "latitude", "longitude"]].reset_index()
    fac_out.to_csv("data/facilities.csv", index=False)

    out, flags = [], []
    for (rid, cap), g in claims.groupby(["row_id", "capability"]):
        row = df.loc[rid]; text = row_text(row)
        stat = set(g.status)
        if "supported" in stat: status = "supported"
        elif "mentioned_only" in stat: status = "mentioned_only"
        else: status = "contradicted"
        conflict = ("contradicted" in stat) and bool(stat & {"supported", "mentioned_only"})
        pick = status                                   # which claim rows to quote
        if conflict and status == "supported":
            status = "mentioned_only"                   # a denial in the same record: never "supported"
        best = (g[g.status == pick].assign(w=lambda x: (x.term_strength == "strong").astype(int))
                .sort_values("w", ascending=False).iloc[0])
        spec = DEP_RX.get(cap, {"hard": {}, "soft": {}})
        hard = {n: bool(r.search(text)) for n, r in spec["hard"].items()}
        soft = {n: bool(r.search(text)) for n, r in spec["soft"].items()}
        missing = [n for n, ok in hard.items() if not ok]
        D = (sum(hard.values()) / len(hard)) if hard else 1.0
        D = min(1.0, D + 0.05 * sum(soft.values()))
        E = {"supported": 1.0, "mentioned_only": 0.6 if best.term_strength == "strong" else 0.4}.get(status, 0.0)
        K = 1.0
        row_flags = []
        if conflict: K -= 0.4; row_flags.append(("polarity_conflict", "high", "claim both asserted and negated/planned in notes"))
        if missing and status != "contradicted":
            K -= 0.2; row_flags.append(("dependency_gap", "high" if status == "supported" else "low",
                                        "not evidenced in record: " + ", ".join(missing)))
        ftype = row["facilityTypeId"]
        if cap in RULES["type_mismatch"].get(ftype, []) and status == "supported":
            K -= 0.2; row_flags.append(("type_mismatch", "medium", f"{ftype} listing claims {cap}"))
        F, fresh = freshness(row, ref); Q = quality(row)
        T = 100 * (W["evidence"] * E + W["dependencies"] * D + W["consistency"] * max(K, 0) + W["freshness"] * F + W["quality"] * Q)
        if status == "contradicted": T = min(T, 40)
        elif conflict: T = min(T, 45)
        elif missing: T = min(T, 60)
        label = ("Conflicting notes" if conflict and status != "contradicted" else
                 {"supported": "Supported" if not missing else "Partially supported",
                  "mentioned_only": "Mentioned only", "contradicted": "Contradicted"}[status])
        out.append(dict(row_id=rid, name=row["name"], facility_type=ftype, state=row["address_stateOrRegion"],
                        city=row["address_city"], pin=row["address_zipOrPostcode"], lat=row["latitude"], lon=row["longitude"],
                        capability=cap, status=status, label=label, trust=round(T, 1),
                        deps_found=",".join(n for n, ok in hard.items() if ok), deps_missing=",".join(missing),
                        staffing_mode=best.staffing_mode, freshness=fresh, quote=best.quote,
                        quote_field=best.field, char_start=best.char_start, char_end=best.char_end))
        for t, sev, d in row_flags:
            flags.append(dict(row_id=rid, name=row["name"], capability=cap, flag=t, severity=sev, detail=d))
    pd.DataFrame(out).to_csv("data/facility_caps.csv", index=False)
    pd.DataFrame(flags).to_csv("data/flags.csv", index=False)
    o = pd.DataFrame(out); f = pd.DataFrame(flags)
    print("facility-capability verdicts:", len(o)); print(o.label.value_counts().to_string())
    print("\nflags:"); print(f.groupby(["flag", "severity"]).size().to_string())

if __name__ == "__main__":
    main(sys.argv[1])
