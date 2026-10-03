"""
State level ranking of observed reproductive health provider density.

This module replaces the residual based access risk classification. That
classification cut regression residuals at quartiles, so exactly a quarter of
states were labelled high risk no matter what the data said, and it did so on
residuals from a model whose honest cross validated R2 is about 0.12. A tier
label carried more confidence than the model could support.

What survives is the part that needs no model: how many reproductive health
providers each state has per 100,000 residents, ranked. The regression residual
is kept as a diagnostic column so the model stays inspectable, but nothing is
classified from it.

No state level density thresholds are invented here. The county thresholds are
calibrated for counties and every state clears them, so a continuous ranking is
the honest output.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.io import save_csv, save_json
from utils.logging_config import setup_logger

logger = setup_logger("ovara.state_density_ranking")

# main file paths for the state density ranking
INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_FILE = Path("data/model_outputs/state_density_ranking.csv")
METADATA_FILE = Path("data/model_outputs/state_density_metadata.json")

# columns carried into the published ranking
OUTPUT_COLUMNS = [
    "practice_state",
    "state_name",
    "provider_count",
    "state_population",
    "providers_per_100k",
    "density_rank",
    "density_percentile",
    "taxonomy_diversity",
    "recent_provider_growth",
    "predicted_provider_density",
    "regression_residual_diagnostic",
]


def load_regression_results() -> pd.DataFrame:
    """load the regression output that carries observed density and residuals."""
    df = pd.read_csv(INPUT_FILE)

    required = {"state_name", "providers_per_100k", "residual", "predicted_provider_density"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    df = df.replace([float("inf"), float("-inf")], pd.NA)

    before = df.shape[0]
    df = df.dropna(subset=["providers_per_100k"]).copy()
    dropped = before - df.shape[0]

    if dropped > 0:
        logger.warning(f"dropped {dropped} rows with missing density")

    logger.info(f"states loaded: {df.shape[0]}")
    return df


def rank_by_density(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rank states by observed provider density, thinnest first.

    Rank 1 is the state with the fewest providers per 100,000 residents. The
    percentile is the state's position in the national density distribution, so
    a low percentile means a thin workforce.

    Parameters
    df : pd.DataFrame with a providers_per_100k column.

    Returns
    pd.DataFrame with density_rank and density_percentile added.
    """
    df = df.copy()

    df["density_rank"] = (
        df["providers_per_100k"].rank(ascending=True, method="min").astype(int)
    )
    df["density_percentile"] = (
        df["providers_per_100k"].rank(ascending=True, pct=True).mul(100).round(1)
    )

    thinnest = df.loc[df["density_rank"].idxmin()]
    logger.info(
        f"thinnest state: {thinnest['practice_state']} at "
        f"{thinnest['providers_per_100k']:.2f} per 100k"
    )

    return df.sort_values("density_rank").reset_index(drop=True)


def keep_residual_as_diagnostic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename the regression residual so it cannot be mistaken for a classification.

    The residual is still useful for inspecting where the model over or under
    predicts, but it no longer decides anything.

    Parameters
    df : pd.DataFrame with a residual column.

    Returns
    pd.DataFrame with the residual renamed.
    """
    return df.rename(columns={"residual": "regression_residual_diagnostic"})


def build_metadata(df: pd.DataFrame) -> dict:
    """summarize the national density picture for the run metadata."""
    national_density = df["provider_count"].sum() / df["state_population"].sum() * 100000
    below_national = int((df["providers_per_100k"] < national_density).sum())

    metadata = {
        "total_states": len(df),
        "national_providers_per_100k": round(float(national_density), 4),
        "median_providers_per_100k": round(float(df["providers_per_100k"].median()), 4),
        "states_below_national_rate": below_national,
        "thinnest_states": df.nsmallest(10, "providers_per_100k")["practice_state"].tolist(),
        "densest_states": df.nlargest(10, "providers_per_100k")["practice_state"].tolist(),
        "classification": (
            "none. state level output is a continuous ranking of observed density, "
            "not a tier assignment"
        ),
    }

    logger.info(
        f"national density: {national_density:.2f} per 100k, "
        f"{below_national} of {len(df)} states below it"
    )
    return metadata


def save_results(df: pd.DataFrame, metadata: dict) -> None:
    """save the ranking csv and its metadata."""
    valid_cols = [col for col in OUTPUT_COLUMNS if col in df.columns]
    save_csv(df[valid_cols], OUTPUT_FILE, logger)
    save_json(metadata, METADATA_FILE, logger)


def run_state_density_ranking() -> pd.DataFrame:
    """rank every state by observed provider density and save the result."""
    try:
        df = load_regression_results()
        df = keep_residual_as_diagnostic(df)
        df = rank_by_density(df)
        metadata = build_metadata(df)
        save_results(df, metadata)
        return df

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building the density ranking: {e}")
        raise


if __name__ == "__main__":
    run_state_density_ranking()
