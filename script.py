import pandas as pd

df = pd.read_csv("data/processed/cleaned_aircrashes_with_geo.csv")

# Check for missing coordinates
missing_coords = df[df["Latitude"].isna() | df["Longitude"].isna()]

if missing_coords.empty:
    print("✅ All locations have coordinates. Data is ready.")
else:
    print(f"⚠️ {len(missing_coords)} locations are still missing coordinates.")
    print(missing_coords[["Location"]])
