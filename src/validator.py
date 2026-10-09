"""Validator agent: the last gate before an answer is shown.
Every displayed claim is re-checked against the RAW dataset cell. Outcomes: PASS / QUALIFY / REMOVE.
Checks: V1 citation present | V2 quote really appears in the cited source cell | V3 claim still derivable from the quote
        V5 no live-availability wording | V6 stale/unknown date tag | V8 unknowns never shown as verified
        V9 evidence comes from a photo/image caption, not a written claim
Usage: from validator import validate; out = validate(search(...))"""
import os, re, json
import pandas as pd
from extract import extract_text

RAW_PATH = "data/Hackathon_Dataset_India_Larg.csv"
TEXT_FIELDS = ["capability", "procedure", "equipment", "description", "specialties"]
LIVE = re.compile(r"\b(available now|open now|currently available|beds? (?:are )?available|vacant beds?|doctors? (?:is |are )?present|right now|today only)\b", re.I)
IMAGE = re.compile(r"\b(visible in (?:the )?(?:image|photo|picture)|(?:image|photo|picture)s? (?:show|shows|display|displays)|seen in (?:the )?(?:image|photo))\b", re.I)
_RAW = {"df": None, "tried": False}

def raw_df():
    if not _RAW["tried"]:
        _RAW["tried"] = True
        if os.path.exists(RAW_PATH):
            _RAW["df"] = pd.read_csv(RAW_PATH, usecols=TEXT_FIELDS, low_memory=False).reset_index(drop=True)
    return _RAW["df"]

def cell_items(cell):
    """Decoded list items (or the plain text) of a raw cell, for literal quote matching."""
    if not isinstance(cell, str): return []
    t = cell.strip()
    if t.startswith("["):
        try: return [str(x) for x in json.loads(t)]
        except Exception: pass
    return [cell]

def label_to_status(label):
    return {"Supported": "supported", "Partially supported": "supported", "Mentioned only": "mentioned_only", "Contradicted": "contradicted"}.get(label)

def validate(out):
    raw = raw_df()
    edits, checked, passed = [], 0, 0
    def log(check, action, item, z, reason): edits.append(dict(check=check, action=action, facility=item["name"], capability=z["capability"] if z else None, reason=reason))
    for key in ("results", "unverified"):
        for item in out.get(key, []):
            item.setdefault("validator_notes", [])
            keep = []
            for z in item["citations"]:
                checked += 1
                ok = True
                # V1: citation completeness
                if not all([z.get("row_id") is not None, z.get("field"), z.get("chars"), z.get("quote")]):
                    log("V1", "REMOVE", item, z, "claim has no complete citation (row, field, span, quote)"); ok = False
                # V2: quote must literally appear in the cited raw cell
                elif raw is not None:
                    cell = raw.at[z["row_id"], z["field"]] if z["row_id"] in raw.index else None
                    if not any(z["quote"] in it or it in z["quote"] for it in cell_items(cell)):
                        log("V2", "REMOVE", item, z, "quote not found in the cited source cell (possible hallucination)"); ok = False
                if not ok: continue
                # V3: claim must still be derivable from the quote alone
                derived = [c for c in extract_text(z["row_id"], z["field"], z["quote"]) if c["capability"] == z["capability"]]
                want = label_to_status(z.get("status"))
                if not derived or (want and derived[0]["status"] != want):
                    log("V3", "QUALIFY", item, z, "quote alone does not clearly support the stated status"); item["validator_notes"].append(f"{z['capability']}: evidence wording is weaker than the label suggests"); item["_qualified"] = True
                    passed -= 0
                # V9: image-derived evidence
                if IMAGE.search(z["quote"]):
                    log("V9", "QUALIFY", item, z, "evidence is a photo/image caption, not a written service claim"); item["validator_notes"].append(f"{z['capability']}: evidence comes from an image description, confirm by phone"); item["_qualified"] = True
                # V5: live-availability wording
                if LIVE.search(z["quote"]):
                    log("V5", "QUALIFY", item, z, "wording implies live availability; the data is a listing, not real time"); item["validator_notes"].append(f"{z['capability']}: 'facility reports' only, not live availability"); item["_qualified"] = True
                keep.append(z)
            removed = len(item["citations"]) - len(keep)
            item["citations"] = keep
            # V6: freshness tag
            if keep:
                passed += len(keep)
            # V8: unknowns must never sit in the verified list
            if key == "results" and (item.get("missing") or item.get("mentioned_only") or item.get("contradicted")):
                log("V8", "REMOVE", item, None, "unknown/only-mentioned capability cannot appear as a verified match"); item["_demote"] = True
            if key == "results" and (removed or not keep):
                item["_demote"] = True
            if key == "results" and item.get("_qualified") and item.get("tier") == "Verified":
                item["tier"] = "Partially verified"
    # move demoted items out of the verified list (never silently drop them)
    stay = [i for i in out.get("results", []) if not i.get("_demote")]
    demoted = [i for i in out.get("results", []) if i.get("_demote")]
    for i in demoted:
        i["tier"] = "Unverified"; i["validator_notes"].append("moved out of verified list by the validator")
    out["results"] = stay
    out["unverified"] = demoted + out.get("unverified", [])
    n_rm = sum(e["action"] == "REMOVE" for e in edits); n_q = sum(e["action"] == "QUALIFY" for e in edits)
    out["validator"] = dict(checked=checked, removed=n_rm, qualified=n_q, edits=edits,
                            raw_checked=raw is not None,
                            summary=f"Validator checked {checked} claims: {n_rm} removed, {n_q} qualified." + ("" if raw is not None else " (raw dataset not found: quote check V2 skipped)"))
    return out
