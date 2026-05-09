import pandas as pd
from pathlib import Path
from utils.io import save_csv, save_json
from utils.logging_config import setup_logger

logger = setup_logger("ovara.access_risk_model")

# file paths

INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_FILE = Path("data/model_outputs/access_risk_classified.csv")
SUMMARY_FILE = Path("data/model_outputs/access_risk_summary.csv")
METADATA_FILE = Path("data/model_outputs/access_risk_metadata.json")

# tier definitions
# states are binned by residual: most negative = most underserved

TIER_BOUNDS = [
    ("high_risk", 0.25),
    ("moderate_risk", 0.50),
    ("adequate", 0.75),
    ("well_served", 1.0),
]

# columns carried into final report

OUTPUT_COLUMNS = [
    "practice_state",
    "state_name",
    "provider_count",
    "metro_population",
    "providers_per_100k",
    "predicted_provider_density",
    "residual",
    "risk_score",
    "risk_tier",
    "supply_gap",
    "risk_rank",
    "taxonomy_diversity",
    "recent_provider_growth",
]


def load_regression_results() -> pd.DataFrame:
    """load regression output with residuals."""
    df = pd.read_csv(INPUT_FILE)

    required = {"state_name", "residual", "providers_per_100k", "predicted_provider_density"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    df = df.replace([float("inf"), float("-inf")], pd.NA)

    before = df.shape[0]
    df = df.dropna(subset=["residual"]).copy()
    dropped = before - df.shape[0]

    if dropped > 0:
        logger.warning(f"dropped {dropped} rows with missing residuals")

    logger.info(f"states loaded: {df.shape[0]}")
    return df


def compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Continuous 0-100 risk score based on residual percentile.
    100 = most underserved, 0 = most oversupplied.
    """
    df["risk_score"] = (
        df["residual"]
        .rank(ascending=True, pct=True)
        .rsub(1)
        .mul(100)
        .round(1)
    )

    logger.info(f"risk score range: [{df['risk_score'].min()}, {df['risk_score'].max()}]")
    return df


def assign_risk_tiers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """bin states into risk tiers using quantile boundaries from TIER_BOUNDS."""
    labels = [t[0] for t in TIER_BOUNDS]
    quantiles = [t[1] for t in TIER_BOUNDS]

    # compute threshold values from residual distribution
    thresholds = [df["residual"].min() - 1]
    for q in quantiles:
        thresholds.append(df["residual"].quantile(q))

    df["risk_tier"] = pd.cut(
        df["residual"],
        bins=thresholds,
        labels=labels,
        include_lowest=True,
    )

    # store thresholds for reproducibility
    threshold_map = {
        label: {"quantile": q, "residual_cutoff": round(df["residual"].quantile(q), 4)}
        for label, q in TIER_BOUNDS
    }

    logger.info("tier thresholds:")
    for tier, info in threshold_map.items():
        logger.info(f"  {tier}: q={info['quantile']}  cutoff={info['residual_cutoff']}")

    return df, threshold_map


def compute_supply_gap(df: pd.DataFrame) -> pd.DataFrame:
    """absolute magnitude of provider shortfall relative to prediction."""
    df["supply_gap"] = df["residual"].clip(upper=0).abs()
    return df


def compute_risk_rank(df: pd.DataFrame) -> pd.DataFrame:
    """rank states by severity (1 = most underserved)."""
    df["risk_rank"] = df["residual"].rank(ascending=True, method="min").astype(int)
    return df


def build_risk_summary(df: pd.DataFrame) -> pd.DataFrame:
    """aggregate risk tier statistics for reporting."""
    summary = (
        df.groupby("risk_tier", observed=False, as_index=False)
        .agg(
            state_count=("state_name", "count"),
            avg_residual=("residual", "mean"),
            avg_density=("providers_per_100k", "mean"),
            avg_supply_gap=("supply_gap", "mean"),
            avg_risk_score=("risk_score", "mean"),
        )
    )

    summary = summary.sort_values("avg_residual").reset_index(drop=True)

    logger.info(f"tier summary:\n{summary.to_string(index=False)}")
    return summary


def save_results(df: pd.DataFrame, summary: pd.DataFrame, thresholds: dict) -> None:
    """Save classified dataset, summary table, and threshold metadata."""
    # only include columns that exist in the dataframe
    valid_cols = [c for c in OUTPUT_COLUMNS if c in df.columns]
    save_csv(df[valid_cols], OUTPUT_FILE, logger)
    save_csv(summary, SUMMARY_FILE, logger)

    metadata = {
        "tier_thresholds": thresholds,
        "total_states": len(df),
        "high_risk_states": df[df["risk_tier"] == "high_risk"]["state_name"].tolist(),
    }
    save_json(metadata, METADATA_FILE, logger)


def run_access_risk_model() -> pd.DataFrame:
    """full access risk classification workflow."""
    try:
        df = load_regression_results()
        df = compute_risk_score(df)
        df, thresholds = assign_risk_tiers(df)
        df = compute_supply_gap(df)
        df = compute_risk_rank(df)
        summary = build_risk_summary(df)
        save_results(df, summary, thresholds)
        return df

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during risk classification: {e}")
        raise


if __name__ == "__main__":
    run_access_risk_model()