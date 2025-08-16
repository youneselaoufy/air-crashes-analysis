import pandas as pd

path = "corrected_aircrashes_geo.csv"
df = pd.read_csv(path)

# Only rows flagged as "Wrong Country"
mask_wrong = df["Geo_Issue"].eq("Wrong Country") & df["Matched_Country"].notna()

# Replace original label with shapefile match
df.loc[mask_wrong, "Country/Region"] = df.loc[mask_wrong, "Matched_Country"]

# Mark what we fixed (optional)
df.loc[mask_wrong, "Geo_Issue"] = "OK-Autofix_CountryLabel"

df.to_csv("../data/processed/corrected_aircrashes_geo_step1.csv", index=False)
print(f"Replaced {mask_wrong.sum()} rows. Saved -> corrected_aircrashes_geo_step1.csv")

# quick summary
print(df["Geo_Issue"].value_counts().to_string())
