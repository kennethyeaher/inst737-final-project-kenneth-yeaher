from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_val_score
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from utils.io import save_csv, save_json
from utils.logging_config import setup_logger
from analysis.regression_model import FEATURE_COLUMNS, TARGET_COLUMN

logger = setup_logger("ovara.evaluate")

# file paths

INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_DIR = Path("data/model_outputs")

# one shared split so every model in this module is scored on the same folds
CV_SPLITTER = KFold(n_splits=5, shuffle=True, random_state=42)

# smallest sample the leak check will report a correlation on
MIN_LEAK_CHECK_ROWS = 5

# candidate feature sets, compared on cross validated R2 before one is chosen.
# every candidate is leak free, meaning no feature is derived from provider_count
CANDIDATE_FEATURE_SETS = {
    "four_composition": [
        "taxonomy_diversity",
        "pct_recent_entrants",
        "pct_female_25_44",
        "provider_enum_year_centered",
    ],
    "two_composition": [
        "taxonomy_diversity",
        "pct_recent_entrants",
    ],
    "taxonomy_only": [
        "taxonomy_diversity",
    ],
}

# growth_per_100k was the winning feature until a leak check retired it. It is
# recent_provider_growth over state_population, and the target is provider_count
# over state_population, so the two share a denominator and the numerator of one
# is a subset of the numerator of the other
LEAKING_FEATURE = "growth_per_100k"
LEAK_SOURCE_COLUMN = "recent_provider_growth"
TARGET_NUMERATOR_COLUMN = "provider_count"


def load_evaluation_data() -> pd.DataFrame:
    """load regression results for model evaluation."""
    df = pd.read_csv(INPUT_FILE)

    required = set(FEATURE_COLUMNS + [TARGET_COLUMN, "residual", "predicted_provider_density"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    df = df.replace([float("inf"), float("-inf")], pd.NA)

    before = df.shape[0]
    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN]).copy()
    dropped = before - df.shape[0]

    if dropped > 0:
        logger.warning(f"dropped {dropped} rows with missing values")

    logger.info(f"states loaded: {df.shape[0]}")
    return df


def evaluate_model(df: pd.DataFrame) -> dict:
    """cross validation, feature importance, and residual diagnostics."""
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    residuals = df["residual"]

    model = LinearRegression()

    # 5-fold cross validation
    cv_r2 = cross_val_score(model, X, y, cv=CV_SPLITTER, scoring="r2")
    cv_mae = -cross_val_score(model, X, y, cv=CV_SPLITTER, scoring="neg_mean_absolute_error")

    # train-set metrics
    model.fit(X, y)
    train_pred = model.predict(X)
    train_r2 = r2_score(y, train_pred)
    train_mae = mean_absolute_error(y, train_pred)
    train_rmse = np.sqrt(mean_squared_error(y, train_pred))

    # naive baseline: always predict the mean
    baseline_mae = mean_absolute_error(y, np.full(len(y), y.mean()))

    # standardized coefficients (scale-independent importance)
    scaler = StandardScaler()
    model_scaled = LinearRegression()
    model_scaled.fit(scaler.fit_transform(X), y)
    std_coefs = dict(zip(FEATURE_COLUMNS, [round(c, 4) for c in model_scaled.coef_]))

    # residual diagnostics
    threshold = residuals.std() * 2
    outlier_states = df.loc[residuals.abs() > threshold, "state_name"].tolist()

    results = {
        "n_states": len(df),
        "n_features": len(FEATURE_COLUMNS),
        "train_r2": round(train_r2, 4),
        "train_mae": round(train_mae, 4),
        "train_rmse": round(train_rmse, 4),
        "cv5_r2_mean": round(cv_r2.mean(), 4),
        "cv5_r2_std": round(cv_r2.std(), 4),
        "cv5_mae_mean": round(cv_mae.mean(), 4),
        "cv5_mae_std": round(cv_mae.std(), 4),
        "baseline_mae": round(baseline_mae, 4),
        "standardized_coefficients": std_coefs,
        "intercept": round(model.intercept_, 4),
        "residual_std": round(residuals.std(), 4),
        "residual_skewness": round(residuals.skew(), 4),
        "residual_kurtosis": round(residuals.kurtosis(), 4),
        "outlier_states": outlier_states,
    }

    logger.info(f"train R2: {train_r2:.4f}  MAE: {train_mae:.4f}")
    logger.info(f"5-fold R2: {cv_r2.mean():.4f} +/- {cv_r2.std():.4f}")
    logger.info(f"baseline MAE (predict mean): {baseline_mae:.4f}")
    logger.info(f"residual skewness: {residuals.skew():.2f}  outliers (>2s): {outlier_states}")

    logger.info("feature importance (standardized):")
    for feat, coef in sorted(std_coefs.items(), key=lambda x: abs(x[1]), reverse=True):
        logger.info(f"  {feat}: {coef:+.4f}")

    return results



