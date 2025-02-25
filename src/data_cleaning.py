# src/data_cleaning.py
import os
import pandas as pd

def load_data(file_name):
    """
    Load the dataset from the raw data folder.
    Args:
        file_name (str): Name of the CSV file.
    Returns:
        DataFrame: Loaded DataFrame.
    """
    # Construct the full file path dynamically
    current_dir = os.path.dirname(__file__)  # Current directory of the script
    file_path = os.path.join(current_dir, '../data/raw/', file_name)
    file_path = os.path.abspath(file_path)   # Get the absolute path
    
    print(f"Looking for file at: {file_path}")  # Debug: See the full path
    
    try:
        df = pd.read_csv(file_path)
        print(f"Data loaded successfully from {file_path}")
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except pd.errors.EmptyDataError:
        print(f"Error: No data in file at {file_path}")
        return None
    except pd.errors.ParserError:
        print(f"Error: Parsing error while reading the file at {file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def clean_data(df):
    """
    Clean the dataset by removing duplicates and handling missing values.
    Args:
        df (DataFrame): Raw DataFrame.
    Returns:
        DataFrame: Cleaned DataFrame.
    """
    # Remove duplicates
    initial_shape = df.shape
    df.drop_duplicates(inplace=True)
    print(f"Duplicates removed. Rows before: {initial_shape[0]}, After: {df.shape[0]}")
    
    # Drop columns with more than 50% missing values
    missing_threshold = 0.5
    cols_to_drop = df.columns[df.isnull().mean() > missing_threshold]
    df.drop(columns=cols_to_drop, inplace=True)
    print(f"Dropped columns with > {missing_threshold*100}% missing values: {list(cols_to_drop)}")
    
    # Fill missing values for numerical columns with median
    num_cols = df.select_dtypes(include=['float64', 'int64']).columns
    df[num_cols] = df[num_cols].fillna(df[num_cols].median())
    print(f"Filled missing numerical values with median: {list(num_cols)}")
    
    # Fill missing values for categorical columns with mode
    cat_cols = df.select_dtypes(include=['object']).columns
    df[cat_cols] = df[cat_cols].fillna(df[cat_cols].mode().iloc[0])
    print(f"Filled missing categorical values with mode: {list(cat_cols)}")
    
    return df

def save_cleaned_data(df, output_file):
    """
    Save the cleaned DataFrame to a CSV file.
    Args:
        df (DataFrame): Cleaned DataFrame.
        output_file (str): Path to the output CSV file.
    """
    # Create the directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
        
    # Save the cleaned CSV file
    df.to_csv(output_file, index=False)
    print(f"Data cleaned and saved successfully at {output_file}")

if __name__ == "__main__":
    # File paths
    file_name = 'aircrashesFullDataUpdated_2024.csv'
    output_file = '../data/processed/cleaned_aircrashes.csv'
    
    # Load, clean, and save data
    df = load_data(file_name)
    if df is not None:
        cleaned_df = clean_data(df)
        save_cleaned_data(cleaned_df, output_file)
