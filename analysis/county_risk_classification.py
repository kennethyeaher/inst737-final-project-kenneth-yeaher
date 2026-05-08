from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from utils.logging_config import setup_logger

logger = setup_logger("ovara.county_risk_classification")

# main file paths for county risk outputs
INPUT_FILE = Path("data/load/county_access_dataset.csv")
OUTPUT_FILE = Path("data/model_outputs/county_risk_classified.csv")
SUMMARY_FILE = Path("data/model_outputs/county_risk_summary.csv")
METADATA_FILE = Path("data/model_outputs/county_risk_metadata.json")

# density thresholds used to classify county access risk
RISK_TIERS = [
    ("access_desert", 0.0),
    ("critical", 5.0),
    ("underserved", 10.0),
    ("adequate", 20.0),
    ("well_served", float("inf")),
]


def load_county_data() -> pd.DataFrame:
    """load county access data and check that the needed columns exist."""
    df = pd.read_csv(INPUT_FILE, dtype={"county_fips": str, "state_fips": str})

    required = {
        "county_fips",
        "county_name",
        "practice_state",
        "provider_count",
        "total_population",
        "providers_per_100k",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    logger.info(f"counties loaded: {len(df):,}")
    return df


def assign_risk_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """classify counties based on provider density thresholds."""
    df = df.copy()

    def _tier(density: float) -> str:
        """return the first risk tier where county density is below the threshold."""
        for label, upper in RISK_TIERS:
            if density <= upper:
                return label

        return RISK_TIERS[-1][0]

    df["risk_tier"] = df["providers_per_100k"].apply(_tier)

    # higher risk score means weaker county level access
    # 100 is closest to an access desert, while 0 is the strongest density group
    df["risk_score"] = (
        df["providers_per_100k"]
        .rank(ascending=True, pct=True)
        .rsub(1)
        .mul(100)
        .round(1)
    )

    # lower provider density gets a higher priority rank
    df["risk_rank"] = df["providers_per_100k"].rank(ascending=True, method="min").astype(int)

    tier_counts = df["risk_tier"].value_counts()
    logger.info("county risk tier distribution:")

    for label, _ in RISK_TIERS:
        logger.info(f"  {label}: {tier_counts.get(label, 0):,}")

    return df


def build_county_summary(df: pd.DataFrame) -> pd.DataFrame:
    """summarize county access patterns by risk tier."""
    tier_order = [tier[0] for tier in RISK_TIERS]

    summary = (
        df.groupby("risk_tier", as_index=False)
        .agg(
            county_count=("county_fips", "count"),
            total_population=("total_population", "sum"),
            avg_density=("providers_per_100k", "mean"),
            avg_providers=("provider_count", "mean"),
            median_density=("providers_per_100k", "median"),
        )
    )

    # keep the summary ordered from worst access to strongest access
    summary["risk_tier"] = pd.Categorical(
        summary["risk_tier"],
        categories=tier_order,
        ordered=True,
    )
    summary = summary.sort_values("risk_tier").reset_index(drop=True)

    logger.info(f"county risk summary:\n{summary.to_string(index=False)}")
    return summary


def save_results(df: pd.DataFrame, summary: pd.DataFrame) -> None:
    """save classified county data, tier summary, and metadata."""
    output_cols = [
        "county_fips",
        "county_name",
        "state_fips",
        "practice_state",
        "provider_count",
        "total_population",
        "providers_per_100k",
        "unique_taxonomies",
        "recent_provider_growth",
        "risk_tier",
        "risk_score",
        "risk_rank",
    ]

    valid_cols = [col for col in output_cols if col in df.columns]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    df[valid_cols].to_csv(OUTPUT_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)

    zero_provider = int((df["provider_count"] == 0).sum())
    total_pop_desert = int(df[df["risk_tier"] == "access_desert"]["total_population"].sum())

    # metadata gives the dashboard and README a quick summary of the county risk output
    metadata = {
        "tier_thresholds": {
            tier: threshold
            for tier, threshold in RISK_TIERS
            if threshold != float("inf")
        },
        "total_counties": len(df),
        "counties_zero_providers": zero_provider,
        "population_in_access_deserts": total_pop_desert,
        "states_with_deserts": sorted(
            df[df["risk_tier"] == "access_desert"]["practice_state"].unique().tolist()
        ),
    }

    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"saved classified -> {OUTPUT_FILE}")
    logger.info(f"saved summary -> {SUMMARY_FILE}")
    logger.info(f"saved metadata -> {METADATA_FILE}")


def run_county_risk_classification() -> pd.DataFrame:
    """run the full county risk classification workflow."""
    try:
        df = load_county_data()
        df = assign_risk_tiers(df)
        summary = build_county_summary(df)
        save_results(df, summary)
        return df

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except Exception as e:
        logger.error(f"unexpected error in county risk classification: {e}")
        raise


if __name__ == "__main__":
    run_county_risk_classification()