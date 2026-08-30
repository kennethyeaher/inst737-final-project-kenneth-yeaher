import pandas as pd
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.regression_model")

# file paths

INPUT_FILE = Path("data/load/access_model_dataset.csv")
OUTPUT_FILE = Path("data/model_outputs/regression_results.csv")

# feature set for provider density estimation
# chosen by cross validated R2 in analysis/evaluate.py, see
# data/model_outputs/feature_selection.json for the comparison that picked it

FEATURE_COLUMNS = [
    "taxonomy_diversity",
]

TARGET_COLUMN = "providers_per_100k"

# residuals that feed the risk tiers are scored out of fold on this split,
# which matches the split analysis/evaluate.py reports against
CV_SPLITTER = KFold(n_splits=5, shuffle=True, random_state=42)


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
    Fit the density model on every state and record the in sample prediction.

    This fit exists to report coefficients on the full sample. Its predictions
    are in sample, so they are saved under their own names and are not what the
    risk tiers are cut from. See score_out_of_fold for the ones that are.

    Parameters
    df : pd.DataFrame with the feature columns and the target.

    Returns
    tuple of the fitted model and the frame with in sample columns added.
    """
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    model = LinearRegression()
    model.fit(X, y)

    df["predicted_density_in_sample"] = model.predict(X)
    df["residual_in_sample"] = y - df["predicted_density_in_sample"]

    mae = mean_absolute_error(y, df["predicted_density_in_sample"])
    r2 = r2_score(y, df["predicted_density_in_sample"])

    logger.info(f"in sample MAE: {mae:.4f}")
    logger.info(f"in sample R2: {r2:.4f}")

    return model, df


def score_out_of_fold(df: pd.DataFrame) -> pd.DataFrame:
    """
    Predict each state from folds it was held out of, and residual against that.

    With 51 rows an in sample fit partly interpolates, so a state's own
    influence on the coefficients leaks into its residual and then into its
    risk tier. Predicting each state from a model it did not help fit removes
    that leak. These are the columns the risk classification reads.

    Parameters
    df : pd.DataFrame with the feature columns and the target.

    Returns
    pd.DataFrame with predicted_provider_density and residual added.
    """
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    df["predicted_provider_density"] = cross_val_predict(
        LinearRegression(), X, y, cv=CV_SPLITTER
    )
    df["residual"] = y - df["predicted_provider_density"]

    mae = mean_absolute_error(y, df["predicted_provider_density"])
    r2 = r2_score(y, df["predicted_provider_density"])

    logger.info(f"out of fold MAE: {mae:.4f}")
    logger.info(f"out of fold R2: {r2:.4f}")
    logger.info(f"residual range: [{df['residual'].min():.2f}, {df['residual'].max():.2f}]")

    return df


def save_results(df: pd.DataFrame) -> None:
    """Save regression outputs so the risk classification stage can read them."""
    save_csv(df, OUTPUT_FILE, logger)


def run_regression_model() -> pd.DataFrame:
    """full regression workflow: load, validate, fit, score, save."""
    try:
        df = load_model_data()
        _, results = fit_regression(df)
        results = score_out_of_fold(results)
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