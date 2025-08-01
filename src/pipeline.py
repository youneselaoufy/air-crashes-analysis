#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pipeline.py – valide & corrige les coordonnées (lat, lon)

import pandas as pd, geopandas as gpd, pycountry
from shapely.geometry import Point
from rapidfuzz import process, fuzz
from geopy.geocoders import Nominatim
from pathlib import Path
import json, time, requests, zipfile, io, sys

# -------------------------------------------------------------------
# RÉPERTOIRES / FICHIERS (toujours relatifs à la racine du projet)
BASE_DIR = Path(__file__).resolve().parent.parent     # …/air-crashes-analysis
DATA_DIR = BASE_DIR / "data"
PROC_DIR = DATA_DIR / "processed"

RAW_CSV  = PROC_DIR / "cleaned_aircrashes_geo_final.csv"     # ← ton dernier CSV
OUT_CSV  = PROC_DIR / "cleaned_aircrashes_geo_PERFECT.csv"
CACHE    = PROC_DIR / "geo_cache.json"

NE_DIR   = DATA_DIR / "ne_admin0"
NE_SHP   = NE_DIR / "ne_110m_admin_0_countries.shp"
NE_ZIP   = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"

# -------------------------------------------------------------------
# VÉRIFICATIONS INITIALES
if not RAW_CSV.exists():
    sys.exit(f"❌ CSV introuvable : {RAW_CSV}")

# -------------------------------------------------------------------
# TÉLÉCHARGEMENT DU SHAPEFILE NATURAL EARTH (une seule fois)
if not NE_SHP.exists():
    print("► Téléchargement du shapefile Natural Earth…")
    NE_DIR.mkdir(parents=True, exist_ok=True)
    z = requests.get(NE_ZIP, timeout=30); z.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(z.content)) as f:
        f.extractall(NE_DIR)
    print("✔ Shapefile extrait dans", NE_DIR)

world = gpd.read_file(NE_SHP)[["ISO_A3", "ADMIN", "geometry"]]

# -------------------------------------------------------------------
# CHARGEMENT DU DATASET
df = pd.read_csv(RAW_CSV)
print(f"Loaded {len(df):,} rows")

# -------------------------------------------------------------------
# FONCTIONS UTILITAIRES
def loc_to_country(loc: str) -> str | None:
    if pd.isna(loc):
        return None
    parts = [p.strip() for p in loc.split(",")]
    return parts[-1] if parts else None

def country_to_iso(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    try:
        return pycountry.countries.lookup(name).alpha_3
    except LookupError:
        all_names = [c.name for c in pycountry.countries]
        best, score, _ = process.extractOne(name, all_names, scorer=fuzz.token_sort_ratio)
        return pycountry.countries.get(name=best).alpha_3 if score > 80 else None

def point_in_iso(lat, lon):
    poly = world[world.contains(Point(lon, lat))]
    return None if poly.empty else poly.iloc[0]["ISO_A3"]

# -------------------------------------------------------------------
# GÉOCODEUR + CACHE
geocoder = Nominatim(user_agent="aircrashes-perfect", timeout=10)
cache = json.load(open(CACHE)) if CACHE.exists() else {}

def geocode_location(query: str):
    if query in cache:
        return cache[query]
    res = geocoder.geocode(query, exactly_one=True)
    if not res:
        return None
    cache[query] = (res.latitude, res.longitude)
    if len(cache) % 20 == 0:
        json.dump(cache, open(CACHE, "w"), indent=2)
    time.sleep(1)  # 1 req/s pour rester fair-use
    return cache[query]

# -------------------------------------------------------------------
# BOUCLE PRINCIPALE
fixed = 0
for idx, row in df.iterrows():
    lat, lon = row.Latitude, row.Longitude
    iso = country_to_iso(loc_to_country(row.Location))
    if iso is None:
        continue

    if pd.notna(lat) and pd.notna(lon) and point_in_iso(lat, lon) == iso:
        continue  # déjà correct

    hit = geocode_location(row.Location)
    if not hit:
        continue
    new_lat, new_lon = hit
    if point_in_iso(new_lat, new_lon) == iso:
        df.at[idx, "Latitude"]  = new_lat
        df.at[idx, "Longitude"] = new_lon
        fixed += 1
        if fixed % 20 == 0:
            print(f"→ {fixed} points corrected")

print(f"Finished. {fixed} points updated.")
df.to_csv(OUT_CSV, index=False)
print("Wrote", OUT_CSV)
