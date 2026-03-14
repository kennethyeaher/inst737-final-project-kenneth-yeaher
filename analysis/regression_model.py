import pandas as pd
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

INPUT_FILE = Path("data/load/access_model_dataset.csv")
OUTPUT_FILE = Path("data/model_outputs/regression_results.csv")

FEATURE_COLUMNS = [
    "metro_population",
    "taxonomy_diversity",
    "recent_provider_growth",
    "avg_provider_enum_year",
]

TARGET_COLUMN = "providers_per_100k"

def load_model_data() -> pd.DataFrame:
    """
    Load the access modeling dataset and keep only rows
    that are usable for the first pass regression model.
    """
    print("\n[REGRESSION] ===== RUNNING REGRESSION MODEL =====")

    df = pd.read_csv(INPUT_FILE)

    required_cols = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    df = df.replace([float("inf"), float("-inf")], pd.NA)
    df = df.dropna(subset=required_cols).copy()

    print(f"[REGRESSION] Modeling rows: {df.shape[0]}")
    return df

def fit_regression(df: pd.DataFrame) -> tuple[LinearRegression, pd.DataFrame]:
    """
    Fit a simple linear regression model to estimate provider density.
    This is meant to be an early modeling baseline for Part 3.
    """
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    model = LinearRegression()
    model.fit(X, y)

    df["predicted_provider_density"] = model.predict(X)
    df["residual"] = df[TARGET_COLUMN] - df["predicted_provider_density"]

    mae = mean_absolute_error(y, df["predicted_provider_density"])
    r2 = r2_score(y, df["predicted_provider_density"])

    print(f"[REGRESSION] MAE: {mae:.4f}")
    print(f"[REGRESSION] R2: {r2:.4f}")

    return model, df


def save_results(df: pd.DataFrame) -> None:
    #Save regression outputs for later evaluation and visualization
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"[REGRESSION] Saved → {OUTPUT_FILE}")
    print("[REGRESSION] ===== MODEL COMPLETE =====")

def run_regression_model() -> pd.DataFrame:
    """
    Full regression workflow:
    load to validate to fit to score then save
    """
    df = load_model_data()
    _, results = fit_regression(df)
    save_results(results)
    return results

if __name__ == "__main__":
    run_regression_model()
