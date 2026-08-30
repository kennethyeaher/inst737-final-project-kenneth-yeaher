import pandas as pd
from pathlib import Path
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_access_model_dataset")

# file paths

PROVIDER_FILE = Path("data/load/provider_geo_features.csv")
COUNTY_POP_FILE = Path("data/reference_tables/county_population.csv")
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

# required columns for validation

SUPPLY_REQUIRED_COLUMNS = {
    "practice_state",
    "provider_count",
    "unique_taxonomies",
    "avg_provider_enum_year",
    "recent_provider_growth",
}

POP_REQUIRED_COLUMNS = {
    "practice_state",
    "total_population",
}

# a state population outside this range means the denominator is not a state population
MIN_STATE_POPULATION = 400_000
MAX_STATE_POPULATION = 45_000_000

# enumeration years enter the model centered so the intercept stays interpretable
ENUM_YEAR_BASELINE = 2010

# output column order

BASE_COLUMNS = [
    "practice_state",
    "state_name",
    "provider_count",
    "taxonomy_diversity",
    "avg_provider_enum_year",
    "recent_provider_growth",
    "state_population",
    "providers_per_100k",
    "growth_per_100k",
    "provider_enum_year_centered",
]

DEMAND_COLUMNS = [
    "female_25_44_pop",
    "providers_per_100k_demand",
    "pct_female_25_44",
]


# helpers

def validate_columns(df: pd.DataFrame, required: set[str], df_name: str) -> None:
    """fail fast if expected columns are missing."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {sorted(missing)}")


# pipeline stages

def load_inputs():
    """load provider features, county population, and demand data."""
    providers = pd.read_csv(PROVIDER_FILE)
    county_pop = pd.read_csv(COUNTY_POP_FILE, dtype={"county_fips": str, "state_fips": str})

    validate_columns(providers, SUPPLY_REQUIRED_COLUMNS, "provider_geo_features")
    validate_columns(county_pop, POP_REQUIRED_COLUMNS, "county_population")

    logger.info(f"provider rows: {providers.shape[0]:,}")
    logger.info(f"county population rows: {county_pop.shape[0]:,}")

    # demand data is optional
    demand = None
    if DEMAND_FILE.exists():
        demand = pd.read_csv(DEMAND_FILE)
        logger.info(f"demand rows: {demand.shape[0]:,}")
    else:
        logger.warning(f"demand file not found: {DEMAND_FILE}, skipping demand features")

    return providers, county_pop, demand


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


def check_population_plausible(pop: pd.DataFrame) -> None:
    """
    Fail the build when a state population is not one a US state could have.

    The previous denominator summed CBSA metro populations, which counts each
    metro once per county in it, so Georgia reached 198,940,717 while Wyoming
    came out at 182,193. Neither is a state population, and nothing caught it.

    Parameters
    pop : pd.DataFrame with practice_state and state_population columns.

    Returns
    None. Raises ValueError naming every implausible state.
    """
    implausible = pop[
        (pop["state_population"] < MIN_STATE_POPULATION)
        | (pop["state_population"] > MAX_STATE_POPULATION)
    ]

    if not implausible.empty:
        detail = ", ".join(
            f"{row.practice_state} {int(row.state_population):,}"
            for row in implausible.itertuples()
        )
        raise ValueError(
            f"state populations outside {MIN_STATE_POPULATION:,} to "
            f"{MAX_STATE_POPULATION:,}: {detail}"
        )


def build_state_population(county_pop: pd.DataFrame) -> pd.DataFrame:
    """
    Sum ACS county population up to the state level.

    County population is the same table the county layer divides by, so the
    state and county rates share one denominator source and one vintage.

    Parameters
    county_pop : pd.DataFrame, one row per county.

    Returns
    pd.DataFrame with practice_state and state_population columns.
    """
    pop = county_pop.copy()
    pop["total_population"] = pd.to_numeric(pop["total_population"], errors="coerce")

    pop = (
        pop.dropna(subset=["practice_state", "total_population"])
        .groupby("practice_state", as_index=False)
        .agg(state_population=("total_population", "sum"))
    )

    check_population_plausible(pop)

    logger.info(f"states with population data: {pop.shape[0]}")
    logger.info(f"total population across states: {pop['state_population'].sum():,}")
    return pop


def merge_features(supply, pop, demand=None) -> pd.DataFrame:
    """merge supply, population, and demand features. compute density metrics."""
    df = supply.merge(pop, on="practice_state", how="left", validate="one_to_one")

    # clean population values
    df["state_population"] = pd.to_numeric(df["state_population"], errors="coerce")
    df.loc[df["state_population"] <= 0, "state_population"] = pd.NA

    # population-based density
    df["providers_per_100k"] = (
        df["provider_count"] / df["state_population"] * 100000
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

    missing_pop = df["state_population"].isna().sum()
    if missing_pop > 0:
        logger.warning(f"rows missing population: {missing_pop}")

    logger.info(f"rows after merge: {df.shape[0]}")
    return df



def add_rate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Express the count and level features as rates so they match the rate target.

    The target is providers per 100k, but the raw features mix counts with
    levels. A count of recent providers partly measures how big a state is, and
    an enumeration year near 2011 pushes the intercept into the thousands.
    Rates and a centered year remove both problems.

    Parameters
    df : pd.DataFrame with state_population and the raw supply features.

    Returns
    pd.DataFrame with the rate features added.
    """
    df = df.copy()

    df["growth_per_100k"] = df["recent_provider_growth"] / df["state_population"] * 100000
    df["provider_enum_year_centered"] = df["avg_provider_enum_year"] - ENUM_YEAR_BASELINE

    # the female population share only exists when the demand stage ran
    if "female_25_44_pop" in df.columns:
        df["pct_female_25_44"] = df["female_25_44_pop"] / df["state_population"]

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
        providers, county_pop, demand = load_inputs()
        supply = build_supply_features(providers)
        pop = build_state_population(county_pop)
        access_model_df = merge_features(supply, pop, demand)
        access_model_df = add_rate_features(access_model_df)
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