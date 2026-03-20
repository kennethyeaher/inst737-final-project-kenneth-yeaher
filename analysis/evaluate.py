import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
 
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
    """Load regression results for model evaluation."""
    print("\n[EVAL] ===== RUNNING MODEL EVALUATION =====")
 
    df = pd.read_csv(INPUT_FILE)
 
    required = set(FEATURE_COLUMNS + [TARGET_COLUMN, "residual", "predicted_provider_density"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
 
    df = df.replace([float("inf"), float("-inf")], pd.NA)
    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN]).copy()
 
    print(f"[EVAL] States loaded: {df.shape[0]}")
    return df


def evaluate_model(df: pd.DataFrame) -> dict:
    """Cross validation, feature importance, and residual diagnostics in one pass."""
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
 
    print(f"[EVAL] Train R²: {train_r2:.4f}  MAE: {train_mae:.4f}")
    print(f"[EVAL] 5-fold R²: {cv_r2.mean():.4f} ± {cv_r2.std():.4f}")
    print(f"[EVAL] Baseline MAE (predict mean): {baseline_mae:.4f}")
    print(f"[EVAL] Residual skewness: {residuals.skew():.2f}  outliers (>2σ): {outlier_states}")
 
    print(f"[EVAL] Feature importance (standardized):")
    for feat, coef in sorted(std_coefs.items(), key=lambda x: abs(x[1]), reverse=True):
        print(f"  {feat}: {coef:+.4f}")
 
    return results


def save_results(results: dict, df: pd.DataFrame) -> None:
    """Save evaluation JSON and per-state detail CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
 
    # per-state detail
    detail = df[["practice_state", "state_name", "providers_per_100k",
                  "predicted_provider_density", "residual"]].copy()
    detail["abs_error"] = detail["residual"].abs()
    detail = detail.sort_values("residual").reset_index(drop=True)
 
    with open(OUTPUT_DIR / "evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2)
 
    detail.to_csv(OUTPUT_DIR / "evaluation_detail.csv", index=False)
 
    print(f"\n[EVAL] Saved → evaluation_results.json, evaluation_detail.csv")
    print("[EVAL] ===== EVALUATION COMPLETE =====")


def run_evaluation() -> dict:
    """Full model evaluation workflow."""
    df = load_evaluation_data()
    results = evaluate_model(df)
    save_results(results, df)
    return results


if __name__ == "__main__":
    run_evaluation()
