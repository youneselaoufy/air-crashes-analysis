import os
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
import shutil
import atexit
import re
import sys

""" /////////// in comment after finishing the cleaning process and switching to the notebook /////////////
you can skip this 2 fonction coming it s just for solving a problem I had with fetching the data from the API,
I had to use the geopy library to get the latitude and longitude of the locations in the dataset , 
so while fetching row by row i had a problem with the API rate limits so i had to use a cache file to save the data,
also a problem with the interruption of the fetching process so I had to use a lock file to prevent multiple instances from running

"""
"""
lock_file = "data_cleaning.lock"

def check_running_instance():
    
    #Checks if another instance of the script is already running.
    #If a lock file exists, it prevents multiple instances from running.
    
    if os.path.exists(lock_file):
        print("Another instance of the script is already running. Exiting...")
        exit(1)

    # Create a lock file to indicate this instance is running
    with open(lock_file, "w") as f:
        f.write("running")




def remove_lock_file():
    
    #Removes the lock file when the script finishes or is interrupted.
    
    if os.path.exists(lock_file):
        os.remove(lock_file)

# Check if another instance is running
check_running_instance()

# Ensure lock file is removed when script ends
atexit.register(remove_lock_file)

"""

def load_data(file_name):
    """
    Loads the air crash dataset from the raw data folder.

    Args:
        file_name (str): Name of the CSV file.

    Returns:
        DataFrame: Loaded dataset or None if there's an issue.
    """
    current_dir = os.path.dirname(__file__)  
    file_path = os.path.abspath(os.path.join(current_dir, '../data/raw/', file_name))

    print(f"Looking for dataset at: {file_path}")

#error handling
    try:
        df = pd.read_csv(file_path)
        print(f"Data loaded successfully ({len(df)} rows).")
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except pd.errors.EmptyDataError:
        print("Error: The file is empty.")
    except pd.errors.ParserError:
        print("Error: Problem parsing the CSV file. Check formatting.")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return None




def clean_data(df):
    """
    Cleans the raw air crashes dataset by:
    - Removing duplicates
    - Handling missing values
    - Keeping Latitude/Longitude for mapping
    - Converting relevant columns to correct types

    Args:
        df (DataFrame): The raw dataset.

    Returns:
        DataFrame: The cleaned dataset.
    """
    print("Cleaning dataset...")

    if df.duplicated().sum() > 0:
        df.drop_duplicates(inplace=True)
        print("Removed duplicate rows.")

    missing_threshold = 0.5
    cols_to_drop = df.columns[df.isnull().mean() > missing_threshold]
    if not cols_to_drop.empty:
        df.drop(columns=cols_to_drop, inplace=True)
        print(f"Dropped columns with too many missing values: {list(cols_to_drop)}")

    geo_cols = ['Latitude', 'Longitude']
    if set(geo_cols).issubset(df.columns):
        df[geo_cols] = df[geo_cols].apply(pd.to_numeric, errors='coerce')
        df.dropna(subset=geo_cols, how='all', inplace=True)
    else:
        print("Warning: Latitude and Longitude columns are missing.")

    for col in df.select_dtypes(include=['float64', 'int64']):
        df[col] = df[col].fillna(df[col].median())

    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].fillna(df[col].mode().iloc[0])


    date_cols = ['Year', 'Month', 'Day']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    print(f"Cleaning complete. {df.shape[0]} rows, {df.shape[1]} columns remaining.")
    return df




