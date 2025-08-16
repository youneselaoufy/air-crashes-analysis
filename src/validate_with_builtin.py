import pandas as pd
import geopandas as gpd

IN_PATH  = "../data/processed/corrected_aircrashes_geo_step1.csv"
OUT_PATH = "../data/processed/corrected_aircrashes_geo_step1_VALID_BUILTIN.csv"

df = pd.read_csv(IN_PATH)
df["Latitude"]  = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
df = df.dropna(subset=["Latitude", "Longitude"]).copy()

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs="EPSG:4326"
)

# Built-in countries (MultiPolygon), has column 'name' and 'iso_a3'
world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))[["name","geometry"]]
world = world.to_crs("EPSG:4326")  # ensure CRS

# use intersects (robust to border precision), with rsuffix to avoid collisions
joined = gpd.sjoin(gdf, world.rename(columns={"name":"Matched_Country"}), how="left",
                   predicate="intersects", rsuffix="_r")

# classify
def classify(row):
    mc = row.get("Matched_Country")
    if pd.isna(mc) or str(mc).strip()=="":
        return "In the Sea"
    original = str(row.get("Country/Region","")).strip().lower()
    matched  = str(mc).strip().lower()
    return "OK" if original in matched else "Wrong Country"

joined["Geo_Issue"] = joined.apply(classify, axis=1)
joined.drop(columns=[c for c in ["index_right","index_left"] if c in joined.columns],
            inplace=True, errors="ignore")

joined.to_csv(OUT_PATH, index=False)
print("Saved:", OUT_PATH)
print(joined["Geo_Issue"].value_counts(dropna=False))
