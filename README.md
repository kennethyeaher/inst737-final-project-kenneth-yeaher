# INST737 Final Project  
# Ovara: Reproductive Health Provider Access Modeling

## Project Overview

Ovara started from a simple observation: fertility and reproductive healthcare access in the United States is not evenly distributed, somthing I observed while working as Healthcare Data Anlyst for a Managment Conclusting company that ran multiple Minimally Invasive Gynecologic Surgery focus Ambulatory Surgery Centers scattered though the top metro cities on the east coast.   However, most of the data that could prove this sits in fragmented federal registries that are difficult to work with. This project builds a data science pipeline to turn that raw registry data into measurable access intelligence.

The pipeline ingests the CMS National Provider Identifier (NPPES) registry, a dataset of over 8 million healthcare providers, and filters it to reproductive health specialties including OB/GYNs, Reproductive Endocrinologists, Certified Nurse Midwives, and Women's Health Nurse Practitioners. It then merges these providers with Census metropolitan population estimates to construct geographic density features, estimate expected provider supply through regression modeling, and classify states by access risk based on where actual supply deviates from predictions.

The core analytical question is straightforward: given a state's population and workforce characteristics, how many reproductive health providers should we expect, and where does reality fall short? States with large negative residuals between predicted and actual provider density are flagged as potentially underserved. This converts a descriptive mapping exercise into a predictive access gap detection framework.

---

## Data and Sources 
### Primary Datasets

The NPPES registry provides provider identity, taxonomy classification, practice location, and enrollment timeline for every registered healthcare provider in the country. Census CBSA delineation files and metropolitan population estimates supply the demand side denominator for density calculations. Both are publicly available federal sources updated regularly.

- CMS NPPES: https://download.cms.gov/nppes/NPI_Files.html

#### Geographic Reference Data
- Census ZIP County Crosswalk  
- Census CBSA Delineation Files  
- Census Metropolitan Population Estimates  

- Census Metro/Micro: https://www.census.gov/programs-surveys/metro-micro.html

#### Supporting Research Sources
- https://healthdata.gov  
- https://data.hrsa.gov  
- https://www.kff.org  

#### Techniques

The pipeline applies supervised regression (scikit-learn LinearRegression) to estimate expected provider density, quartile based residual classification to assign access risk tiers, K-Means clustering with silhouette scoring to segment states by supply characteristics, and standardized EDA visualization (matplotlib) to communicate specialty distribution, geographic concentration, and enrollment trends.

#### Reproductive Health Taxonomy Scope

Rather than analyzing all healthcare providers generically, Ovara filters the NPPES dataset during the transform stage to 13 NUCC taxonomy codes that represent the reproductive and women's health workforce. This decision was deliberate, it keeps the analysis focused on the provider types that directly serve fertility and reproductive care.
- Obstetrics & Gynecology (207V*) General OB/GYN, Gynecology, Obstetrics, Maternal-Fetal Medicine, Reproductive Endocrinology, Female Pelvic Medicine, Gynecologic Oncology, Critical Care Medicine, REI
- Midwifery
- Certified Nurse Midwife (367A00000X), Midwife (176B00000X)
- Nurse Practitioner
- Women's Health NP (363LW0102X)

--

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/kennethyeaher/inst737-final-project-kenneth-yeaher.git
cd inst737-final-project-kenneth-yeaher
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

> NOTE: The NPPES raw data file is not included in the repository due to size. Download the latest weekly NPI data file from https://download.cms.gov/nppes/NPI_Files.html and place the extracted CSV in data/extracted/nppes_weekly_raw/.

--

## Running the Project

1. Run the full pipeline end to end:
```bash
python main.py
```
This executes all stages in order: extract, transform, EDA, feature engineering, metro reference construction, access model assembly, regression, access risk classification, clustering, and interactive visualization.

2. To launch the interactive dashboard separately:
```bash
python vis/interactive_visualizations.py
```
Open http://127.0.0.1:8050 in your browser. Click any state on the map to filter the bar chart. Hit Reset to restore the default view.

--

## Code Package Structure