def check_target_leakage(df: pd.DataFrame) -> dict:
    """
    Record why growth_per_100k was removed, with the evidence rather than a claim.

    The retired feature scored well because it carried the target inside it.
    This measures the subset relationship it rests on and scores the same model
    with and without it, so the removal can be audited later instead of taken
    on trust.

    Parameters
    df : pd.DataFrame with the target, the leaking feature, and its replacement.

    Returns
    dict describing the leak and its cost in cross validated R2.
    """
    y = df[TARGET_COLUMN]
    share = df[LEAK_SOURCE_COLUMN] / df[TARGET_NUMERATOR_COLUMN]

    def _cv_r2(features: list[str]) -> float | None:
        """cross validated R2 for one feature set, or None if a column is missing."""
        if any(col not in df.columns for col in features):
            return None
        scores = cross_val_score(
            LinearRegression(), df[features], y, cv=CV_SPLITTER, scoring="r2"
        )
        return round(float(scores.mean()), 4)

    leak_check = {
        "retired_feature": LEAKING_FEATURE,
        "reason": (
            f"{LEAK_SOURCE_COLUMN} is a strict subset of {TARGET_NUMERATOR_COLUMN}, "
            f"and {LEAKING_FEATURE} divides it by the same denominator as the target"
        ),
        "subset_holds_for_all_states": bool(
            (df[LEAK_SOURCE_COLUMN] <= df[TARGET_NUMERATOR_COLUMN]).all()
        ),
        "recent_share_of_workforce": {
            "min": round(float(share.min()), 4),
            "max": round(float(share.max()), 4),
            "national": round(
                float(df[LEAK_SOURCE_COLUMN].sum() / df[TARGET_NUMERATOR_COLUMN].sum()), 4
            ),
        },
        "cv5_r2_with_leaking_feature": _cv_r2(["taxonomy_diversity", LEAKING_FEATURE]),
        "cv5_r2_with_leak_free_replacement": _cv_r2(
            ["taxonomy_diversity", "pct_recent_entrants"]
        ),
        "cv5_r2_taxonomy_diversity_only": _cv_r2(["taxonomy_diversity"]),
        "replacement_correlation_with_target": None,
    }

    replacement = df[["pct_recent_entrants", TARGET_COLUMN]].dropna()
    if len(replacement) >= MIN_LEAK_CHECK_ROWS:
        rho, p_value = pearsonr(replacement["pct_recent_entrants"], replacement[TARGET_COLUMN])
        leak_check["replacement_correlation_with_target"] = {
            "pearson_r": round(float(rho), 4),
            "p_value": round(float(p_value), 4),
        }

    logger.info(
        f"leak check: {LEAKING_FEATURE} retired, CV R2 "
        f"{leak_check['cv5_r2_with_leaking_feature']} with it against "
        f"{leak_check['cv5_r2_with_leak_free_replacement']} with the leak free replacement"
    )

    return leak_check

def compare_feature_sets(df: pd.DataFrame) -> dict:
    """
    Score every candidate feature set on the same folds and rank them.

    The shipped five features mixed counts and rates against a rate target and
    carried two collinear population proxies. Rather than assert a replacement,
    this fits each candidate on one shared split and lets cross validated R2
    pick the winner.

    Parameters
    df : pd.DataFrame holding every candidate feature and the target.

    Returns
    dict with one entry per candidate plus the winning set name.
    """
    y = df[TARGET_COLUMN]
    baseline_mae = mean_absolute_error(y, np.full(len(y), y.mean()))

    candidates = {}
    for name, features in CANDIDATE_FEATURE_SETS.items():
        missing = [col for col in features if col not in df.columns]
        if missing:
            logger.warning(f"skipping feature set {name}, missing columns: {missing}")
            continue

        X = df[features]
        cv_r2 = cross_val_score(LinearRegression(), X, y, cv=CV_SPLITTER, scoring="r2")
        cv_mae = -cross_val_score(
            LinearRegression(), X, y, cv=CV_SPLITTER, scoring="neg_mean_absolute_error"
        )

        candidates[name] = {
            "features": features,
            "n_features": len(features),
            "cv5_r2_mean": round(cv_r2.mean(), 4),
            "cv5_r2_std": round(cv_r2.std(), 4),
            "cv5_mae_mean": round(cv_mae.mean(), 4),
            "cv5_mae_std": round(cv_mae.std(), 4),
            "beats_baseline_mae": bool(cv_mae.mean() < baseline_mae),
        }

    winner = max(candidates, key=lambda name: candidates[name]["cv5_r2_mean"])

    comparison = {
        "n_states": len(df),
        "cv": "KFold 5 shuffle True random_state 42",
        "baseline_mae": round(baseline_mae, 4),
        "leakage_check": check_target_leakage(df),
        "candidates": candidates,
        "selected": winner,
        "selected_features": candidates[winner]["features"],
        "in_use": FEATURE_COLUMNS,
    }

    logger.info(f"feature set comparison (baseline MAE {baseline_mae:.4f}):")
    for name, scores in candidates.items():
        logger.info(
            f"  {name}: R2 {scores['cv5_r2_mean']:+.4f} "
            f"MAE {scores['cv5_mae_mean']:.4f} ({scores['n_features']} features)"
        )
    logger.info(f"selected by cross validated R2: {winner}")

    if comparison["selected_features"] != FEATURE_COLUMNS:
        logger.warning(
            f"regression_model.FEATURE_COLUMNS is {FEATURE_COLUMNS}, "
            f"but {winner} scores highest. Update FEATURE_COLUMNS to match."
        )

    return comparison


def save_results(results: dict, df: pd.DataFrame, comparison: dict) -> None:
    """Save evaluation json, the feature set comparison, and the per state detail csv."""
    # build the per state detail table sorted by residual so the worst gaps come first
    detail = df[["practice_state", "state_name", "providers_per_100k",
                  "predicted_provider_density", "residual"]].copy()
    detail["abs_error"] = detail["residual"].abs()
    detail = detail.sort_values("residual").reset_index(drop=True)

    save_json(results, OUTPUT_DIR / "evaluation_results.json", logger)
    save_json(comparison, OUTPUT_DIR / "feature_selection.json", logger)
    save_csv(detail, OUTPUT_DIR / "evaluation_detail.csv", logger)


def run_evaluation() -> dict:
    """full model evaluation workflow."""
    try:
        df = load_evaluation_data()
        results = evaluate_model(df)
        comparison = compare_feature_sets(df)
        save_results(results, df, comparison)
        return results

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during evaluation: {e}")
        raise


if __name__ == "__main__":
    run_evaluation()