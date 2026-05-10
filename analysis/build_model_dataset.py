import pandas as pd
from pathlib import Path
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_model_dataset")

# file path

INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_FILE = Path("data/load/provider_geo_features.csv")


def load_provider_data() -> pd.DataFrame:
    """load cleaned reproductive health provider dataset."""
    logger.info("loading reproductive health provider data...")

    df = pd.read_csv(INPUT_FILE, parse_dates=["provider_enumeration_date"])

    logger.info(f"providers loaded: {df.shape[0]:,}")
    return df


def compute_supply_counts(df: pd.DataFrame) -> pd.Series:
    """count reproductive health providers per state-zip pair."""
    return (
        df.groupby(["practice_state", "zip5"])
        .size()
        .rename("provider_count")
    )


def compute_taxonomy_diversity(df: pd.DataFrame) -> pd.Series:
    """count unique reproductive health specialties per state-zip pair."""
    return (
        df.groupby(["practice_state", "zip5"])["taxonomy_code_1"]
        .nunique()
        .rename("unique_taxonomies")
    )


def compute_maturity_proxy(df: pd.DataFrame) -> pd.Series:
    """average enumeration year as a workforce maturity indicator."""
    return (
        df.assign(enum_year=df["provider_enumeration_date"].dt.year)
        .groupby(["practice_state", "zip5"])["enum_year"]
        .mean()
        .rename("avg_provider_enum_year")
    )


def compute_recent_growth(df: pd.DataFrame) -> pd.Series:
    """count providers enumerated in the last 3 years as a growth signal."""
    recent_cutoff = df["provider_enumeration_date"].max() - pd.DateOffset(years=3)

    return (
        df[df["provider_enumeration_date"] >= recent_cutoff]
        .groupby(["practice_state", "zip5"])
        .size()
        .rename("recent_provider_growth")
    )


def build_provider_geo_features() -> pd.DataFrame:
    """
    Build ZIP level reproductive health provider feature dataset.
    Aggregates supply counts, specialty diversity, workforce maturity,
    and recent growth from the cleaned provider data.
    """
    try:
        df = load_provider_data()

        geo_features = pd.concat(
            [
                compute_supply_counts(df),
                compute_taxonomy_diversity(df),
                compute_maturity_proxy(df),
                compute_recent_growth(df),
            ],
            axis=1,
        ).fillna(0).reset_index()

        logger.info(f"zip-level rows: {geo_features.shape[0]:,}")
        logger.info(f"states covered: {geo_features['practice_state'].nunique()}")
        save_csv(geo_features, OUTPUT_FILE, logger)

        return geo_features

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except KeyError as e:
        logger.error(f"missing expected column: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building geo features: {e}")
        raise


if __name__ == "__main__":
    build_provider_geo_features()