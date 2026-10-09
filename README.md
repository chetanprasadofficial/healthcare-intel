# Healthcare Intelligence (PS-03) - Chilli Coders

## Start here
1. pip install -r requirements.txt
2. Put the dataset in data/ then run:  python src/audit.py data/<file>.csv
3. Read data/samples.txt (30 random notes). Add synonyms/negations to config/lexicons.yaml
4. python src/extract.py data/<file>.csv <NOTES_COL> [more text cols]   -> data/claims.csv
5. Check the status mix printed at the end. If almost nothing is "supported", loosen detail_cues.

## Known limits of extract.py v1 (fix these first, using real notes)
- Negation window is crude: "oxygen concentrator not working in emergency ward" marks emergency as contradicted.
  Fix: only treat negation as applying to the nearest capability term, or scope it by clause.
- Lists like "ICU, OT, dialysis available" are one sentence; split on commas when many capabilities appear.
- Hindi/regional text is not handled.
- Staffing mode is per sentence, not linked to a specific doctor.

## Next files to write (in this order)
src/verify.py (dependency rules + contradictions) -> src/query.py -> src/search.py -> src/validator.py -> app/streamlit_app.py -> src/deserts.py
