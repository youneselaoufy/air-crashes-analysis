
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def plot_crashes_over_year(df):
    df['Year'] = pd.to_datetime(df['Date']).dt.year
    yearly_counts = df['Year'].value_counts().sort_index()
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x=yearly_counts.index, y=yearly_counts.values)
    plt.title("Number of Air Crashes per Year")
    plt.xlabel("Year")
    plt.ylabel("Crashes")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_crashes_by_country(df, top_n=15):
    country_counts = df['Country/Region'].value_counts().head(top_n)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=country_counts.values, y=country_counts.index)
    plt.title(f"Top {top_n} Countries with Most Air Crashes")
    plt.xlabel("Number of Crashes")
    plt.ylabel("Country/Region")
    plt.tight_layout()
    plt.show()

def plot_fatalities_distribution(df):
    plt.figure(figsize=(10, 5))
    sns.histplot(df['Fatalities'], bins=50, kde=True)
    plt.title("Distribution of Fatalities in Air Crashes")
    plt.xlabel("Fatalities")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.show()

def plot_crashes_by_aircraft_model(df, top_n=10):
    model_counts = df['Aircraft_Model'].value_counts().head(top_n)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=model_counts.values, y=model_counts.index)
    plt.title(f"Top {top_n} Aircraft Models Involved in Crashes")
    plt.xlabel("Number of Crashes")
    plt.ylabel("Aircraft Model")
    plt.tight_layout()
    plt.show()


def plot_fatalities_over_year(df):
    df['Year'] = pd.to_datetime(df['Date']).dt.year
    fatalities_by_year = df.groupby('Year')['Fatalities'].sum()
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x=fatalities_by_year.index, y=fatalities_by_year.values)
    plt.title("Total Fatalities per Year in Air Crashes")
    plt.xlabel("Year")
    plt.ylabel("Fatalities")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_top_operators(df, top_n=10):
    operator_counts = df['Operator'].value_counts().head(top_n)
    plt.figure(figsize=(12, 6))
    sns.barplot(x=operator_counts.values, y=operator_counts.index)
    plt.title(f"Top {top_n} Airlines with Most Crashes")
    plt.xlabel("Crashes")
    plt.ylabel("Airline")
    plt.tight_layout()
    plt.show()

def plot_correlation_heatmap(df):
    numeric_cols = df.select_dtypes(include='number')
    plt.figure(figsize=(10, 8))
    sns.heatmap(numeric_cols.corr(), annot=True, cmap='coolwarm', linewidths=0.5)
    plt.title("Correlation Between Numeric Variables")
    plt.tight_layout()
    plt.show()

def plot_crashes_by_month(df):
    df['Month'] = pd.to_datetime(df['Date'], errors='coerce').dt.month
    monthly_counts = df['Month'].value_counts().sort_index()

    plt.figure(figsize=(10, 5))
    sns.barplot(x=monthly_counts.index, y=monthly_counts.values)
    plt.title("Air Crashes by Month")
    plt.xlabel("Month")
    plt.ylabel("Crashes")
    plt.tight_layout()
    plt.show()


def plot_crashes_by_quarter(df):
    df['Quarter'] = pd.to_datetime(df['Date'], errors='coerce').dt.quarter
    quarterly_counts = df['Quarter'].value_counts().sort_index()

    plt.figure(figsize=(8, 5))
    sns.barplot(x=quarterly_counts.index, y=quarterly_counts.values)
    plt.title("Air Crashes by Quarter")
    plt.xlabel("Quarter")
    plt.ylabel("Crashes")
    plt.tight_layout()
    plt.show()

def plot_common_aircraft_manufacturers(df, top_n=10):
    manufacturer_counts = df['Aircraft_Manufacturer'].value_counts().head(top_n)

    plt.figure(figsize=(12, 6))
    sns.barplot(x=manufacturer_counts.values, y=manufacturer_counts.index)
    plt.title(f"Top {top_n} Aircraft Manufacturers Involved in Crashes")
    plt.xlabel("Crashes")
    plt.ylabel("Manufacturer")
    plt.tight_layout()
    plt.show()
