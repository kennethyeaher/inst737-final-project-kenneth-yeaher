import pandas as pd
import requests
from pathlib import Path
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_demand_features")

# file path

OUTPUT_FILE = Path("data/reference_tables/acs_female_25_44_by_state.csv")

# census acs api endpoint

ACS_URL = "https://api.census.gov/data/2024/acs/acs1"

# b01001 female age variables for 25-44

FEMALE_AGE_VARS = {
    "B01001_035E": "female_25_29",
    "B01001_036E": "female_30_34",
    "B01001_037E": "female_35_39",
    "B01001_038E": "female_40_44",
}

# census fips to state abbreviation

FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


def fetch_from_census() -> pd.DataFrame:
    """pull female 25-44 population by state from Census ACS B01001."""
    var_codes = ",".join(FEMALE_AGE_VARS.keys())
    url = f"{ACS_URL}?get=NAME,{var_codes}&for=state:*"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    logger.info(f"fetched {len(data) - 1} rows from Census ACS API")
    return pd.DataFrame(data[1:], columns=data[0])


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """reshape Census API response into state-level demand features."""
    df = df.rename(columns=FEMALE_AGE_VARS)

    age_cols = list(FEMALE_AGE_VARS.values())
    for col in age_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["female_25_44_pop"] = df[age_cols].sum(axis=1)
    df["practice_state"] = df["state"].map(FIPS_TO_STATE)
    df = df.dropna(subset=["practice_state"])

    logger.info(f"states with demand data: {df.shape[0]}")
    return df[["practice_state"] + age_cols + ["female_25_44_pop"]].copy()


def build_demand_features(refresh: bool = False) -> pd.DataFrame:
    """
    Build fertility-age demand features by state.
    Uses cached file if available unless refresh is True.
    """
    try:
        if OUTPUT_FILE.exists() and not refresh:
            logger.info(f"loading cached -> {OUTPUT_FILE}")
            return pd.read_csv(OUTPUT_FILE)

        logger.info("fetching from Census ACS API...")
        raw = fetch_from_census()
        demand = transform(raw)

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        demand.to_csv(OUTPUT_FILE, index=False)

        logger.info(f"saved -> {OUTPUT_FILE} ({demand.shape[0]} states)")
        return demand

    except requests.RequestException as e:
        logger.error(f"census API request failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building demand features: {e}")
        raise


if __name__ == "__main__":
    build_demand_features(refresh=True)