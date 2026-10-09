"""Geography helpers: clean state names (using PIN prefixes learned from the data), PIN/city centroids, haversine."""
import re, math, pandas as pd

CANON = ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana","Himachal Pradesh",
 "Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab",
 "Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Delhi","Chandigarh",
 "Puducherry","Jammu And Kashmir","Ladakh","Andaman And Nicobar Islands","Dadra And Nagar Haveli And Daman And Diu","Lakshadweep"]
ALIAS = {"up":"Uttar Pradesh","tamilnadu":"Tamil Nadu","uttaranchal":"Uttarakhand","punjab region":"Punjab","orissa":"Odisha",
         "new delhi":"Delhi","nct of delhi":"Delhi","jammu & kashmir":"Jammu And Kashmir","j&k":"Jammu And Kashmir",
         "pondicherry":"Puducherry","bengal":"West Bengal","mp":"Madhya Pradesh"}
_canon_l = {c.lower(): c for c in CANON}

def canon_state(s):
    if not isinstance(s, str): return None
    t = re.sub(r"\s+", " ", s.strip().lower())
    if t in _canon_l: return _canon_l[t]
    if t in ALIAS: return ALIAS[t]
    for part in [p.strip() for p in t.split(",")][::-1]:            # "Jehanabad, Bihar"
        if part in _canon_l: return _canon_l[part]
        if part in ALIAS: return ALIAS[part]
    return None

def clean_geo(f):
    """Add state_clean (own state text, else majority state of its PIN prefix). Blank out coordinates outside India."""
    f = f.copy()
    for c in ("latitude", "longitude"):
        f[c] = pd.to_numeric(f[c], errors="coerce")
    bad = ~(f.latitude.between(6, 38) & f.longitude.between(68, 98))
    f.loc[bad, ["latitude", "longitude"]] = float("nan")
    f["pin"] = f["address_zipOrPostcode"].astype(str).str.extract(r"(\d{6})")[0]
    f["state_clean"] = f["address_stateOrRegion"].map(canon_state)
    known = f.dropna(subset=["state_clean", "pin"])
    for n in (3, 2):
        maj = known.groupby(known.pin.str[:n]).state_clean.agg(lambda s: s.value_counts().index[0])
        miss = f.state_clean.isna() & f.pin.notna()
        f.loc[miss, "state_clean"] = f.loc[miss, "pin"].str[:n].map(maj)
    return f

def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371 * 2 * math.asin(math.sqrt(a))
