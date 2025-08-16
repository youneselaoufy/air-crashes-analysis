import os, pandas as pd, geopandas as gpd

print("== Import OK ==")
csv = "data/processed/cleaned_aircrashes_with_geo.csv"

assert os.path.exists(csv), f"Missing {csv}"
df = pd.read_csv(csv, low_memory=False)
for c in ["Latitude","Longitude"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
print("Non-numeric coords after coercion:", df[["Latitude","Longitude"]].isna().any(axis=1).sum())

countries = "ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"
assert os.path.exists(countries), f"Missing {countries}"
g = gpd.read_file(countries)[["ADMIN","geometry"]]
print("Countries:", len(g), "CRS:", g.crs)
print("Smoke check passed.")
