import pandas as pd
import geopandas as gpd

IN_PATH  = "../data/processed/corrected_aircrashes_geo_step1.csv"
WORLD_SHP = "../ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"
OUT_PATH = "../data/processed/corrected_aircrashes_geo_step1_validated.csv"

# 1) Load & coerce coords
df = pd.read_csv(IN_PATH)
df["Latitude"]  = pd.to_numeric(df.get("Latitude"),  errors="coerce")
df["Longitude"] = pd.to_numeric(df.get("Longitude"), errors="coerce")
df = df.dropna(subset=["Latitude", "Longitude"]).copy()

# Drop any stale join columns
for col in ["index_right","index_left","Matched_Country_right","Matched_Country_left"]:
    if col in df.columns:
        df.drop(columns=[col], inplace=True)

# 2) to GeoDataFrame
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs="EPSG:4326"
)

# 3) load & sanitize countries
countries = gpd.read_file(WORLD_SHP)[["ADMIN","geometry"]].rename(columns={"ADMIN":"Matched_Country"})
if countries.crs is None or countries.crs.to_string().upper() != "EPSG:4326":
    countries = countries.set_crs("EPSG:4326", allow_override=True)
countries["geometry"] = countries["geometry"].buffer(0)  # fix invalid polygons

# 4) spatial join (intersects is more tolerant than within)
joined = gpd.sjoin(gdf, countries, how="left", predicate="intersects", rsuffix="_r")
if "Matched_Country_r" in joined.columns and "Matched_Country" not in joined.columns:
    joined = joined.rename(columns={"Matched_Country_r":"Matched_Country"})

# 5) classify — prefer strict equality (ignoring case), since step1 already auto-replaced many
def classify(row):
    mc = row.get("Matched_Country")
    if pd.isna(mc) or str(mc).strip()=="":
        return "In the Sea"
    original = str(row.get("Country/Region","")).strip().lower()
    matched  = str(mc).strip().lower()
    return "OK" if original == matched else "Wrong Country"

joined["Geo_Issue"] = joined.apply(classify, axis=1)

# 6) clean & save
joined.drop(columns=[c for c in ["index_right","index_left"] if c in joined.columns],
            inplace=True, errors="ignore")
joined.to_csv(OUT_PATH, index=False)

print(f"✅ Analysis complete. Saved to {OUT_PATH}\n")
print("Issue counts:")
print(joined["Geo_Issue"].value_counts(dropna=False).to_string())
