"""Source Audit. Usage: python src/audit.py data/india10k.csv
Prints what the dataset really contains so the plan can be adapted to real fields."""
import sys, re, pandas as pd

def load(path):
    if path.endswith((".xlsx", ".xls")): return pd.read_excel(path)
    if path.endswith(".json"): return pd.read_json(path)
    return pd.read_csv(path, low_memory=False)

def main(path):
    df = load(path)
    print(f"ROWS: {len(df)}  COLS: {len(df.columns)}\n")
    rows = []
    for c in df.columns:
        s = df[c]
        rows.append((c, str(s.dtype), round(s.isna().mean()*100, 1), s.nunique(), round(s.astype(str).str.len().mean(), 1)))
    rep = pd.DataFrame(rows, columns=["column", "dtype", "null_%", "n_unique", "avg_len"])
    print(rep.to_string(index=False))

    text_cols = rep[(rep.dtype.isin(["object","str","string"])) & (rep.avg_len > 80)].column.tolist()
    print("\nLIKELY FREE-TEXT COLUMNS:", text_cols)
    guess = lambda pat: [c for c in df.columns if re.search(pat, c, re.I)]
    print("PIN-like:", guess(r"pin|zip|postal"))
    print("State/District-like:", guess(r"state|district|city"))
    print("Lat/Lon-like:", guess(r"lat|lon|lng"))
    print("Type-like:", guess(r"type|category|level|ownership"))
    print("Year/date-like:", guess(r"year|date|survey|updated"))

    with open("data/samples.txt", "w") as f:
        for i in df.sample(min(30, len(df)), random_state=1).index:
            f.write(f"--- row {i} ---\n")
            for c in text_cols[:3]:
                f.write(f"[{c}] {df.at[i, c]}\n")
    print("\nWrote 30 random notes to data/samples.txt. READ THEM and note the patterns.")

if __name__ == "__main__":
    main(sys.argv[1])
