import os
import pandas as pd
import requests
import re

# -------------------- Step 1: Clean and Standardize Locations --------------------

def clean_location_string(location):
    """
    Cleans a location string to improve geolocation search accuracy.
    - Removes unnecessary words, distance markers, and outdated names.
    - Replaces old country names with modern equivalents.
    - Standardizes "Mt." to "Mount".
    """
    # Remove distance markers like "950 nm S of", "50 km N of"
    location = re.sub(r"\d+\s*(nm|km|miles)?\s*[NSEW]\s*of\s*", "", location, flags=re.IGNORECASE)

    # Replace outdated country names
    location_corrections = {
        "Yugoslavia": "Serbia",
        "Bugaria": "Bulgaria",
        "Zaire": "Democratic Republic of Congo",
        "Czechoslovakia": "Czech Republic",
        "Binh Tahi Da": "Da Nang, Vietnam",
        "Geti Democratic": "Democratic Republic of Congo",
        "Leopoldville Zaire": "Kinshasa, Democratic Republic of Congo",
        "Kinshasa Zaire": "Kinshasa, Democratic Republic of Congo",
        "Kasongo Zaire": "Kasongo, Democratic Republic of Congo",
        "Kiev Ukraine": "Kyiv, Ukraine",
        "Moscow USSR": "Moscow, Russia",
        "USSRAeroflot": "Russia",
    }

    for old, new in location_corrections.items():
        location = location.replace(old, new)

    # Standardize "Mt." to "Mount"
    location = re.sub(r"\bMt\.\s*", "Mount ", location)

    # Remove unnecessary words like "Near", "Off", etc.
    location = re.sub(r"\b(Near|Off|Over|Approx\.?|Close to|Off the coast of|En route)\b", "", location, flags=re.IGNORECASE).strip()

    # Remove excessive spaces
    location = re.sub(r"\s+", " ", location).strip()

    return location


# -------------------- Step 2: Find Missing Locations --------------------

def find_missing_geolocations():
    """Identifies locations with missing coordinates and saves them for review."""
    cache_file = "src/geolocation_cachefile.csv"
    cleaned_file = "data/processed/cleaned_aircrashes.csv"

    if not os.path.exists(cache_file) or not os.path.exists(cleaned_file):
        print("Missing required files. Ensure 'geolocation_cachefile.csv' and 'cleaned_aircrashes.csv' exist.")
        return False

    df_cleaned = pd.read_csv(cleaned_file)
    df_geo = pd.read_csv(cache_file)

    # Merge latitude and longitude into the cleaned dataset
    df_final = df_cleaned.merge(df_geo, on="Location", how="left")

    # Save the updated dataset
    df_final.to_csv("data/processed/cleaned_aircrashes_with_geo.csv", index=False)
    print("Merged geolocation data. Saved as 'cleaned_aircrashes_with_geo.csv'.")

    # Find locations still missing coordinates
    missing_coords = df_final[df_final["Latitude"].isna() | df_final["Longitude"].isna()]

    if missing_coords.empty:
        print("All locations have coordinates. No missing data found.")
        return False

    # Clean locations before saving
    missing_coords["Location"] = missing_coords["Location"].apply(clean_location_string)
    missing_coords[["Location"]].drop_duplicates().to_csv("src/missing_locations.csv", index=False)
    print(f"Saved {len(missing_coords)} missing locations to 'src/missing_locations.csv'.")

    return True


# -------------------- Step 3: Fetch Missing Coordinates --------------------

def get_google_maps_coordinates(location):
    """Fetches latitude and longitude using Google Maps API."""
    api_key = "YOUR_GOOGLE_MAPS_API_KEY"
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location}&key={api_key}"
    response = requests.get(url)
    data = response.json()

    if data["status"] == "OK":
        lat = data["results"][0]["geometry"]["location"]["lat"]
        lon = data["results"][0]["geometry"]["location"]["lng"]
        return lat, lon
    else:
        print(f"Could not find coordinates for '{location}'.")
        return None, None

# Fallback coordinates for known locations with API failures
approximate_locations = {
    "Off Barnegat New": (39.761, -74.101),
    "Off Townsville Australia": (-19.258, 146.818),
    "Off Trapani Italy": (38.018, 12.513),
    "Off Gozo Malta": (36.044, 14.251),
    "Off Folkestone England": (51.081, 1.171),
    "Belgrad Yugoslavia": (44.786, 20.448),  # Belgrade, Serbia
    "Kinshasa Zaire": (-4.325, 15.322),  # Kinshasa, Democratic Republic of Congo
}

def fetch_missing_coordinates():
    """Fetches missing coordinates and saves them to a new file."""
    missing_file = "src/missing_locations.csv"

    if not os.path.exists(missing_file):
        print("No missing locations file found. Skipping fetch step.")
        return False

    df_missing = pd.read_csv(missing_file)

    for index, row in df_missing.iterrows():
        loc = clean_location_string(row["Location"])  
        lat, lon = get_google_maps_coordinates(loc)

        if lat is None or lon is None:  # Use fallback if API fails
            lat, lon = approximate_locations.get(loc, (None, None))

        df_missing.at[index, "Latitude"] = lat
        df_missing.at[index, "Longitude"] = lon

    df_missing.to_csv("src/missing_locations_updated.csv", index=False)
    print("Updated missing locations saved to 'src/missing_locations_updated.csv'.")
    return True


# -------------------- Step 4: Merge Updated Data into Cache --------------------

def update_cache():
    """Merges newly found coordinates back into the main cache file."""
    cache_file = "src/geolocation_cachefile.csv"
    updated_file = "src/missing_locations_updated.csv"

    if not os.path.exists(updated_file):
        print("No updated locations to merge. Skipping cache update.")
        return

    df_cache = pd.read_csv(cache_file)
    df_fixed = pd.read_csv(updated_file)

    # Update the cache with the newly found data
    df_cache.update(df_fixed)
    df_cache.to_csv(cache_file, index=False)

    print("Cache file updated with missing locations.")


# -------------------- Step 5: Merge Final Geolocations into Cleaned Dataset --------------------

def merge_geolocations_to_cleaned():
    """Ensures all available geolocation data is merged into the cleaned dataset."""
    cleaned_file = "data/processed/cleaned_aircrashes.csv"
    cache_file = "src/geolocation_cachefile.csv"

    if not os.path.exists(cleaned_file) or not os.path.exists(cache_file):
        print("Missing files for merging geolocations.")
        return

    df_cleaned = pd.read_csv(cleaned_file)
    df_geo = pd.read_csv(cache_file)

    df_final = df_cleaned.merge(df_geo, on="Location", how="left")

    # Save the final dataset
    df_final.to_csv("data/processed/cleaned_aircrashes_with_geo.csv", index=False)
    print("Final dataset with geolocation saved as 'cleaned_aircrashes_with_geo.csv'.")


# -------------------- Run All Steps --------------------

if __name__ == "__main__":
    print("Checking for missing geolocations...")
    missing_found = find_missing_geolocations()

    if missing_found:
        print("Fetching missing coordinates...")
        fetched = fetch_missing_coordinates()

        if fetched:
            print("Updating cache with new data...")
            update_cache()

    print("Merging final geolocation data into cleaned dataset...")
    merge_geolocations_to_cleaned()

    print("Processing complete.")
