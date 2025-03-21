#  Air Crashes Analysis (1908-2023)

##  Overview

This project analyzes global air crashes from **1908-2023** using **Python**. The dataset is cleaned and visualized to uncover trends, most affected airlines, and geographical patterns.

##  Dataset

- **Source**: [Kaggle Air Crashes Full Data (1908-2023)](https://www.kaggle.com/datasets/jogwums/air-crashes-full-data-1908-2023)
- **Total Records**: 5,000+ air crashes

## 🛠️ Project Structure

```
 data/
   ├── raw/ (original dataset)
   ├── processed/ (cleaned dataset)
 src/
   ├── data_cleaning.py (cleans dataset)
   ├── visualization.py (generates plots)
 notebooks/
   ├── project.ipynb (detailed EDA & insights)
 reports/
   ├── figures/ (saved charts & maps)
```
##  Data Cleaning Steps

- Removed **duplicates & missing values**
- Converted **dates & locations** to correct formats
- **Fetched and added precise Latitude & Longitude** for mapping using **OpenStreetMap API (Nominatim)** to enrich the dataset
- Saved cleaned dataset: `data/processed/cleaned_aircrashes.csv`

##  Visualizations & Insights

| Chart                        | Insight                                                         |
| ---------------------------- | --------------------------------------------------------------- |
|  Crashes Over Time         | Air crashes peaked between 1960-1990 and declined after 2000    |
|  Geographical Distribution | USA & Russia had the most crashes                               |
|  Top Aircraft Models       | Boeing & Airbus have the highest crash records                  |
|  Correlation Heatmap       | Fatalities strongly correlate with number of passengers onboard |
|  Severity & Impact         | Major crashes are often linked to larger aircraft               |

> ** Screenshots of visualizations should be added here**

##  How to Run the Project

### **1. Clone this repository:**

```bash
git clone https://github.com/youneselaoufy/air-crashes-analysis.git
```

### **2. Install dependencies:**

```bash
pip install -r requirements.txt
```

### **3. Run the cleaning script:**

```bash
python src/data_cleaning.py
```

### **4. Run visualizations:**

```bash
python src/visualization.py
```

##  Next Steps

✔ **Build an Interactive Map using Folium** \
✔ **Develop a Power BI Dashboard** \
✔ **Perform Advanced Statistical Analysis** 

---

💪 Feel free to contribute or suggest improvements!

