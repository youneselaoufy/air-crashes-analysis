#!/usr/bin/env python
# -*- coding: utf-8 -*-
# fix_coords_hard.py  –  reverse-check every lat/lon, forward-geocode if wrong,
#                        retry politely on 503 / timeouts.

import pandas as pd, geopandas as gpd, pycountry
from shapely.geometry import Point
from geopy.geocoders import Nominatim
from geopy.exc      import GeocoderTimedOut, GeocoderServiceError
from pathlib import Path
import json, time, requests, zipfile, io, sys

# ───────────────────────── Paths
ROOT   = Path(__file__).resolve().parent.parent
DATA   = ROOT / "data"
PROC   = DATA / "processed"

SRC_CSV = PROC / "cleaned_aircrashes_geo_final.csv"
DST_CSV = PROC / "cleaned_aircrashes_geo_FIXED.csv"
CACHE   = PROC / "geo_cache.json"

NE_DIR  = DATA / "ne_admin0"
NE_SHP  = NE_DIR / "ne_110m_admin_0_countries.shp"
NE_ZIP  = "https://naciscdn.org/naturalearth/110m/cultural/" \
          "ne_110m_admin_0_countries.zip"

# ───────────────────────── Download shapefile (once)
if not NE_SHP.exists():
    print("► Downloading Natural Earth…")
    NE_DIR.mkdir(parents=True, exist_ok=True)
    r = requests.get(NE_ZIP, timeout=30); r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(NE_DIR)

world = gpd.read_file(NE_SHP)[["ISO_A3", "geometry"]]

def iso_from_point(lat, lon):
    poly = world[world.contains(Point(lon, lat))]
    return None if poly.empty else poly.iloc[0]["ISO_A3"]

# ───────────────────────── Data
if not SRC_CSV.exists():
    sys.exit(f"❌ Missing file: {SRC_CSV}")
df = pd.read_csv(SRC_CSV)
print(f"Loaded {len(df):,} rows")

# ───────────────────────── Geocoder + cache with retry
geo        = Nominatim(user_agent="aircrash-fix", timeout=10)
BASE_DELAY = 1       # seconds between successful calls
RETRIES    = 4       # attempts on 503 / timeout
BACKOFF    = 30      # wait seconds before retry

cache = json.load(open(CACHE)) if CACHE.exists() else {}

def cached_query(q: str, forward=True):
    key = ("F" if forward else "R") + q
    if key in cache:
        return cache[key]

    for attempt in range(RETRIES):
        try:
            if forward:
                res = geo.geocode(q, exactly_one=True)
            else:
                res = geo.reverse(q, exactly_one=True, language="en")
            if res:
                cache[key] = (res.latitude, res.longitude)
                if len(cache) % 50 == 0:
                    json.dump(cache, open(CACHE, "w"), indent=2)
                time.sleep(BASE_DELAY)
                return cache[key]
            return None                        # not found
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            if attempt == RETRIES - 1:
                print(f"× giving up on {q[:60]} – {e}")
                return None
            print(f"· 503/timeout → retry in {BACKOFF}s ({attempt+1}/{RETRIES})")
            time.sleep(BACKOFF)
    return None

# ───────────────────────── Main loop
fixed = 0
for i, row in df.iterrows():
    lat, lon = row.Latitude, row.Longitude
    if pd.isna(lat) or pd.isna(lon):
        continue

    rev_iso = iso_from_point(lat, lon)
    exp_country = (
        row.Location.split(",")[-1].strip()
        if isinstance(row.Location, str) and "," in row.Location
        else str(row.get("Country/Region", "")).strip()
    )
    try:
        exp_iso = pycountry.countries.lookup(exp_country).alpha_3
    except LookupError:
        exp_iso = rev_iso  # fallback: treat as OK

    if rev_iso == exp_iso:
        continue  # already correct

    hit = cached_query(row.Location, forward=True)
    if not hit:
        continue
    new_lat, new_lon = hit
    if iso_from_point(new_lat, new_lon) == exp_iso:
        df.at[i, "Latitude"]  = new_lat
        df.at[i, "Longitude"] = new_lon
        fixed += 1
        if fixed % 20 == 0:
            print(f"→ {fixed} points fixed")

print(f"✅ Done. {fixed} points moved.")
df.to_csv(DST_CSV, index=False)
print("Wrote", DST_CSV)
