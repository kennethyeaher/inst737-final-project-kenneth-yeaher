import pandas as pd
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.regression_model")

# file paths

INPUT_FILE = Path("data/load/access_model_dataset.csv")
OUTPUT_FILE = Path("data/model_outputs/regression_results.csv")

# feature set for provider density estimation

FEATURE_COLUMNS = [
    "metro_population",
    "taxonomy_diversity",
    "recent_provider_growth",
    "avg_provider_enum_year",
    "female_25_44_pop",
]

TARGET_COLUMN = "providers_per_100k"


def load_model_data() -> pd.DataFrame:
    """load access model dataset and drop rows with missing or invalid values."""
    df = pd.read_csv(INPUT_FILE)

    required_cols = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"missing required columns: {missing_cols}")

    df = df.replace([float("inf"), float("-inf")], pd.NA)

    before = df.shape[0]
    df = df.dropna(subset=required_cols).copy()
    dropped = before - df.shape[0]

    if dropped > 0:
        logger.warning(f"dropped {dropped} rows with missing or infinite values")

    if df.empty:
        raise ValueError(
            "no modeling rows available after filtering. "
            "check access_model_dataset merge and required feature columns."
        )

    logger.info(f"modeling rows: {df.shape[0]}")
    return df


def fit_regression(df: pd.DataFrame) -> tuple[LinearRegression, pd.DataFrame]:
    """
    Estimate expected reproductive health provider density per state.
    Residuals capture the gap between predicted and actual supply.
    """
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    model = LinearRegression()
    model.fit(X, y)

    df["predicted_provider_density"] = model.predict(X)
    df["residual"] = df[TARGET_COLUMN] - df["predicted_provider_density"]

    mae = mean_absolute_error(y, df["predicted_provider_density"])
    r2 = r2_score(y, df["predicted_provider_density"])

    logger.info(f"MAE: {mae:.4f}")
    logger.info(f"R2: {r2:.4f}")
    logger.info(f"residual range: [{df['residual'].min():.2f}, {df['residual'].max():.2f}]")

    return model, df


def save_results(df: pd.DataFrame) -> None:
    """Save regression outputs so the risk classification stage can read them."""
    save_csv(df, OUTPUT_FILE, logger)


def run_regression_model() -> pd.DataFrame:
    """full regression workflow: load, validate, fit, score, save."""
    try:
        df = load_model_data()
        _, results = fit_regression(df)
        save_results(results)
        return results

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during regression: {e}")
        raise


if __name__ == "__main__":
    run_regression_model()