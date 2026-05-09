import pandas as pd
import requests
from pathlib import Path
from utils.cache import load_or_fetch
from utils.fips import FIPS_TO_STATE
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_demand_features")

# file path
OUTPUT_FILE = Path("data/reference_tables/acs_female_25_44_by_state.csv")

# census acs api endpoint
ACS_URL = "https://api.census.gov/data/2024/acs/acs1"

# b01001 female age variables for ages 25 to 44 (the fertility window we model)
FEMALE_AGE_VARS = {
    "B01001_035E": "female_25_29",
    "B01001_036E": "female_30_34",
    "B01001_037E": "female_35_39",
    "B01001_038E": "female_40_44",
}


def fetch_from_census() -> pd.DataFrame:
    """Pull female 25-44 population by state from Census ACS B01001."""
    var_codes = ",".join(FEMALE_AGE_VARS.keys())
    url = f"{ACS_URL}?get=NAME,{var_codes}&for=state:*"
 
    response = requests.get(url, timeout=30)
    response.raise_for_status()
 
    data = response.json()
    return pd.DataFrame(data[1:], columns=data[0])


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Reshape Census API response into state level demand features."""
    df = df.rename(columns=FEMALE_AGE_VARS)
 
    age_cols = list(FEMALE_AGE_VARS.values())
    for col in age_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
 
    df["female_25_44_pop"] = df[age_cols].sum(axis=1)
    df["practice_state"] = df["state"].map(FIPS_TO_STATE)
    df = df.dropna(subset=["practice_state"])
 
    return df[["practice_state"] + age_cols + ["female_25_44_pop"]].copy()


def build_demand_features(refresh: bool = False) -> pd.DataFrame:
    """
    Build fertility age demand features by state.

    Uses the cached csv if it exists unless refresh is True. On a cache miss
    pulls fresh data from the Census ACS API and reshapes it into one row
    per state.

    Parameters
    refresh : bool
        Force a fresh API pull even if the cached file is present.

    Returns
    pd.DataFrame with practice_state, the four age band columns, and
    female_25_44_pop totals.
    """
    try:
        logger.info("building demand side features...")
        return load_or_fetch(
            OUTPUT_FILE,
            fetcher=lambda: transform(fetch_from_census()),
            refresh=refresh,
            logger=logger,
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Census ACS API request failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building demand features: {e}")
        raise


if __name__ == "__main__":
    build_demand_features(refresh=True)