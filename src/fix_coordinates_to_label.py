import pandas as pd, geopandas as gpd

INPUT = "data/processed/corrected_aircrashes_geo_step1.csv"
FINAL = "data/processed/cleaned_aircrashes_geo_FINAL.csv"
SHAPE = "ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"

def main():
    df = pd.read_csv(INPUT, low_memory=False)
    df["Latitude"]  = pd.to_numeric(df["Latitude"],  errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    countries = gpd.read_file(SHAPE)[["ADMIN","geometry"]].rename(columns={"ADMIN":"Country"})
    if countries.crs is None or countries.crs.to_string().upper() != "EPSG:4326":
        countries = countries.set_crs("EPSG:4326", allow_override=True)
    countries["geometry"] = countries["geometry"].buffer(0)
    c = countries.copy()
    c["centroid_lat"] = c.geometry.centroid.y
    c["centroid_lon"] = c.geometry.centroid.x
    centroids = c.set_index(c["Country"].str.strip().str.lower())[["centroid_lat","centroid_lon"]].to_dict("index")

    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
        crs="EPSG:4326"
    )
    joined = gpd.sjoin(gdf, countries[["Country","geometry"]], how="left", predicate="intersects", rsuffix="_r")

    def needs_fix(row):
        declared = str(row.get("Country/Region","")).strip().lower()
        hit      = str(row.get("Country","")).strip().lower()
        return (hit == "" or declared != hit)

    joined["Coord_FixedReason"] = None
    mask = joined.apply(needs_fix, axis=1)

    def fix_row(row):
        declared = str(row.get("Country/Region","")).strip().lower()
        info = centroids.get(declared)
        if info:
            row["Latitude"]  = info["centroid_lat"]
            row["Longitude"] = info["centroid_lon"]
            row["Coord_FixedReason"] = "CentroidOfCountry"
        else:
            row["Coord_FixedReason"] = "NoCountryCentroidFound"
        return row

    joined.loc[mask, :] = joined.loc[mask, :].apply(fix_row, axis=1)

    out = joined.drop(columns=[c for c in joined.columns if c.startswith("index_") or c in ["geometry","Country"]]).copy()
    out["Geo_Issue"] = out["Coord_FixedReason"].apply(lambda x: "Coord_OK" if pd.isna(x) else "Coord_Replaced")
    out.to_csv(FINAL, index=False)
    print(out["Geo_Issue"].value_counts(dropna=False).to_string())
    print("Wrote ->", FINAL)

if __name__ == "__main__":
    main()
