# src/visualization.py
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def plot_crashes_over_time(df):
    """
    Plot the number of air crashes over time (Year, Quarter, and Month).

    Args:
        df (DataFrame): Cleaned DataFrame containing the air crashes data.
    
    Returns:
        None. Displays the plots and saves them as PNG files.
    """
    # Get the current directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the full path for the output directory
    output_dir = os.path.join(current_dir, '../reports/figures/')
    os.makedirs(output_dir, exist_ok=True)

    # Extract Year
    df['Year'] = pd.to_datetime(df['Year'], format='%Y')

    # Safely Extract Quarter
    if 'Quarter' in df.columns and df['Quarter'].notna().any():
        # Convert to string safely, then extract the number, and handle NaNs
        df['Quarter'] = df['Quarter'].astype(str).str.extract('(\d)').astype(float)
    else:
        print("Warning: 'Quarter' column is either missing or empty.")

    # Convert Month names to numerical values
    month_mapping = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4, 
        'May': 5, 'June': 6, 'July': 7, 'August': 8, 
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    df['Month'] = df['Month'].map(month_mapping)

    # 1. Crashes by Year
    crashes_per_year = df['Year'].value_counts().sort_index()
    plt.figure(figsize=(14, 7))
    sns.lineplot(x=crashes_per_year.index, y=crashes_per_year.values, marker='o', color='blue')
    plt.title('Air Crashes Over Time (Year)', fontsize=16)
    plt.xlabel('Year', fontsize=14)
    plt.ylabel('Number of Crashes', fontsize=14)
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'crashes_over_year.png'))
    plt.close()

    # 2. Crashes by Quarter
    if 'Quarter' in df.columns:
        crashes_per_quarter = df['Quarter'].value_counts().sort_index()
        plt.figure(figsize=(10, 6))
        sns.barplot(x=crashes_per_quarter.index, y=crashes_per_quarter.values, 
                    palette='viridis', hue=crashes_per_quarter.index, dodge=False, legend=False)
        plt.title('Air Crashes by Quarter', fontsize=16)
        plt.xlabel('Quarter', fontsize=14)
        plt.ylabel('Number of Crashes', fontsize=14)
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'crashes_by_quarter.png'))
        plt.close()

    # 3. Crashes by Month
    crashes_per_month = df['Month'].value_counts().sort_index()
    plt.figure(figsize=(10, 6))
    sns.barplot(x=crashes_per_month.index, y=crashes_per_month.values, 
                palette='coolwarm', hue=crashes_per_month.index, dodge=False, legend=False)
    plt.title('Air Crashes by Month', fontsize=16)
    plt.xlabel('Month', fontsize=14)
    plt.ylabel('Number of Crashes', fontsize=14)
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'crashes_by_month.png'))
    plt.close()

def plot_crashes_by_location(df):
    """
    Plot the geographical distribution of air crashes by Country/Region.

    Args:
        df (DataFrame): Cleaned DataFrame containing the air crashes data.
    
    Returns:
        None. Displays the plot and saves it as a PNG file.
    """
    # Get the current directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the full path for the output directory
    output_dir = os.path.join(current_dir, '../reports/figures/')
    os.makedirs(output_dir, exist_ok=True)

    # Top 10 countries/regions with most crashes
    top_countries = df['Country/Region'].value_counts().head(10)
    
    # Plot geographical distribution
    plt.figure(figsize=(12, 8))
    sns.barplot(y=top_countries.index, x=top_countries.values, 
                palette='magma', hue=top_countries.index, dodge=False, legend=False)
    plt.title('Top 10 Countries/Regions with Most Air Crashes', fontsize=16)
    plt.xlabel('Number of Crashes', fontsize=14)
    plt.ylabel('Country/Region', fontsize=14)
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'crashes_by_location.png'))
    plt.close()

def plot_common_aircraft_manufacturers(df):
    """
    Plot the most common aircraft manufacturers involved in air crashes.

    Args:
        df (DataFrame): Cleaned DataFrame containing the air crashes data.
    
    Returns:
        None. Displays the plot and saves it as a PNG file.
    """
    # Get the current directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the full path for the output directory
    output_dir = os.path.join(current_dir, '../reports/figures/')
    os.makedirs(output_dir, exist_ok=True)

    # Top 10 aircraft manufacturers
    top_manufacturers = df['Aircraft Manufacturer'].value_counts().head(10)
    
    # Plot most common aircraft manufacturers
    plt.figure(figsize=(12, 8))
    sns.barplot(y=top_manufacturers.index, x=top_manufacturers.values, 
                palette='plasma', hue=top_manufacturers.index, dodge=False, legend=False)
    plt.title('Top 10 Aircraft Manufacturers Involved in Air Crashes', fontsize=16)
    plt.xlabel('Number of Crashes', fontsize=14)
    plt.ylabel('Aircraft Manufacturer', fontsize=14)
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'common_aircraft_manufacturers.png'))
    plt.close()


if __name__ == "__main__":
    df = pd.read_csv('../data/processed/cleaned_aircrashes.csv')
    plot_crashes_over_time(df)
    plot_crashes_by_location(df)
    plot_common_aircraft_manufacturers(df)
