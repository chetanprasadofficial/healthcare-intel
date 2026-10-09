"""Desert map engine: per PIN-prefix area and capability -> Covered / Data desert / Likely medical desert.
Covered         = a facility with SUPPORTED evidence for the capability lies within `radius` km of the area centre.
Data desert     = no such facility, but >= min_listings listings of any kind exist within `radius` km (care may exist, records are silent).
Medical desert  = no such facility and fewer than min_listings listings nearby (sparse listings; 'likely', not proven).
Usage: python src/deserts.py dialysis"""
import sys
import numpy as np, pandas as pd
from geo import clean_geo

CAPS = ["dialysis", "trauma", "oncology", "icu", "emergency", "surgery"]
LABELS = {"covered": "Covered", "data_desert": "Data desert", "medical_desert": "Likely medical desert"}
COLORS = {"covered": "#2e9e5b", "data_desert": "#f5a623", "medical_desert": "#d64545"}

def _hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))

def _mode(s):
    s = s.dropna()
    return s.mode().iat[0] if len(s) else ""

def load():
    fac = clean_geo(pd.read_csv("data/facilities.csv", low_memory=False))
    fac = fac.dropna(subset=["latitude", "longitude", "pin"]).reset_index(drop=True)
    # drop rows whose PIN prefix is rare for their own state (typos like 996544 in Hyderabad)
    fac["p3"] = fac.pin.str[:3]
    share = fac.groupby(["state_clean", "p3"]).size() / fac.groupby("state_clean").size()
    keyed = pd.MultiIndex.from_frame(fac[["state_clean", "p3"]])
    cnt = fac.groupby(["state_clean", "p3"]).size().reindex(keyed).values
    fac = fac[(cnt >= 3) | fac.state_clean.isna()].reset_index(drop=True)
    return fac, pd.read_csv("data/facility_caps.csv")

def compute(cap, prefix=3, radius=25.0, min_listings=5):
    fac, caps = load()
    c = caps[caps.capability == cap]
    fac["has_ev"] = fac.row_id.isin(set(c[c.status == "supported"].row_id))
    fac["has_mention"] = fac.row_id.isin(set(c[c.status == "mentioned_only"].row_id))
    fac["area"] = fac.pin.str[:prefix]
    areas = fac.groupby("area").agg(lat=("latitude", "mean"), lon=("longitude", "mean"), listings=("row_id", "size"),
                                    with_evidence=("has_ev", "sum"), mentions=("has_mention", "sum"),
                                    state=("state_clean", _mode), city=("address_city", _mode)).reset_index()
    flat, flon, ev = fac.latitude.values, fac.longitude.values, fac.has_ev.values
    near_l, near_e, nearest = [], [], []
    for i in range(0, len(areas), 200):                       # chunked so memory stays small
        a = areas.iloc[i:i + 200]
        D = _hav(a.lat.values[:, None], a.lon.values[:, None], flat[None, :], flon[None, :])
        near_l.append((D <= radius).sum(1))
        if ev.any():
            De = D[:, ev]
            near_e.append((De <= radius).sum(1)); nearest.append(De.min(1))
        else:
            near_e.append(np.zeros(len(a), dtype=int)); nearest.append(np.full(len(a), np.nan))
    areas["listings_nearby"] = np.concatenate(near_l)
    areas["evidence_nearby"] = np.concatenate(near_e)
    areas["nearest_evidence_km"] = np.round(np.concatenate(nearest), 1)
    areas["kind"] = np.where(areas.evidence_nearby > 0, "covered",
                             np.where(areas.listings_nearby >= min_listings, "data_desert", "medical_desert"))
    areas["label"] = areas.kind.map(LABELS)
    areas["color"] = areas.kind.map(COLORS)
    return areas

if __name__ == "__main__":
    cap = sys.argv[1] if len(sys.argv) > 1 else "dialysis"
    a = compute(cap)
    print(f"{cap}: {len(a)} areas (3-digit PIN prefix, 25 km)")
    print(a.label.value_counts().to_string())
    print("\nLargest data deserts (most listings, no evidence):")
    print(a[a.kind == "data_desert"].sort_values("listings_nearby", ascending=False).head(5)[["area", "state", "city", "listings_nearby", "nearest_evidence_km"]].to_string(index=False))
