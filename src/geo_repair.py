#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
geo_repair.py – remet au bon endroit les points (lat, lon) hors de leur pays.
Output : cleaned_aircrashes_geo_final.csv
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from geopy.geocoders import Nominatim
from pathlib import Path
import json, time, requests, zipfile, io, sys

# ------------------------------------------------------------------#
# 1. Répertoires et fichiers
# ------------------------------------------------------------------#
BASE_DIR   = Path(__file__).resolve().parent.parent        # …/air-crashes-analysis
DATA_DIR   = BASE_DIR / "data"
PROC_DIR   = DATA_DIR / "processed"

INPUT_CSV  = PROC_DIR / "cleaned_aircrashes_with_geo.csv"        # <-- adapte si besoin
OUTPUT_CSV = PROC_DIR / "cleaned_aircrashes_geo_final.csv"
CACHE_JSON = PROC_DIR / "geo_cache.json"

NE_DIR   = DATA_DIR / "ne_admin0"
NE_SHP   = NE_DIR / "ne_110m_admin_0_countries.shp"
NE_ZIP   = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"

# ------------------------------------------------------------------#
# 2. Téléchargement du shapefile Natural Earth (si absent)
# ------------------------------------------------------------------#
if not NE_SHP.exists():
    print("► Téléchargement du shapefile Natural Earth…")
    NE_DIR.mkdir(parents=True, exist_ok=True)
    r = requests.get(NE_ZIP, timeout=30)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(NE_DIR)
    print("✔ Shapefile extrait dans", NE_DIR)

world = gpd.read_file(NE_SHP)

# ------------------------------------------------------------------#
# 3. Dataset d’origine + cache
# ------------------------------------------------------------------#
if not INPUT_CSV.exists():
    sys.exit(f"❌ CSV introuvable : {INPUT_CSV}")

df = pd.read_csv(INPUT_CSV)

if CACHE_JSON.exists():
    cache = json.load(open(CACHE_JSON, encoding="utf-8"))
else:
    cache = {}

# ------------------------------------------------------------------#
# 4. Outils
# ------------------------------------------------------------------#
geolocator = Nominatim(user_agent="aircrashes-fix", timeout=10)

def country_of(lat: float, lon: float) -> str | None:
    res = world[world.contains(Point(lon, lat))]
    return res.iloc[0]["NAME"] if not res.empty else None

def repair_row(idx: int, row) -> bool:
    """Renvoie True si la ligne a été corrigée."""
    lat, lon = row.Latitude, row.Longitude
    if pd.isna(lat) or pd.isna(lon):
        return False
    if country_of(lat, lon) == row["Country/Region"]:
        return False           # déjà cohérent

    query = f"{row.Location}, {row['Country/Region']}"
    if query in cache:
        new_lat, new_lon = cache[query]
    else:
        loc = geolocator.geocode(query, exactly_one=True)
        if not loc:
            return False
        new_lat, new_lon = loc.latitude, loc.longitude
        cache[query] = (new_lat, new_lon)
        with open(CACHE_JSON, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        time.sleep(1)          # ~1000 req/h

    if country_of(new_lat, new_lon) != row["Country/Region"]:
        return False           # réponse douteuse

    df.at[idx, "Latitude"]  = new_lat
    df.at[idx, "Longitude"] = new_lon
    return True

# ------------------------------------------------------------------#
# 5. Boucle de correction avec progression
# ------------------------------------------------------------------#
corrected = 0
total     = len(df)

print(f"→ Vérification de {total} lignes…")
for i, r in df.iterrows():
    if i % 50 == 0:
        print(f"{i}/{total} traitées – {corrected} corrigées", end="\r")
    if repair_row(i, r):
        corrected += 1
        print(f"✔ Ligne {i} corrigée ({corrected} au total)")

print()  # retour ligne final
print(f"✅ Terminé : {corrected} lignes ajustées sur {total}.")

df.to_csv(OUTPUT_CSV, index=False)
print(f"📄 Fichier écrit : {OUTPUT_CSV}")