def clean_location_string(location):
    """
    Cleans a location string to create a broader search query.
    Removes unnecessary words, distance markers, and outdated names.
    """
    # Remove distance markers like "950 nm S of", "50 km N of"
    location = re.sub(r"\d+\s*(nm|km|miles)?\s*[NSEW]\s*of\s*", "", location, flags=re.IGNORECASE)

    # Replace outdated country names with modern equivalents
    location_corrections = {
        "Yugoslavia": "Serbia",
        "Bugaria": "Bulgaria",
        "Zaire": "Democratic Republic of Congo",
        "Czechoslovakia": "Czech Republic",
        "Binh Tahi Da": "Da Nang, Vietnam",
        "Geti Democratic": "Democratic Republic of Congo",
        "Nasaso": "Nassau, Bahamas",
        "Rochefort  France": "Rochefort, France",
        "Verona  - Villafranca Italy": "Verona, Italy",
        "Mt. Giner Italy": "Monte Giner, Italy",
        "Mt. Argentari Italy": "Monte Argentario, Italy",
        "Wusong Jiangsu": "Wusong, China",
        "U. S. Air Force": "",  # Remove military references
        "Soviet": "Russia",  # Convert USSR references to modern names
        "USSRAeroflot": "Russia",  
        "Kiev Ukraine": "Kyiv, Ukraine",
        "Moscow USSR": "Moscow, Russia",
    }

    for old, new in location_corrections.items():
        location = location.replace(old, new)

    # If location starts with "Near" or "Off", provide an alternative city instead of just removing
    near_replacements = {
        "Off Barnegat New": "Barnegat, New Jersey, USA",
        "Off Townsville Australia": "Townsville, Queensland, Australia",
        "Off Trapani Italy": "Trapani, Sicily, Italy",
        "Off Gozo Malta": "Gozo, Malta",
        "Off Folkestone England": "Folkestone, England, UK",
    }

    for old, new in near_replacements.items():
        if old in location:
            location = new

    # Standardize "Mt." to "Mount"
    location = re.sub(r"\bMt\.\s*", "Mount ", location)

    # Remove excessive spaces
    location = re.sub(r"\s+", " ", location).strip()

    return location



def save_cleaned_data(df, output_file):
    """
    Saves the cleaned DataFrame to a CSV file.

    Args:
        df (DataFrame): Cleaned dataset.
        output_file (str): Path to save the CSV file.
    """
    output_dir = os.path.dirname(output_file)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"Data saved successfully: {output_file}")



cache_file = os.path.join(os.path.dirname(__file__), "geolocation_cachefile.csv")




def load_geolocation_cache():
    """
    Loads the geolocation cache from a CSV file.
    Ensures the cache is valid and contains the necessary columns.
    """
    if not os.path.exists(cache_file):
        print("No existing geolocation cache found. Starting fresh.")
        return {}

    try:
        df_cache = pd.read_csv(cache_file)

        required_cols = {"Location", "Latitude", "Longitude"}
        if not required_cols.issubset(df_cache.columns):
            raise ValueError("Cache file is missing required columns. Resetting cache.")

        df_cache.set_index("Location", inplace=True)
        cache_dict = df_cache.to_dict(orient="index")

        print(f"Loaded {len(cache_dict)} cached locations.")
        return cache_dict

    except Exception as e:
        print(f"Error loading cache: {e}. Creating a fresh cache.")
        return {}

geolocation_cache = load_geolocation_cache()




def get_lat_lon(location, max_retries=5):
    """
    Fetches latitude and longitude for a given location using Nominatim API.
    If no precise match is found, it tries a broader search.

    Args:
        location (str): The location name.
        max_retries (int): Maximum retries in case of failure.

    Returns:
        tuple: (latitude, longitude) or (None, None) if unsuccessful.
    """
    if not location or pd.isna(location):
        return None, None

    # Check if already cached
    if location in geolocation_cache and geolocation_cache[location]["Latitude"] is not None:
        return geolocation_cache[location]['Latitude'], geolocation_cache[location]['Longitude']

    geolocator = Nominatim(user_agent="air_crash_locator")

    # Try full location first
    for attempt in range(max_retries):
        try:
            loc = geolocator.geocode(location, timeout=10)
            if loc:
                geolocation_cache[location] = {"Latitude": loc.latitude, "Longitude": loc.longitude}
                save_geolocation_cache()
                return loc.latitude, loc.longitude

        except GeocoderTimedOut:
            print(f"Timeout while fetching '{location}', retrying ({attempt + 1}/{max_retries})...")
            time.sleep(2 ** attempt)

    # If full location fails, try broader location (remove details)
    broader_location = clean_location_string(location)
    if broader_location and broader_location != location:
        print(f"Retrying with a broader location: {broader_location}")
        for attempt in range(max_retries):
            try:
                loc = geolocator.geocode(broader_location, timeout=10)
                if loc:
                    geolocation_cache[location] = {"Latitude": loc.latitude, "Longitude": loc.longitude}
                    save_geolocation_cache()
                    return loc.latitude, loc.longitude
            except GeocoderTimedOut:
                time.sleep(2 ** attempt)

    print(f" Warning: No coordinates found for '{location}', even after fallback.")
    return None, None




