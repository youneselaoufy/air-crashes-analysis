import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

IN_PATH  = "../data/processed/corrected_aircrashes_geo_step1.csv"
WORLD_SHP = "../ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"

df = pd.read_csv(IN_PATH)
df["Latitude"]  = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
df = df.dropna(subset=["Latitude", "Longitude"]).copy()

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs="EPSG:4326"
)

countries = gpd.read_file(WORLD_SHP)

print("Points:", len(gdf), " | CRS points:", gdf.crs)
print("Countries rows:", len(countries), " | CRS countries:", countries.crs)
print("Countries columns:", list(countries.columns)[:10])

# show a couple geometries/types
print("Country geom type sample:", countries.geometry.iloc[0].geom_type)
print("Points bounds:", gdf.total_bounds)
print("Countries bounds:", countries.total_bounds)
