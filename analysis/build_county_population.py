from __future__ import annotations
from pathlib import Path
import pandas as pd
import requests
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_county_population")

# main output path for county population reference data
OUTPUT_FILE = Path("data/reference_tables/county_population.csv")

# ACS 5 year is used because it covers all counties, unlike ACS 1 year
ACS_URL = "https://api.census.gov/data/2022/acs/acs5"

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


def fetch_county_population() -> pd.DataFrame:
    """fetch total population for every US county from Census ACS 5 year."""
    url = f"{ACS_URL}?get=NAME,B01003_001E&for=county:*&in=state:*"
    logger.info("fetching county population from Census ACS 5 year...")

    resp = requests.get(url, timeout=45)
    resp.raise_for_status()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])

    logger.info(f"raw county rows from Census: {len(df):,}")
    return df


def transform_county_population(df: pd.DataFrame) -> pd.DataFrame:
    """clean Census API output into a county population reference table."""
    df = df.copy()

    # combine state and county codes into one five digit county FIPS code
    df["county_fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
    df["state_fips"] = df["state"].str.zfill(2)
    df["practice_state"] = df["state_fips"].map(FIPS_TO_STATE)

    # convert Census population field into a numeric column
    df["total_population"] = pd.to_numeric(df["B01003_001E"], errors="coerce")
    df = df.rename(columns={"NAME": "county_name"})

    # keep only valid US counties with usable population values
    df = df.dropna(subset=["practice_state", "total_population"])
    df = df[df["total_population"] > 0]

    out = df[
        ["county_fips", "county_name", "state_fips", "practice_state", "total_population"]
    ].copy()

    out = out.sort_values("county_fips").reset_index(drop=True)

    logger.info(f"counties with population: {len(out):,}")
    return out


def build_county_population(refresh: bool = False) -> pd.DataFrame:
    """build or load the county population reference table."""
    try:
        if OUTPUT_FILE.exists() and not refresh:
            logger.info(f"loading cached -> {OUTPUT_FILE}")
            return pd.read_csv(OUTPUT_FILE, dtype={"county_fips": str, "state_fips": str})

        raw = fetch_county_population()
        pop = transform_county_population(raw)

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pop.to_csv(OUTPUT_FILE, index=False)

        logger.info(f"saved -> {OUTPUT_FILE}")
        return pop

    except requests.exceptions.RequestException as e:
        logger.error(f"Census ACS API request failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building county population: {e}")
        raise


if __name__ == "__main__":
    build_county_population(refresh=True)