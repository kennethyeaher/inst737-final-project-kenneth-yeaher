# INST737 Final Project — Healthcare Provider Access Modeling

## Project Overview

This project builds an end to end data science pipeline to analyze healthcare provider distribution and identify potentially underserved geographic markets across the United States.

Using national provider registry data (NPPES) and Census metropolitan population estimates, the workflow constructs geographic provider density features that can support:

- Access risk modeling
- Market opportunity analysis
- Healthcare infrastructure planning
- Metro-level clustering and segmentation

The pipeline follows a modular data engineering + analytics architecture similar to real industry data science workflows.

---

## Data Sources

### Primary Dataset
- NPPES National Provider Identifier Registry  
  https://download.cms.gov/nppes/NPI_Files.html  

### Geographic Reference Data
- Census ZIP-County Crosswalk  
- Census CBSA Delineation Files  
- Census Metropolitan Population Estimates  

https://www.census.gov/programs-surveys/metro-micro.html  

### Supporting Research Sources
- https://healthdata.gov  
- https://data.hrsa.gov  
- https://www.kff.org  

---

## Project Structure
- analysis/ → modeling dataset construction + analytics modules
- etl/ → extract + transform pipeline scripts
- vis/ → EDA visualizations
- data/
	•	extracted/ → raw standardized datasets
	•	transformed/ → cleaned modeling-ready datasets
	•	load/ → feature engineered datasets
	•	visualizations/ → generated charts

- main.py → full pipeline entry point
- requirements.txt → dependencies

## Pipeline Stages

### 1. Extract Stage

- Loads weekly NPPES provider file
- Filters relevant provider identity + taxonomy + geography fields
- Saves standardized raw dataset

Output: data/extracted/nppes_provider_raw.csv

### 2. Transform Stage

- Filters inactive providers
- Standardizes column names
- Cleans ZIP + state geography
- Parses provider enumeration timeline fields
- Removes duplicate NPIs

Output: data/transformed/nppes_provider_clean.csv

### 3. Exploratory Data Analysis (EDA)

Generates visual insights including:

- Provider counts by state
- Provider taxonomy distribution
- Provider enumeration growth trends

Outputs saved in: data/visualizations/

### 4. Geographic Feature Engineering

Aggregates provider supply indicators at ZIP level:

- Provider counts
- Taxonomy diversity
- Provider maturity indicators
- Recent provider growth signals

Output: data/load/provider_geo_features.csv

### 5. Metro Reference Dataset Construction

Builds Census-aligned metropolitan reference dataset:

- County → CBSA mapping
- Metro population estimates
- Supports later provider density modeling

Output: data/load/cbsa_reference_dataset.csv

## Running the Pipeline

Activate virtual environment: "source .venv/bin/activate"
Run full workflow: "python main.py"

## Modeling Direction (Next Steps)

Planned modeling components extend beyond traditional tabular analytics and incorporate spatial, temporal, and network-based approaches to better understand healthcare access dynamics.

### Provider Density & Access Risk Modeling
- Construction of metro-level provider supply indicators
- Population-normalized density scoring (providers per 100k residents)
- Identification of statistically underserved metropolitan markets
- Classification models to predict access risk zones

### Market Segmentation & Clustering
- Unsupervised clustering of metropolitan areas based on:
  - provider supply
  - taxonomy diversity
  - provider growth trends
  - population scale
- Detection of similar healthcare infrastructure patterns across regions

### Network & Graph Modeling (Neo4j Integration)

Future extensions of this project will incorporate graph data modeling using Neo4j to represent relationships between:

- Providers
- ZIP codes
- Counties
- Metropolitan statistical areas (CBSAs)

Graph-based analysis will support:

- Provider accessibility path analysis
- Network centrality scoring for healthcare hubs
- Detection of structurally underserved geographic clusters
- Community detection algorithms to identify healthcare service ecosystems
- Graph embeddings for advanced access risk modeling

This network perspective enables modeling healthcare access not just as geographic density, but as a connected infrastructure system.

### Decision Intelligence Outputs
- Ranked metro opportunity scoring
- Provider expansion targeting signals
- Visualization-driven market intelligence dashboards

## Visualization, HCI & Decision Support Design

Beyond technical modeling, this project emphasizes human-centered analytics design to ensure outputs are interpretable and actionable for real stakeholders such as healthcare planners, policy analysts, and provider network strategists.

Visualization improvements focus on:

### Geographic Decision Interfaces
- Metro-level provider density mapping
- Underserved market highlighting through color-encoded risk scoring
- Spatial clustering overlays for market segmentation analysis

### Multi-Level Analytical Views
- National → Metro → ZIP drill-down capability
- Aggregated dashboards that allow users to transition from macro trends to localized insights
- Comparative metro benchmarking visuals (e.g., provider supply vs population demand)

### Cognitive Load Reduction
- Consistent chart labeling and standardized feature naming
- Use of ranking visuals (Top N markets) to prioritize attention
- Density metrics normalized per 100k population to improve interpretability

### Temporal Storytelling
- Provider growth trend visualizations to identify infrastructure expansion patterns
- Recent enumeration signals used to detect emerging markets vs stagnant regions

### Future HCI Enhancements
Planned enhancements include:

- Interactive dashboards (Plotly / Power BI / Tableau)
- Map-based exploration interfaces
- User persona–driven analytic views (policy analyst vs healthcare operator)
- Risk alert visualization components for underserved metro detection

These design considerations align the project with modern analytics UX principles where insight delivery, not just model performance, determines real world impact.






## Author

Kenneth Yeaher  
Master of Information Management  
University of Maryland, College Park  

Focus Areas:
Healthcare Analytics | Data Science | Market Intelligence | Geographic Modeling
