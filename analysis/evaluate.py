import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from utils.logging_config import setup_logger


logger = setup_logger("ovara.evaluate")

# file paths

INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_DIR = Path("data/model_outputs")

# must match regression_model.py

FEATURE_COLUMNS = [
    "metro_population",
    "taxonomy_diversity",
    "recent_provider_growth",
    "avg_provider_enum_year",
]

TARGET_COLUMN = "providers_per_100k"


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
    cv_r2 = cross_val_score(model, X, y, cv=5, scoring="r2")
    cv_mae = -cross_val_score(model, X, y, cv=5, scoring="neg_mean_absolute_error")

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


def save_results(results: dict, df: pd.DataFrame) -> None:
    """save evaluation json and per-state detail csv."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # per-state detail
    detail = df[["practice_state", "state_name", "providers_per_100k",
                  "predicted_provider_density", "residual"]].copy()
    detail["abs_error"] = detail["residual"].abs()
    detail = detail.sort_values("residual").reset_index(drop=True)

    json_path = OUTPUT_DIR / "evaluation_results.json"
    csv_path = OUTPUT_DIR / "evaluation_detail.csv"

    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    detail.to_csv(csv_path, index=False)

    logger.info(f"saved -> {json_path}")
    logger.info(f"saved -> {csv_path}")


def run_evaluation() -> dict:
    """full model evaluation workflow."""
    try:
        df = load_evaluation_data()
        results = evaluate_model(df)
        save_results(results, df)
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