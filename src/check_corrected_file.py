import pandas as pd
df = pd.read_csv("corrected_aircrashes_geo.csv")

expected = ["Country/Region", "Location", "Latitude", "Longitude", "Matched_Country", "Geo_Issue"]
missing = [c for c in expected if c not in df.columns]
print("Missing columns:", missing)

print("\nIssue counts:")
print(df["Geo_Issue"].value_counts(dropna=False).to_string())
