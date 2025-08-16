import pandas as pd
import geopandas as gpd

IN_PATH  = "../data/processed/corrected_aircrashes_geo_step1.csv"
WORLD_SHP = "../ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"

df = pd.read_csv(IN_PATH)
df["Latitude"]  = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
df = df.dropna(subset=["Latitude", "Longitude"]).copy()

gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]), crs="EPSG:4326")
countries = gpd.read_file(WORLD_SHP)[["ADMIN","geometry"]].rename(columns={"ADMIN":"ADMIN_RAW"}).to_crs("EPSG:4326")
countries["geometry"] = countries["geometry"].buffer(0)  # fix minor invalid geoms

# Try the first 10 points
sample = gdf.head(10).copy()
for i, row in sample.iterrows():
    pt = row.geometry
    hit = countries[countries.contains(pt)]
    print(f"Row {i} -> matches: {len(hit)}", (hit["ADMIN_RAW"].iloc[0] if len(hit) else None))