| Directory / File | Description |
|---|---|
| **analysis/** | **modeling and analytics modules** |
| `access_risk_model.py` | residual based risk classification |
| `build_access_model_dataset.py` | state level supply + population merge |
| `build_metro_dataset.py` | Census CBSA reference construction |
| `build_model_dataset.py` | ZIP level feature engineering |
| `clustering_model.py` | K-Means metro segmentation |
| `eda_provider.py` | exploratory visualizations |
| `regression_model.py` | provider density regression |
| **etl/** | **extract and transform pipeline** |
| `extract.py` | NPPES raw file ingestion |
| `transform.py` | cleaning, filtering, standardization |
| **vis/** | **visualization and dashboard scripts** |
| `interactive_visualizations.py` | Dash web application |
| `static_visualizations.py` | matplotlib chart generation |
| **utils/** | **shared configuration and helpers** |
| `config.py` | pipeline constants and file paths |
| `helpers.py` | reusable utility functions |
| **data/** | **pipeline data artifacts** |
| `extracted/` | raw standardized datasets |
| `transformed/` | cleaned modeling ready datasets |
| `load/` | feature engineered datasets |
| `model_outputs/` | regression, risk, and clustering results |
| `reference-tables/` | data dictionaries and geographic reference files |
| `visualizations/` | generated charts |
| `main.py` | full pipeline entry point |
| `requirements.txt` | dependencies |

-- 

## Pipeline Stages

1. Extract
Loads the weekly NPPES provider file and selects only the columns needed for geographic and specialty analysis. The full file contains over 8 million rows and 300+ columns, the extraction narrows this to 17 core fields covering provider identity, taxonomy, practice location, and enrollment dates.
> Output: data/extracted/nppes_provider_raw.csv

2. Transform
Filters to active providers, applies the reproductive health taxonomy filter defined in REPRODUCTIVE_HEALTH_TAXONOMY, standardizes column names to snake_case, cleans ZIP and state geography, removes duplicate NPIs, and parses date fields. This is the stage where the dataset shifts from general purpose to reproductive health focused.
> Output: data/transformed/nppes_provider_clean.csv

3. Exploratory Data Analysis
Generates three visualizations from the filtered dataset: a ranked horizontal bar chart of reproductive health provider counts by state, a specialty breakdown showing how providers distribute across OB/GYN subspecialties versus midwifery and NP roles, and an annual enumeration trend chart that identifies workforce growth patterns while handling partial year data quality issues.
> Output: data/visualizations/

4. Geographic Feature Engineering
Aggregates the cleaned provider dataset to the ZIP level, producing four supply indicators: provider count, taxonomy diversity (number of unique specialties), provider maturity (average enumeration year as a proxy for workforce age), and recent provider growth (providers enumerated in the last three years).
> Output: data/load/provider_geo_features.csv

5. Metro Reference Dataset
Builds a Census aligned metropolitan reference dataset by merging CBSA delineation files with population estimates. The output maps each county to its metropolitan statistical area and carries the 2024 population estimate used as the demand denominator in density calculations.
> Output: data/load/cbsa_reference_dataset.csv

6. Access Model Dataset
Merges state level supply features with metro population totals and computes provider density as providers per 100,000 residents. This is the modeling ready dataset that feeds both the regression and clustering stages.
> Output: data/load/access_model_dataset.csv

7. Regression Model
Fits a linear regression estimating expected reproductive health provider density from four features: metro population, taxonomy diversity, recent provider growth, and average provider enumeration year. The residual for each state, the difference between actual and predicted density, is the core analytical signal. States where actual density falls well below the prediction are candidates for access concern.
> Output: data/model_outputs/regression_results.csv

8. Access Risk Classification
Converts regression residuals into actionable risk labels. Each state receives a continuous risk score (0–100, where 100 is most underserved), a categorical tier assignment based on residual quartile position (high risk, moderate risk, adequate, well served), a supply gap magnitude, and a severity ranking. Threshold metadata is saved separately for reproducibility.
> Outputs: data/model_outputs/access_risk_classified.csv, access_risk_summary.csv, access_risk_metadata.json

9. Metro Clustering
Segments states into supply profile groups using K-Means clustering. Features are standardized with StandardScaler before clustering, and the optimal cluster count is selected by silhouette scoring across k=2 through k=6. Cluster labels are assigned by average provider density to keep them interpretable.
> Output: data/model_outputs/clustering_results.csv

10. Interactive Dashboard
A Dash web application that visualizes reproductive health provider density by state through a choropleth map and filterable bar charts. Clicking a state on the map filters the detail view.

--

## Next Steps and Future Considerations

### Demand Side Feature Engineering
The current regression model primarily captures **supply side provider availability and population size**.  
Future iterations can improve explanatory power by incorporating **demand proxy variables**, such as estimated fertility age population such as women aged 25–44.

Including these demographic features would allow the model to:
- [] Better distinguish **true provider access gaps** from differences driven by population composition
- [] Improve model calibration across metro areas with varying reproductive age population structures
- [] Strengthen policy relevance for workforce planning and resource allocation

### CDC ART Data Integration
The **CDC National Assisted Reproductive Technology (ART) Surveillance System** publishes clinic level treatment activity and outcome data for approximately 500 fertility clinics nationwide. Integrating ART data with NPPES provider records at the geographic level would introduce:
- [] Treatment volume as a proxy for **care utilization intensity**
- [] Outcome based metrics as a proxy for **effective access**
- [] A second dimension of access measurement beyond simple provider density

This integration would enable a more comprehensive framework combining:
> Provider supply + population demand + treatment performance.

### Network Based Access Modeling
Future research may extend the analysis using **graph based modeling approaches**. By constructing provider clinic metro referral networks, using Neo4j Graph Data Science, access can be evaluated through:
- [] Connectivity and referral centrality
- [] Network fragmentation and regional isolation
- [] Cluster detection of underserved geographic communities

This approach shifts the access paradigm from **density based measurement to connectivity based measurement**, which may better reflect real world care pathways.


### Geographic Visualization Enhancements
The current visualization layer provides state level exploratory and model based insights.  
Future dashboard iterations will introduce **multi scale geographic visualization**, including:

- [] Metro level choropleth maps
- [] Access risk tier overlays
- [] Drill down navigation from national to state to metro to ZIP level views
- [] Interactive decision support panels for workforce planning

These enhancements will improve interpretability for stakeholders and support more targeted intervention strategies.

---

## Author

Kenneth Yeaher  
Master of Information Management 2027 
University of Maryland, College Park  
[Linkedin](https://www.linkedin.com/in/kennethyeaher/)

Focus Areas:
Healthcare Analytics, Data Science, Data Visualization, Geographic Modeling

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Plotly](https://img.shields.io/badge/Visualization-Plotly-orange)
![Status](https://img.shields.io/badge/Status-In%20Progress-yellow)