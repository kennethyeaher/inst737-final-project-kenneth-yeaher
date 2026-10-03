from __future__ import annotations
from pathlib import Path
import pandas as pd

from utils.fips import FIPS_TO_STATE
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_county_dataset")

# main file paths for county level feature engineering
PROVIDER_FILE = Path("data/transformed/nppes_provider_clean.csv")
CROSSWALK_FILE = Path("data/reference_tables/zip_county_lookup.csv")
POPULATION_FILE = Path("data/reference_tables/county_population.csv")
OUTPUT_FILE = Path("data/load/county_access_dataset.csv")

# share of crosswalk matched providers allowed to miss a population row before warning
MAX_UNMATCHED_POPULATION_SHARE = 0.02


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """load provider records, ZIP to county lookup, and county population data."""
    providers = pd.read_csv(
        PROVIDER_FILE,
        parse_dates=["provider_enumeration_date"],
        usecols=[
            "npi",
            "practice_state",
            "zip5",
            "taxonomy_code_1",
            "provider_enumeration_date",
        ],
    )
    logger.info(f"providers loaded: {len(providers):,}")

    crosswalk = pd.read_csv(CROSSWALK_FILE, dtype={"county_fips": str, "state_fips": str})
    logger.info(f"crosswalk ZCTAs: {len(crosswalk):,}")

    population = pd.read_csv(POPULATION_FILE, dtype={"county_fips": str, "state_fips": str})
    logger.info(f"county population rows: {len(population):,}")

    return providers, crosswalk, population