def save_geolocation_cache():
    """
    Saves the geolocation cache to a CSV file safely.
    Uses a temporary file to prevent corruption.
    """
    if not geolocation_cache:
        print("No new geolocation data to save.")
        return  

    df_cache = pd.DataFrame.from_dict(geolocation_cache, orient="index").reset_index()
    df_cache.rename(columns={"index": "Location"}, inplace=True)

    temp_file = cache_file + ".tmp"

    try:
        print(f"Saving {len(geolocation_cache)} locations to cache...")
        df_cache.to_csv(temp_file, index=False, encoding="utf-8")

        # Ensure the temp file replaces the original
        shutil.move(temp_file, cache_file)
        print("Cache successfully updated.")

    except Exception as e:
        print(f"Error saving cache: {e}")



def add_geolocation(df):
    """
    Adds latitude and longitude columns to the dataset based on crash locations.
    Ensures that the cache file is updated as new locations are processed.

    Args:
        df (DataFrame): Data containing a 'Location' column.

    Returns:
        DataFrame: Updated DataFrame with 'Latitude' and 'Longitude' columns.
    """
    if "Location" not in df.columns:
        print("Error: 'Location' column is missing from the dataset.")
        return df

    print("Fetching latitude and longitude for crash locations...")

    latitudes, longitudes = [], []

    for idx, loc in enumerate(df["Location"]):
        if pd.notnull(loc) and loc.strip() != "":
            #  Clean the location string before searching
            cleaned_location = clean_location_string(loc)

            #  Use cached value if available
            if cleaned_location in geolocation_cache and geolocation_cache[cleaned_location]["Latitude"] is not None:
                lat, lon = geolocation_cache[cleaned_location]["Latitude"], geolocation_cache[cleaned_location]["Longitude"]
            else:
                lat, lon = get_lat_lon(cleaned_location)

                #  Only save valid coordinates
                if lat is not None and lon is not None:
                    geolocation_cache[cleaned_location] = {"Latitude": lat, "Longitude": lon}
                    save_geolocation_cache()

            latitudes.append(lat)
            longitudes.append(lon)

            if idx % 50 == 0:
                save_geolocation_cache()
                print(f"Saved progress at {idx} locations.")

            time.sleep(1)  # Avoid API rate limits
        else:
            latitudes.append(None)
            longitudes.append(None)

    df["Latitude"] = latitudes
    df["Longitude"] = longitudes

    save_geolocation_cache()
    print("All locations processed and saved.")

    return df


def clean_aircrash_data():
    """
    Executes the full pipeline: Load → Clean → Geolocation → Save
    """
    file_name = 'aircrashesFullDataUpdated_2024.csv'
    output_file = '../data/processed/cleaned_aircrashes.csv'

    df = load_data(file_name)
    if df is not None:
        cleaned_df = clean_data(df)              
        cleaned_df = add_geolocation(cleaned_df)
        save_cleaned_data(cleaned_df, output_file)



if __name__ == "__main__":
    file_name = 'aircrashesFullDataUpdated_2024.csv'
    output_file = '../data/processed/cleaned_aircrashes.csv'
    
    df = load_data(file_name)
    if df is not None:
        cleaned_df = clean_data(df)
        cleaned_df = add_geolocation(cleaned_df)
        save_cleaned_data(cleaned_df, output_file)
