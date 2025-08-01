# src/validate_geo.py
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
from pathlib import Path

CSV   = Path("../data/processed/cleaned_aircrashes_geo_final.csv")
SHP   = Path("../data/ne_admin0/ne_110m_admin_0_countries.shp")

df     = pd.read_csv(CSV)
world  = gpd.read_file(SHP)

def mismatch(row):
    # Ignore les NaN
    if pd.isna(row.Latitude) or pd.isna(row.Longitude):
        return True
    pt   = Point(row.Longitude, row.Latitude)
    poly = world[world.contains(pt)]
    return poly.empty or poly.iloc[0]["NAME"] != row["Country/Region"]

nb_errors = df.apply(mismatch, axis=1).sum()
print(f"Incohérences restantes : {nb_errors} sur {len(df)} lignes")
