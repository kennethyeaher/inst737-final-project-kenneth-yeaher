<div align="center">

# Ovara

### Reproductive Health Provider Access Modeling

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.3-150458?style=flat&logo=pandas&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.6-F7931E?style=flat&logo=scikit-learn&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-6.6-3F4F75?style=flat&logo=plotly&logoColor=white)
![Dash](https://img.shields.io/badge/Dash-2.14-008DE4?style=flat&logo=plotly&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat)

**INST737: Data Science Techniques - Final Project** 

[View Dashboard](#running-the-project) · [Pipeline Stages](#pipeline-stages) · [Data Sources](#data-and-sources) · [Future Work](#next-steps-and-future-considerations)
 
---
 
</div>

## Project Overview

Ovara started from a simple observation: fertility and reproductive healthcare access in the United States is not evenly distributed. Somthing I observed while working as Healthcare Data Anlyst for a Managment Conclusting company that ran multiple Minimally Invasive Gynecologic Surgery focus Ambulatory Surgery Centers scattered though the top metro cities on the east coast.   However, most of the data that could prove this sits in fragmented federal registries that are difficult to work with. This project builds a data science pipeline to turn that raw registry data into measurable access intelligence.

The pipeline ingests the CMS National Provider Identifier (NPPES) registry, a dataset of over 8 million healthcare providers, and filters it to reproductive health specialties including OB/GYNs, Reproductive Endocrinologists, Certified Nurse Midwives, and Women's Health Nurse Practitioners. It then merges these providers with Census metropolitan population estimates to construct geographic density features, estimate expected provider supply through regression modeling, and classify states by access risk based on where actual supply deviates from predictions.

> **Core question:** Given a state's population and workforce characteristics, how many reproductive health providers should we expect, and where does reality fall short? 

States with large negative residuals between predicted and actual provider density are flagged as potentially underserved. This converts a descriptive mapping exercise into a predictive access gap detection framework.

---

## Data and Sources 

<details>
<summary><strong>📊 Primary Datasets</strong></summary>
 
<br>

The NPPES registry provides provider identity, taxonomy classification, practice location, and enrollment timeline for every registered healthcare provider in the country. Census CBSA delineation files and metropolitan population estimates supply the demand side denominator for density calculations. Both are publicly available federal sources updated regularly.

| Source | Description | URL |
|---|---|---|
| CMS NPPES | National provider registry (~8M providers) | [download.cms.gov](https://download.cms.gov/nppes/NPI_Files.html) |
| Census CBSA | Metropolitan population estimates | [census.gov](https://www.census.gov/programs-surveys/metro-micro.html) |
| HealthData.gov | Supporting health datasets | [healthdata.gov](https://healthdata.gov) |
| HRSA | Health workforce data | [data.hrsa.gov](https://data.hrsa.gov) |
| KFF | Health policy research | [kff.org](https://www.kff.org) |


</details>
 
<details>
<summary><strong>🔬 Techniques</strong></summary>
 
<br>

| Technique | Library | Purpose |
|---|---|---|
| Linear Regression | scikit-learn | Estimate expected provider density |
| Quartile Classification | pandas | Assign access risk tiers from residuals |
| K-Means Clustering | scikit-learn | Segment states by supply characteristics |
| Silhouette Scoring | scikit-learn | Optimize cluster count |
| Cross Validation | scikit-learn | Evaluate model generalization |
| Interactive Dashboard | Dash + Plotly | Explore access gaps by state |
| EDA Visualization | matplotlib | Specialty distribution and growth trends |

</details>
 
<details>
<summary><strong>🏷️ Reproductive Health Taxonomy Scope</strong></summary>
 
<br>

Rather than analyzing all healthcare providers generically, Ovara filters the NPPES dataset during the transform stage to 13 NUCC taxonomy codes that represent the reproductive and women's health workforce. 

| Category | Specialties | Codes |
|---|---|---|
| **OB/GYN** | General, Gynecology, Obstetrics, Maternal-Fetal Medicine, Reproductive Endocrinology, Female Pelvic Medicine and Reconstructive Surgery, Gynecologic Oncology, Critical Care, REI | `207V*` family |
| **Midwifery** | Certified Nurse Midwife, Midwife | `367A00000X`, `176B00000X` |
| **Nurse Practitioner** | Women's Health NP | `363LW0102X` |

The full code to label mapping is defined in `REPRODUCTIVE_HEALTH_TAXONOMY` in `etl/transform.py`.
 
</details>
 
---
 
## Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/kennethyeaher/inst737-final-project-kenneth-yeaher.git
cd inst737-final-project-kenneth-yeaher

# 2. Create and activate a virtual environment:
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies:
pip install -r requirements.txt
```

> **NOTE:** The NPPES raw data file is not included due to size (~11 GB). Download the latest weekly NPI data file from [CMS NPPES](https://download.cms.gov/nppes/NPI_Files.html), place the extracted CSV in `data/extracted/nppes_weekly_raw/`, then run `python preprocess_nppes.py` to filter to reproductive health providers before running the pipeline.

--

## Running the Project

```bash
# Run the full pipeline end to end
python main.py

# Or launch the interactive dashboard separately
python vis/interactive_visualizations.py
```

Open [http://127.0.0.1:8050](http://127.0.0.1:8050) in your browser. Click any state on the map to filter the bar chart. Hit **Reset** to restore the default view.

--

## Code Package Structure

| Directory / File | Description |
|---|---|
| **`analysis/`** | **Modeling and analytics modules** |
| `access_risk_model.py` | Residual based risk classification |
| `build_access_model_dataset.py` | State level supply + population merge |
| `build_metro_dataset.py` | Census CBSA reference construction |
| `build_model_dataset.py` | ZIP level feature engineering |
| `clustering_model.py` | K-Means metro segmentation |
| `eda_provider.py` | Exploratory visualizations |
| `evaluate.py` | Model evaluation and diagnostics |
| `regression_model.py` | Provider density regression |
| **`etl/`** | **Extract and transform pipeline** |
| `extract.py` | NPPES raw file ingestion |
| `transform.py` | Cleaning, filtering, standardization |
| **`vis/`** | **Visualization and dashboard** |
| `interactive_visualizations.py` | Dash web application |
| **`utils/`** | **Shared configuration and helpers** |
| `config.py` | Pipeline constants and file paths |
| `helpers.py` | Reusable utility functions |
| **`data/`** | **Pipeline data artifacts** |
| `extracted/` | Raw standardized datasets |
| `transformed/` | Cleaned modeling ready datasets |
| `load/` | Feature engineered datasets |
| `model_outputs/` | Regression, risk, and clustering results |
| `reference-tables/` | Data dictionaries and geographic reference files |
| `visualizations/` | Generated charts |
| `main.py` | Full pipeline entry point |
| `preprocess_nppes.py` | One time NPPES preprocessing script |
| `requirements.txt` | Dependencies |


-- 

## Pipeline Stages

```
┌──────────┐   ┌───────────┐   ┌─────┐   ┌──────────┐   ┌───────────┐
│ Extract  │──▶│ Transform │──▶│ EDA │──▶│ Feature  │──▶│   Metro   │
└──────────┘   └───────────┘   └─────┘   │ Engineer │   │ Reference │
                                         └──────────┘   └───────────┘
                                                              │
     ┌────────────┐   ┌──────────┐   ┌──────────┐     ┌───────▼───────┐
     │ Dashboard  │◀──│ Cluster  │◀──│  Access  │◀────│  Regression   │
     └────────────┘   └──────────┘   │   Risk   │     │  + Evaluation │
                                     └──────────┘     └───────────────┘
```

--

<details>
<summary><strong>1. Extract</strong> — <code>data/extracted/nppes_provider_raw.csv</code></summary>
 
<br>
 
Loads the weekly NPPES provider file and selects only the columns needed for geographic and specialty analysis. The full file contains over 8 million rows and 330 columns, the extraction narrows this to 17 core fields covering provider identity, taxonomy, practice location, and enrollment dates.
</details>
 
<details>
<summary><strong>2. Transform</strong> — <code>data/transformed/nppes_provider_clean.csv</code></summary>
 
<br>
 
Filters to active providers, applies the reproductive health taxonomy filter defined in `REPRODUCTIVE_HEALTH_TAXONOMY`, standardizes column names to snake_case, cleans ZIP and state geography, removes duplicate NPIs, and parses date fields. This is the stage where the dataset shifts from general purpose to reproductive health focused.
</details>
 
<details>
<summary><strong>3. Exploratory Data Analysis</strong> — <code>data/visualizations/</code></summary>
 
<br>
 
Generates three visualizations from the filtered dataset: a ranked horizontal bar chart of reproductive health provider counts by state, a specialty breakdown showing how providers distribute across OB/GYN subspecialties versus midwifery and NP roles, and an annual enumeration trend chart that identifies workforce growth patterns while handling partial year data quality issues.
</details>
 
<details>
<summary><strong>4. Geographic Feature Engineering</strong> — <code>data/load/provider_geo_features.csv</code></summary>
 
<br>
 
Aggregates the cleaned provider dataset to the ZIP level, producing four supply indicators: provider count, taxonomy diversity (number of unique specialties), provider maturity (average enumeration year as a proxy for workforce age), and recent provider growth (providers enumerated in the last three years).
</details>
 
<details>
<summary><strong>5. Metro Reference Dataset</strong> — <code>data/load/cbsa_reference_dataset.csv</code></summary>
 
<br>
 
Builds a Census aligned metropolitan reference dataset by merging CBSA delineation files with population estimates. The output maps each county to its metropolitan statistical area and carries the 2024 population estimate used as the demand denominator in density calculations.
</details>
 
<details>
<summary><strong>6. Access Model Dataset</strong> — <code>data/load/access_model_dataset.csv</code></summary>
 
<br>
 
Merges state level supply features with metro population totals and computes provider density as providers per 100,000 residents. This is the modeling ready dataset that feeds both the regression and clustering stages.
</details>
 
<details>
<summary><strong>7. Regression Model</strong> — <code>data/model_outputs/regression_results.csv</code></summary>
 
<br>
 
Fits a linear regression estimating expected reproductive health provider density from four features: metro population, taxonomy diversity, recent provider- rowth, and average provider enumeration year. The residual for each state, the difference between actual and predicted density, is the core analytical signal. States where actual density falls well below the prediction are candidates for access concern.
</details>
 
<details>
<summary><strong>8. Model Evaluation</strong> — <code>data/model_outputs/evaluation_results.json</code></summary>
 
<br>
 
Runs 5 fold cross validation, computes standardized feature coefficients for scale independent importance analysis, performs residual diagnostics (skewness, kurtosis, outlier detection), and benchmarks against a naive baseline. Saves structured results as JSON and per state detail as CSV.
</details>
 
<details>
<summary><strong>9. Access Risk Classification</strong> — <code>data/model_outputs/access_risk_classified.csv</code></summary>
 
<br>
 
Converts regression residuals into actionable risk labels. Each state receives a continuous risk score (0–100, where 100 is most underserved), a categorical tier assignment based on residual quartile position (high risk, moderate risk, adequate, well served), a supply gap magnitude, and a severity ranking. Threshold metadata is saved separately for reproducibility.
</details>
 
<details>
<summary><strong>10. Metro Clustering</strong> — <code>data/model_outputs/clustering_results.csv</code></summary>
 
<br>
 
Segments states into supply profile groups using K-Means clustering. Features are standardized with StandardScaler before clustering, and the optimal cluster count is selected by silhouette scoring across k=2 through k=6. Cluster labels are assigned by average provider density to keep them interpretable.
</details>
 
<details>
<summary><strong>11. Interactive Dashboard</strong> — <code>http://127.0.0.1:8050</code></summary>
 
<br>
 
A Dash web application that visualizes reproductive health provider density by state through a choropleth map, filterable bar charts, predicted vs actual scatter with outlier annotations, KPI cards, and an auto-generated executive summary. Clicking a state on the map filters the detail view.
</details>


--

## Data Management
 
### Data Dictionaries
 
Each analytical dataset has a corresponding data dictionary stored in `data/reference_tables/` following the naming convention `data_dictionary_[dataset_name].csv`.
 
| Dictionary | Dataset | Fields |
|---|---|---|
| `data_dictionary_nppes_provider_clean.csv` | Cleaned provider level dataset | 18 |
| `data_dictionary_provider_geo_features.csv` | ZIP level engineered features | 6 |
| `data_dictionary_cbsa_reference_dataset.csv` | Census metro reference | 8 |
 
### Reference Tables
 
| File | Purpose |
|---|---|
| `cbsa_reference_dataset.csv` | Maps CBSA codes to county FIPS, state names, and 2024 population estimates |
| `REPRODUCTIVE_HEALTH_TAXONOMY` | In code reference table in `etl/transform.py` defining 13 NUCC codes |
 
## Next Steps and Future Considerations

| Enhancement | Description | Impact |
|---|---|---|
| **Demand Side Features** | Add fertility age population (women 25–44) as a demand proxy | Distinguish true access gaps from population composition effects |
| **CDC ART Integration** | Join CDC fertility clinic treatment data (~500 clinics) | Add treatment volume and outcomes as a second access dimension |
| **Network Modeling** | Neo4j graph analysis of provider clinic metro referral networks | Shift from density based to connectivity based access measurement |
| **Geographic Drill Down** | Metro and ZIP level choropleth with risk tier overlays | Enable targeted intervention planning at sub state level |

---
 
---
 
<div align="center">

## Author

**Kenneth Yeaher** 
Master of Information Management, Class of 2027 
University of Maryland, College Park  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Kenneth_Yeaher-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/kennethyeaher/)

Focus Areas:
`Healthcare Analytics` · `Data Science` · `Data Visualization` · `Geographic Modeling`

</div>