def assign_providers_to_counties(
    providers: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> pd.DataFrame:
    """match providers to counties using their ZIP code."""
    merged = providers.merge(crosswalk[["zip5", "county_fips"]], on="zip5", how="left")

    unmatched = merged["county_fips"].isna().sum()
    if unmatched > 0:
        logger.warning(f"providers without county match: {unmatched:,} ({unmatched / len(merged):.1%})")

    # keep only providers with a county match so county level aggregation stays clean
    matched = merged.dropna(subset=["county_fips"]).copy()

    logger.info(f"providers matched to counties: {len(matched):,}")
    return matched


def aggregate_county_features(providers: pd.DataFrame) -> pd.DataFrame:
    """create county level provider supply features."""
    recent_cutoff = providers["provider_enumeration_date"].max() - pd.DateOffset(years=3)

    providers = providers.copy()
    providers["enum_year"] = providers["provider_enumeration_date"].dt.year
    providers["is_recent"] = providers["provider_enumeration_date"] >= recent_cutoff

    agg = (
        providers.groupby("county_fips", as_index=False)
        .agg(
            provider_count=("npi", "count"),
            unique_taxonomies=("taxonomy_code_1", "nunique"),
            avg_provider_enum_year=("enum_year", "mean"),
            recent_provider_growth=("is_recent", "sum"),
        )
    )

    agg["recent_provider_growth"] = agg["recent_provider_growth"].astype(int)

    logger.info(f"counties with providers: {len(agg):,}")
    return agg


def _summarize_fips_prefixes(county_fips: set[str]) -> str:
    """Reduce a set of county FIPS codes to their sorted three digit prefixes for logging."""
    return ", ".join(sorted({code[:3] for code in county_fips}))


def check_county_geography_vintage(
    providers: pd.DataFrame,
    population: pd.DataFrame,
) -> None:
    """
    Stop the build when a state's crosswalk counties cannot match its population counties.

    Census county geographies change between vintages. Connecticut replaced its
    eight legacy counties with nine planning regions in the 2022 ACS, so a
    crosswalk built on an older vintage hands over county codes that no
    population row can ever match. The merge would drop those providers without
    complaining and publish the state as an access desert, so raise instead.

    Parameters
    providers : pd.DataFrame
        Providers already assigned a county_fips by the crosswalk.
    population : pd.DataFrame
        County population reference table that defines the valid county universe.

    Returns
    None. Raises ValueError on a vintage mismatch.
    """
    assigned = providers.copy()
    assigned["state_fips"] = assigned["county_fips"].str[:2]

    population_by_state = population.groupby("state_fips")["county_fips"].apply(set)

    for state_fips, state_rows in assigned.groupby("state_fips"):
        population_counties = population_by_state.get(state_fips, set())

        # territories have no population rows at all, which is a coverage gap
        # rather than a vintage mismatch, so warn and move on
        if not population_counties:
            logger.warning(
                f"no population rows for state FIPS {state_fips}, "
                f"{len(state_rows):,} providers will be dropped"
            )
            continue

        assigned_counties = set(state_rows["county_fips"])

        if assigned_counties & population_counties:
            continue

        state = FIPS_TO_STATE.get(state_fips, state_fips)
        raise ValueError(
            f"county geography vintage mismatch in {state}: the crosswalk assigned "
            f"{len(state_rows):,} providers to county FIPS prefixes "
            f"{_summarize_fips_prefixes(assigned_counties)} but county_population.csv "
            f"only holds prefixes {_summarize_fips_prefixes(population_counties)}. "
            "Rebuild the ZIP to county crosswalk against the population vintage."
        )


def check_population_join_coverage(
    providers: pd.DataFrame,
    population: pd.DataFrame,
) -> None:
    """
    Warn when too many crosswalk matched providers fail to land on a population row.

    This is the softer companion to check_county_geography_vintage. A partial
    overlap between vintages does not trip the hard guard, but it still leaks
    providers, so surface the per state breakdown.

    Parameters
    providers : pd.DataFrame
        Providers already assigned a county_fips by the crosswalk.
    population : pd.DataFrame
        County population reference table.

    Returns
    None.
    """
    known_counties = set(population["county_fips"])
    dropped = providers[~providers["county_fips"].isin(known_counties)]

    share = len(dropped) / len(providers)
    if share <= MAX_UNMATCHED_POPULATION_SHARE:
        return

    breakdown = dropped["practice_state"].value_counts()
    detail = ", ".join(f"{state} {count:,}" for state, count in breakdown.items())
    logger.warning(
        f"{len(dropped):,} of {len(providers):,} crosswalk matched providers "
        f"({share:.1%}) have no population row: {detail}"
    )


def merge_population_and_compute_density(
    county_features: pd.DataFrame,
    population: pd.DataFrame,
) -> pd.DataFrame:
    """merge provider features with county population and calculate provider density."""
    # use population as the base so counties with zero providers still appear in the dataset
    merged = population.merge(county_features, on="county_fips", how="left")

    for col in ["provider_count", "unique_taxonomies", "recent_provider_growth"]:
        merged[col] = merged[col].fillna(0).astype(int)

    merged["avg_provider_enum_year"] = merged["avg_provider_enum_year"].fillna(0)

    merged["providers_per_100k"] = (
        merged["provider_count"] / merged["total_population"] * 100_000
    ).round(4)

    # map state FIPS back to state abbreviations for dashboard filters and summaries
    merged["practice_state"] = merged["state_fips"].map(FIPS_TO_STATE)
    merged = merged.dropna(subset=["practice_state"])

    zero_provider = (merged["provider_count"] == 0).sum()
    logger.info(f"counties with zero providers: {zero_provider:,} / {len(merged):,}")

    return merged.sort_values("county_fips").reset_index(drop=True)


def build_county_dataset() -> pd.DataFrame:
    """run the full county level dataset build."""
    try:
        providers, crosswalk, population = load_inputs()
        matched = assign_providers_to_counties(providers, crosswalk)
        check_county_geography_vintage(matched, population)
        features = aggregate_county_features(matched)
        dataset = merge_population_and_compute_density(features, population)
        check_population_join_coverage(matched, population)

        output_cols = [
            "county_fips",
            "county_name",
            "state_fips",
            "practice_state",
            "provider_count",
            "unique_taxonomies",
            "avg_provider_enum_year",
            "recent_provider_growth",
            "total_population",
            "providers_per_100k",
        ]

        save_csv(dataset[output_cols], OUTPUT_FILE, logger)
        logger.info(f"county rows saved: {len(dataset):,}")
        return dataset

    except FileNotFoundError as e:
        logger.error(f"input file not found: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building county dataset: {e}")
        raise


if __name__ == "__main__":
    build_county_dataset()