# 🏥 Healthcare Intelligence (PS-03) - Chilli Coders

**Find healthcare facilities whose claimed capabilities are backed by evidence, not just listed.**

**Live demo:** https://healthcare-intel-l9ebv6gzbbackls36rmadz.streamlit.app/

> ⚠️ This is a research prototype. It does not know whether a service is available right now. Always phone the facility first, and call **112** in an emergency.

---

## The problem

Facility directories list services, but a listing is not proof. A hospital may be tagged "ICU" or "dialysis" with nothing in its record to support it, and a worried patient cannot tell which entries to trust. Large parts of the country also have no verified facility for critical services at all.

## What this does

You describe what you need in plain language, in any of 9 languages (for example *"dialysis near 110001"* or *"मुझे बिहार में डायलिसिस चाहिए"*). The app:

1. **Shows what it understood** (capabilities, state, PIN, city, urgency, staffing) before showing any result.
2. **Returns ranked facilities with cited evidence.** Every claim is a verbatim quote from the source record, with its row ID, field and character range.
3. **Marks each facility** as Verified, Partially verified or Unverified, with a trust score.
4. **Explains what is missing and why near-misses were excluded**, and treats missing evidence as *unknown*, never as proof of absence.
5. **Maps medical deserts** on a separate page, in 9 languages.

## How it works

```
raw dataset ──► extract ──► claims ──► verify ──► facility table + capability verdicts + flags
                                                          │
 user query ──► parse (rules, optional Gemini) ──► search ──► VALIDATOR ──► UI
```

| Stage | What it does | Code |
|---|---|---|
| Extract | Pulls capability claims, with exact quotes, from free-text fields | `src/extract.py` |
| Verify | Builds per-facility capability verdicts, dependency checks and flags | `src/verify.py` |
| Search | Matches the parsed query to facilities, with distance from a PIN or city | `src/search.py`, `src/geo.py`, `src/query.py` |
| **Validator** | Re-checks every claim before it is displayed (see below) | `src/validator.py` |
| AI layer | Gemini parses free-text queries and writes a short summary | `src/llm.py` |
| Desert map | Finds areas lacking verified capability | `src/deserts.py` |
| UI | Streamlit app, 9 languages | `app/streamlit_app.py`, `app/pages/2_Desert_map.py`, `src/i18n.py`, `src/desert_i18n.py` |

### The validator (nothing is shown unchecked)

| Check | Rule |
|---|---|
| V1 | Every claim has a citation |
| V2 | The quote is found in the raw source cell |
| V3 | The claim can be derived from the quote |
| V5 | No live-availability wording ("available now", "open now") |
| V8 | Unknowns are never shown as verified |
| V9 | Evidence that comes only from photo captions is flagged |

The validator log is shown in the app, including anything it changed or removed.

### The AI is guarded, not trusted

Gemini is optional. It never adds facts. It only (1) converts a free-text query into a structured request, and (2) summarises results that have **already passed the validator**. Its output is checked again:

- Any quote in a summary must appear exactly in the evidence, or the summary is rejected.
- Summaries with live-availability wording are rejected.
- Parsed queries are validated against allowed values (capabilities, states, PIN format).
- After an AI failure (for example a quota error), AI calls pause for 60 seconds. The cited results are unaffected, and the app shows "No AI summary right now."

### Trust score

A heuristic, **not a probability**:

```
trust = 100 × (0.30 evidence + 0.30 dependencies + 0.20 consistency + 0.10 freshness + 0.10 record quality)
```

- A missing required item (for example anaesthesia for surgery) caps trust at 60.
- A contradicted claim caps trust at 40.
- A missing required capability scales trust down.
- Dependency rules are project rules, not clinical standards.

## Run it locally

```bash
git clone https://github.com/chetanprasadofficial/healthcare-intel.git
cd healthcare-intel
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The app works without any API key (rules-based search with citations). To turn on the AI assistant:

```bash
export GEMINI_API_KEY="your-key"
export LLM_MODEL="gemini-3.5-flash-lite"   # optional, this is the default
```

On Streamlit Community Cloud, set `GEMINI_API_KEY` and `LLM_MODEL` in the app's Secrets. Never commit a key. Set `LLM_DEBUG=1` to print the real AI error in the terminal.

## Rebuild the data (optional)

The processed files in `data/` are already included. To regenerate them from the raw dataset:

1. Put the dataset in `data/` and audit it: `python src/audit.py data/<file>.csv`
2. Read `data/samples.txt` (30 random notes) and add synonyms and negations to `config/lexicons.yaml`.
3. Extract claims: `python src/extract.py data/<file>.csv NOTES_COL [NOTES_COL2 ...]` writes `data/claims.csv`.
4. Check the status mix printed at the end. If almost nothing is "supported", loosen `detail_cues` in the lexicon.
5. Verify: `python src/verify.py data/<file>.csv` writes `data/facilities.csv`, `data/facility_caps.csv` and `data/flags.csv`.

Replace `NOTES_COL` with the free-text columns of your dataset.

## Project layout

```
app/
  streamlit_app.py        main search page
  pages/2_Desert_map.py   medical desert map
src/                      extract, verify, search, validator, llm, i18n, deserts, geo, query
data/                     raw dataset + processed CSVs
requirements.txt
```

## Limitations

- Evidence comes only from the supplied records. A missing mention means *unknown*, not *absent*.
- The system cannot know live availability, bed counts or staffing today.
- Distances are measured from the average position of listings in a PIN or city, so they are approximate.
- The trust score is a heuristic and the dependency rules are not clinical standards.
- AI summaries can still be wrong. Check the quotes in the cited records.

### Known limits of the rule-based extractor (`extract.py`)

- The negation window is crude. "Oxygen concentrator not working in emergency ward" can mark emergency as contradicted. Planned fix: apply negation only to the nearest capability term, or scope it by clause.
- Lists such as "ICU, OT, dialysis available" are read as one sentence, so they are split on commas when many capabilities appear.
- Hindi and regional-language source notes are not handled by the extractor. Queries in 9 languages are supported, but the evidence is read from the English records.
- Staffing mode is detected per sentence and is not linked to a specific doctor.

## Team

**Chilli Coders**. *Add member names here.*
