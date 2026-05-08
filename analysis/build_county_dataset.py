from __future__ import annotations
from pathlib import Path
import pandas as pd

from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_county_dataset")

# main file paths for county level feature engineering
PROVIDER_FILE = Path("data/transformed/nppes_provider_clean.csv")
CROSSWALK_FILE = Path("data/reference_tables/zip_county_lookup.csv")
POPULATION_FILE = Path("data/reference_tables/county_population.csv")
OUTPUT_FILE = Path("data/load/county_access_dataset.csv")

FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


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
        features = aggregate_county_features(matched)
        dataset = merge_population_and_compute_density(features, population)

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

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        dataset[output_cols].to_csv(OUTPUT_FILE, index=False)

        logger.info(f"saved -> {OUTPUT_FILE} ({len(dataset):,} counties)")
        return dataset

    except FileNotFoundError as e:
        logger.error(f"input file not found: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building county dataset: {e}")
        raise


if __name__ == "__main__":
    build_county_dataset()