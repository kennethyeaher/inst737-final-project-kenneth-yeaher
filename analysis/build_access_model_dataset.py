import pandas as pd
from pathlib import Path
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_access_model_dataset")

# file paths

PROVIDER_FILE = Path("data/load/provider_geo_features.csv")
CBSA_REF_FILE = Path("data/load/cbsa_reference_dataset.csv")
DEMAND_FILE = Path("data/reference_tables/acs_female_25_44_by_state.csv")
OUTPUT_FILE = Path("data/load/access_model_dataset.csv")


# state abbreviation to full name mapping

STATE_ABBR_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

NAME_TO_STATE_ABBR = {v: k for k, v in STATE_ABBR_TO_NAME.items()}

# required columns for validation

SUPPLY_REQUIRED_COLUMNS = {
    "practice_state",
    "provider_count",
    "unique_taxonomies",
    "avg_provider_enum_year",
    "recent_provider_growth",
}

POP_REQUIRED_COLUMNS = {
    "State Name",
    "population_2024",
}

# output column order

BASE_COLUMNS = [
    "practice_state",
    "state_name",
    "provider_count",
    "taxonomy_diversity",
    "avg_provider_enum_year",
    "recent_provider_growth",
    "metro_population",
    "providers_per_100k",
]

DEMAND_COLUMNS = [
    "female_25_44_pop",
    "providers_per_100k_demand",
]


# helpers

def validate_columns(df: pd.DataFrame, required: set[str], df_name: str) -> None:
    """fail fast if expected columns are missing."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {sorted(missing)}")


# pipeline stages

def load_inputs():
    """load provider features, CBSA reference, and demand data."""
    providers = pd.read_csv(PROVIDER_FILE)
    cbsa_ref = pd.read_csv(CBSA_REF_FILE)

    validate_columns(providers, SUPPLY_REQUIRED_COLUMNS, "provider_geo_features")
    validate_columns(cbsa_ref, POP_REQUIRED_COLUMNS, "cbsa_reference_dataset")

    logger.info(f"provider rows: {providers.shape[0]:,}")
    logger.info(f"CBSA reference rows: {cbsa_ref.shape[0]:,}")

    # demand data is optional
    demand = None
    if DEMAND_FILE.exists():
        demand = pd.read_csv(DEMAND_FILE)
        logger.info(f"demand rows: {demand.shape[0]:,}")
    else:
        logger.warning(f"demand file not found: {DEMAND_FILE}, skipping demand features")

    return providers, cbsa_ref, demand


def build_supply_features(providers: pd.DataFrame) -> pd.DataFrame:
    """build state level supply features from ZIP level provider data."""
    providers = providers[providers["practice_state"].isin(STATE_ABBR_TO_NAME)].copy()

    supply = (
        providers.groupby("practice_state", as_index=False)
        .agg(
            provider_count=("provider_count", "sum"),
            taxonomy_diversity=("unique_taxonomies", "mean"),
            avg_provider_enum_year=("avg_provider_enum_year", "mean"),
            recent_provider_growth=("recent_provider_growth", "sum"),
        )
    )

    supply["state_name"] = supply["practice_state"].map(STATE_ABBR_TO_NAME)

    logger.info(f"states with providers: {supply.shape[0]}")
    return supply


def build_population_proxy(cbsa_ref: pd.DataFrame) -> pd.DataFrame:
    """aggregate metro population totals to the state level."""
    pop = cbsa_ref.copy()

    pop["population_2024"] = pd.to_numeric(pop["population_2024"], errors="coerce")
    pop["practice_state"] = (
        pop["State Name"].astype(str).str.strip().map(NAME_TO_STATE_ABBR)
    )

    pop = (
        pop.dropna(subset=["practice_state"])
        .groupby("practice_state", as_index=False)
        .agg(metro_population=("population_2024", "sum"))
    )

    logger.info(f"states with population data: {pop.shape[0]}")
    return pop


def merge_features(supply, pop, demand=None) -> pd.DataFrame:
    """merge supply, population, and demand features. compute density metrics."""
    df = supply.merge(pop, on="practice_state", how="left", validate="one_to_one")

    # clean population values
    df["metro_population"] = pd.to_numeric(df["metro_population"], errors="coerce")
    df.loc[df["metro_population"] <= 0, "metro_population"] = pd.NA

    # population-based density
    df["providers_per_100k"] = (
        df["provider_count"] / df["metro_population"] * 100000
    )

    # demand-adjusted density
    if demand is not None:
        df = df.merge(
            demand[["practice_state", "female_25_44_pop"]],
            on="practice_state",
            how="left",
        )
        df["providers_per_100k_demand"] = (
            df["provider_count"] / df["female_25_44_pop"] * 100000
        )
        missing_demand = df["female_25_44_pop"].isna().sum()
        if missing_demand > 0:
            logger.warning(f"rows missing demand data: {missing_demand}")

    missing_pop = df["metro_population"].isna().sum()
    if missing_pop > 0:
        logger.warning(f"rows missing population: {missing_pop}")

    logger.info(f"rows after merge: {df.shape[0]}")
    return df


def save_output(df: pd.DataFrame) -> None:
    """save the access modeling dataset for regression and clustering."""

    # include demand columns only if they exist
    output_cols = BASE_COLUMNS.copy()
    if "female_25_44_pop" in df.columns:
        output_cols += DEMAND_COLUMNS

    df = df[output_cols]

    logger.info(f"columns: {list(df.columns)}")
    save_csv(df, OUTPUT_FILE, logger)


def build_access_model_dataset() -> pd.DataFrame:
    """run the full access model dataset workflow."""
    try:
        providers, cbsa_ref, demand = load_inputs()
        supply = build_supply_features(providers)
        pop = build_population_proxy(cbsa_ref)
        access_model_df = merge_features(supply, pop, demand)
        save_output(access_model_df)

        return access_model_df

    except FileNotFoundError as e:
        logger.error(f"input file not found: {e}")
        raise

    except ValueError as e:
        logger.error(f"column validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building access model dataset: {e}")
        raise


if __name__ == "__main__":
    build_access_model_dataset()