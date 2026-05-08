# Ovara Methodology Notes

**INST737: Data Science Techniques Final Project**  
University of Maryland, College of Information

## At a Glance

| Section | Purpose |
|---|---|
| Research Question | Explains what Ovara is trying to measure |
| Data Sources | Describes where the project data comes from |
| Methodology Flow | Shows the pipeline from raw data to risk classification |
| Regression Model | Explains how expected provider density is estimated |
| Access Risk Classification | Shows how states are grouped by access risk |
| HRSA External Validation | Checks Ovara against federal shortage designations |
| K Means Clustering | Groups states into provider supply patterns |
| Limitations | Explains what the model cannot claim |
| Summary of Key Findings | Gives the main results and how to interpret them |

## Table of Contents

- [How to Read This File](#how-to-read-this-file)
- [What This Document Is](#what-this-document-is)
- [Methodology Flow](#methodology-flow)
- [The Research Question](#the-research-question)
- [Data Sources](#data-sources)
  - [CMS NPPES Registry](#cms-nppes-registry)
  - [Census CBSA and Population Estimates](#census-cbsa-and-population-estimates)
  - [Census ACS Demand Features](#census-acs-demand-features)
  - [HRSA HPSA Data](#hrsa-hpsa-data)
- [Regression Model](#regression-model)
  - [Features](#features)
  - [Results](#results)
  - [Why the Model Underperforms Out of Sample](#why-the-model-underperforms-out-of-sample)
  - [Why the Residuals Are Still Useful](#why-the-residuals-are-still-useful)
- [Access Risk Classification](#access-risk-classification)
- [HRSA External Validation](#hrsa-external-validation)
- [K Means Clustering](#k-means-clustering)
- [Limitations](#limitations)
- [Summary of Key Findings](#summary-of-key-findings)
- [Related Files](#related-files)

## How to Read This File

If you want a quick overview, start with the Research Question, Methodology Flow, and Summary of Key Findings. If you want to understand the modeling decisions, read the Regression Model and Access Risk Classification sections. If you want to evaluate whether the model is credible, focus on HRSA External Validation and Limitations. If you want to understand the full project context, read the whole file alongside the code.

## What This Document Is

This document explains the analytical choices I made while building Ovara, including the parts that did not work as cleanly as I expected. It is meant to be read alongside the code, not as a replacement for it. My goal is to be honest about what the model can and cannot tell us, while also explaining why I still think the output is useful despite its statistical limits.

> **Key takeaway:**  
> Ovara should not be treated as a perfect prediction model. It is better understood as a relative access signal that shows which states appear more underserved compared to similar states in the dataset.

## The Research Question

The starting point for this project came from something I saw directly while working as a Healthcare Data Analyst for a management consulting company that operated Minimally Invasive Gynecologic Surgery focused Ambulatory Surgery Centers across major East Coast metro areas. The centers we worked with were consistently full, consistently referring patients out for specialty care, and consistently serving patients who traveled long distances to access care. That pattern raised a bigger question:

> **Is this just an operational issue for a few centers, or does it reflect something structural about how reproductive health providers are distributed across the country?**

The federal NPPES registry has registration data for every licensed healthcare provider in the United States. The data exists, but it sits in a raw file with 8 million rows and 330 columns, which makes it hard to turn into a clear geographic access picture. Ovara is my attempt to bridge that gap by taking raw workforce registry data and turning it into a signal about where supply may fall short of demand.

The core question is:

> **Given a state's population, workforce history, and specialty composition, how many reproductive health providers should we expect? And where does reality fall short of that expectation?**

## Data Sources

### CMS NPPES Registry

The National Plan and Provider Enumeration System is the main federal database of licensed healthcare providers. Ovara downloads the weekly NPI file and filters it to 13 NUCC taxonomy codes representing the reproductive and women's health workforce:

| Provider Group | Taxonomy Codes |
|---|---|
| OB/GYNs and subspecialties | `207V*` family |
| Certified Nurse Midwives | `367A00000X`, `176B00000X` |
| Women's Health Nurse Practitioners | `363LW0102X` |

The filtered dataset only includes active providers with a valid practice state and primary taxonomy code. Duplicate NPIs are removed. Date fields are parsed to compute provider tenure and identify recent growth based on providers registered within the last three years.

> **Important limitation:**  
> NPPES registration reflects who is licensed, not always who is currently practicing or accessible to patients.

Providers who have retired, moved, or stopped accepting patients may still appear in the registry. On the other side, providers working in states with heavier administrative processes may have registration delays. The model treats NPPES counts as a proxy for workforce supply. It is the best federal signal available for this scope, but it is still imperfect.

### Census CBSA and Population Estimates

Census Core Based Statistical Area delineation files map counties to metropolitan statistical areas. The 2024 population estimates from those CBSA files serve as the demand side denominator for all density calculations. Using metro population instead of total state population is intentional. Reproductive health providers are more likely to locate in metro areas, so using total state population would make rural heavy states look more underserved than they may be by this specific measure.

### Census ACS Demand Features

The Census American Community Survey B01001 table provides state level counts of women aged 25 to 44, which I use as the primary fertility age cohort. These counts are pulled through the Census API and cached locally. The point is to capture demand side variation that raw population does not. A state with a higher share of fertility age women should theoretically support more reproductive health providers, even if total population is the same.

### HRSA HPSA Data

The HRSA Health Professional Shortage Area Primary Care designations are fetched from the HRSA data warehouse and cached locally at:

```text
data/reference_tables/hrsa_hpsa_raw.csv
```

These designations represent areas where the federal government has already determined that primary care provider supply is insufficient relative to population. I use them as an external validation benchmark to check whether Ovara's statistical risk classification is picking up a similar shortage signal.

## Regression Model

### Features

The regression model estimates expected reproductive health provider density, measured as providers per 100,000 metro residents, from five features:

| Feature | Description | Why It Matters |
|---|---|---|
| `metro_population` | Aggregated CBSA metro population | Captures the size of the population being served |
| `taxonomy_diversity` | Mean number of unique taxonomy codes per ZIP area | Measures breadth of reproductive health specialty coverage |
| `recent_provider_growth` | Providers enumerated in the last three years | Captures recent workforce expansion |
| `avg_provider_enum_year` | Mean provider enrollment year | Acts as a workforce maturity proxy |
| `female_25_44_pop` | Women aged 25 to 44 from Census ACS | Acts as a demand proxy |

I chose these features to capture three main dimensions:

| Dimension | Features Used |
|---|---|
| Population scale | `metro_population`, `female_25_44_pop` |
| Specialty mix | `taxonomy_diversity` |
| Workforce maturity and growth | `recent_provider_growth`, `avg_provider_enum_year` |

### Results

| Metric | Value | Interpretation |
|---|---:|---|
| Training R² | 0.151 | The model explains about 15% of the variance in provider density |
| 5 fold cross validated R² | −0.226 | The model does not generalize well to held out states |
| Cross validation standard deviation | 0.34 | Fold results are unstable because the sample size is small |

A negative cross validated R² means that on held out data, the model performs worse than simply predicting the mean density for every state.

> **Key takeaway:**  
> The regression model is not strong enough to be used as a forecasting tool. Its value comes from the residuals, not from its ability to predict unseen states.

### Why the Model Underperforms Out of Sample

Several structural issues limit the regression's predictive power at this scale.

#### 1. The sample is too small for 5 fold cross validation

With 51 states including D.C., each fold uses roughly 40 training observations and 10 test observations. Five features in a linear regression with only 40 training samples is close to the edge of what is statistically stable. One unusual state in a test fold can move the fold R² from positive to strongly negative. The high standard deviation across folds, 0.34, shows that instability.

#### 2. Vermont and Wyoming are high leverage outliers

Vermont has a residual of +28.8, meaning 28 more providers per 100k than predicted. Wyoming has a residual of +67.1. Wyoming's outlier status is partly a data artifact because its CBSA metro population is only about 182,000, making the denominator very small. That makes the per 100k number extremely sensitive to even modest provider counts. When either state lands in a test fold, the fold's prediction error is dominated by that one observation.

#### 3. Feature collinearity inflates coefficient variance

`metro_population` and `female_25_44_pop` are both proxies for state size and are highly correlated. The standardized coefficients reflect this:

| Feature | Standardized Coefficient |
|---|---:|
| `metro_population` | −3.95 |
| `female_25_44_pop` | +2.51 |
| `recent_provider_growth` | −4.24 |

The large opposing coefficients on `metro_population` and `female_25_44_pop` are a sign of collinearity. The model is partly regressing the two population proxies against each other instead of learning a clean population to provider relationship.

#### 4. Structurally important features are missing

The strongest predictors of reproductive health provider presence are not in the NPPES data.

| Missing Feature | Why It Matters |
|---|---|
| Insurance coverage rates and Medicaid expansion status | Providers locate where they can maintain a financially viable practice |
| Abortion policy environment | Policy changes after Dobbs may affect OB/GYN workforce movement |
| Telehealth penetration | Physical provider density may miss virtual access |
| Rural healthcare infrastructure | Rural access depends on transportation, broadband, and clinic capacity |
| Medical school and residency program density | States with large academic medical centers may train and retain more providers |

Without these features, the model is trying to explain a structural access issue using mostly supply side workforce characteristics.

### Why the Residuals Are Still Useful

The negative cross validated R² does not mean the analysis has no value. The residuals are still meaningful because they answer a different question. The regression is not being used to forecast provider counts for unknown states. It is being used to create a relative comparison across states that already exist in the data.

The question is not:

> How many providers will Iowa have?

The question is:

> Given what Iowa looks like on the available supply and demand features, does it have more or fewer providers than expected?

That comparison still has value, even if the model would perform poorly on a truly held out state. The residuals capture deviation from the observed cross state pattern instead of absolute prediction accuracy.

> **Interpretation:**  
> This is a structure of shortage analysis, not a forecasting model. That distinction matters for how the outputs should be used.

## Access Risk Classification

Risk tiers are assigned by binning states into residual quartiles.

| Tier | Definition |
|---|---|
| `high_risk` | Bottom 25% of residuals, meaning most underserved relative to prediction |
| `moderate_risk` | Second residual quartile |
| `adequate` | Third residual quartile |
| `well_served` | Top residual quartile |

Each state also receives a continuous risk score from 0 to 100 based on residual percentile rank, where 100 is the most underserved state. This approach is intentionally relative, not absolute. There is no fixed threshold that defines what "enough" providers looks like. The classification tells us which states are most underserved *compared to other states with similar characteristics*, not whether any state has reached a universal adequacy benchmark.

> **Key takeaway:**  
> The risk tiers should be read as relative access signals, not clinical adequacy labels.

The 13 states classified as `high_risk` are:

| High Risk States |
|---|
| Arkansas |
| Delaware |
| District of Columbia |
| Indiana |
| Iowa |
| Kansas |
| Kentucky |
| Louisiana |
| Mississippi |
| New Hampshire |
| Oklahoma |
| Rhode Island |
| West Virginia |

## HRSA External Validation

To check whether the risk classification is picking up a real signal or just reflecting the model's limits, I benchmarked the `high_risk` tier against HRSA Primary Care HPSA designations. HRSA designations are useful here because they represent the federal government's own geographic shortage assessment.

### Validation Results

| Validation Metric | Value | Interpretation |
|---|---:|---|
| High risk states with active HRSA HPSA designations | 13 of 13 | Every high risk state has a federal shortage designation |
| Precision | 1.00 | No false positives in the high risk tier |
| Recall | 25.5% | Expected because Ovara only flags the bottom 25% of states |
| Spearman correlation with HRSA avg HPSA score | 0.21 | Directionally positive, but not statistically significant |
| p value | 0.15 | Not significant at this sample size |

All 13 states in Ovara's `high_risk` tier have active HRSA Primary Care HPSA designations, giving the model **precision = 1.0**. The recall is 25.5%, which is expected. HRSA designates shortage areas in almost every state, while Ovara only flags the bottom residual quartile, or 25% of states by design. Because of that setup, precision is the more useful metric here.

### HRSA Severity Gradient

The HRSA average HPSA score, based on a 0 to 25 severity scale, shows a positive tier gradient:

| Ovara Tier | HRSA Average HPSA Score |
|---|---:|
| `well_served` | 13.5 |
| `moderate_risk` | 14.4 |
| `high_risk` | 15.6 |

This is directionally consistent. Higher Ovara risk tiers are associated with higher HRSA assessed shortage severity. However, the correlation does not reach statistical significance with only 51 state level observations.

### Important Validation Caveat

Raw HRSA shortage population, meaning total residents in designated shortage areas, shows almost no correlation with Ovara's risk score at r = −0.03. This happens because raw shortage population is heavily influenced by state size. California and Texas can have large absolute shortage populations even when they are relatively well served on a per capita basis. Rate normalized metrics like the HRSA score work better as a validation benchmark, which matches Ovara's own use of rate based features over raw counts.

> **Validation takeaway:**  
> Ovara's `high_risk` states are real shortage states by independent federal assessment. The model is not just creating false positives.

## K Means Clustering

K Means clustering segments states into supply archetypes using four rate based features:

| Feature | Purpose |
|---|---|
| Provider density per 100k | Measures provider supply relative to population |
| Taxonomy diversity | Measures specialty breadth |
| Population normalized recent growth | Measures workforce expansion relative to population |
| Average enumeration year | Acts as a workforce maturity proxy |

Features are standardized with `StandardScaler` before clustering. The optimal cluster count was selected by a silhouette score sweep across k = 2 through k = 6:

| k | Silhouette Score |
|---|---:|
| 2 | **0.556** |
| 3 | 0.285 |
| 4 | 0.292 |
| 5 | 0.303 |
| 6 | 0.287 |

k = 2 was selected with a silhouette score of 0.556. The sharp drop from k = 2 to k = 3, from 0.556 to 0.285, is meaningful. It shows that the data separates most clearly into two supply archetypes:

| Cluster Pattern | Interpretation |
|---|---|
| Low supply states | States with weaker reproductive health provider supply signals |
| High supply states | States with stronger reproductive health provider supply signals |

The data does not naturally break into more detailed groups with the current feature set. Forcing k greater than or equal to 3 creates clusters that are less coherent internally.

> **Clustering takeaway:**  
> After normalization, the supply feature space shows a fairly simple low versus high split. A more detailed clustering model would require additional structural features.

## Limitations

### What the Model Cannot See

The NPPES registry reflects who is licensed, not who is accessible. A provider registered in Mississippi may be practicing mainly in Tennessee, retired, or on leave. The registry does not capture:

| Missing Access Factor | Why It Matters |
|---|---|
| Accepting new patients | Licensed providers may not have open appointment capacity |
| Medicaid acceptance | Provider supply does not equal access for low income patients |
| Access for uninsured patients | Insurance status can block practical access |
| Telemedicine reach | One provider in a metro area may serve rural patients |
| Clinic level capacity | One high volume provider is not the same as one low volume provider |

### Geographic Aggregation

All analysis is at the state level. State level aggregation hides major variation within states. Rural West Virginia and Charleston, WV have very different access realities even though both contribute to the same state residual. The state level model is useful as a first cut for national scope analysis and policy targeting, but it should not be used to make access claims about specific communities.

### The 51 State Limit

Every statistical technique in this pipeline operates on 51 observations. That is a major constraint.

| Method | Constraint |
|---|---|
| Linear regression | Five features at n = 51 is underpowered for strong out of sample prediction |
| Cross validation | Each fold is too small to be stable |
| Silhouette score | Cluster quality is sensitive to individual state composition |
| Residual ranking | Outlier states can strongly affect interpretation |

These limitations are not really fixable within the current scope because they come from working at the state level with national data. The value comes from the patterns themselves, not from strong statistical confidence.

### Policy Environment

This analysis does not directly model the post Dobbs policy environment. Several states with restrictive abortion laws have reported signs of OB/GYN workforce pressure since 2022. The NPPES data reflects a current registration snapshot that may not fully capture provider relocation, reduced practice activity, or retirement driven by policy changes. States like Texas and Florida, classified as `adequate` or `well_served` in this analysis, may still be experiencing access deterioration that trailing NPPES data does not yet reflect.

### Ethical Considerations

This analysis flags states as underserved relative to a statistical model, not relative to a clinical standard of adequacy. The residuals do not tell us whether any state's provider supply is truly enough to meet patient need. They tell us which states are most underserved relative to the cross state pattern. A state ranked `well_served` by this model may still have communities with serious access gaps, especially rural communities and communities of color.

> **Ethical framing:**  
> The goal of this analysis is to show where federal workforce data points to structural supply gaps, so that people working in policy, advocacy, and resource allocation have a clearer picture to start from. It is a starting point, not a verdict.

## Summary of Key Findings

| Finding | Value | What It Means |
|---|---:|---|
| Training R² | 0.151 | The model captures some signal, but not enough for strong prediction |
| 5 fold CV R² | −0.226 | The model should not be used to forecast unseen states |
| CV MAE vs Baseline MAE | 8.86 vs 8.92 | Model performance is close to baseline |
| High risk states identified | 13 | Bottom quartile of residual based access risk |
| HRSA validation precision | 1.00 | Every high risk state also has federal shortage designations |
| HRSA avg HPSA score for well served states | 13.5 | Lower average federal shortage severity |
| HRSA avg HPSA score for high risk states | 15.6 | Higher average federal shortage severity |
| Optimal clustering k | 2 | States split most clearly into low supply and high supply groups |
| Outlier states | Vermont, Wyoming | These states strongly affect model stability |

The negative CV R² is the most important number in this table. It means the model is not reliable as a prediction engine for unseen states. It also means the residuals should be interpreted as relative shortage signals within the observed dataset, not as forecasts. The 100% HRSA precision is the most validating number because it confirms that the states the model flags as most underserved are also states the federal shortage designation process has independently identified.

## Related Files

| File | Purpose |
|---|---|
| [`README.md`](README.md) | Main project overview and setup instructions |
| [`main.py`](main.py) | Runs the full project pipeline |
| [`analysis/regression_model.py`](analysis/regression_model.py) | Builds the provider density regression model |
| [`analysis/access_risk_model.py`](analysis/access_risk_model.py) | Creates residual based access risk tiers |
| [`analysis/clustering_model.py`](analysis/clustering_model.py) | Runs K Means clustering |
| [`analysis/evaluate.py`](analysis/evaluate.py) | Evaluates model performance and validation outputs |
| [`etl/`](etl/) | Extract, transform, and load scripts |
| [`vis/`](vis/) | Dashboard and visualization scripts |
| [`data/reference_tables/`](data/reference_tables/) | Cached reference data used in the project |

## Final Note

Ovara is not a final answer to reproductive healthcare access. It is a data pipeline that turns fragmented federal workforce records into a clearer access signal. The model has real limitations, especially around prediction, sample size, and missing structural features. But it still shows a useful pattern: some states have fewer reproductive health providers than expected, and the highest risk states line up with independent federal shortage designations. That makes the project useful as an early access intelligence tool, especially for identifying where deeper policy, clinical, and geographic analysis should happen next.

*Kenneth Yeaher INST737 Final Project University of Maryland, Spring 2026*