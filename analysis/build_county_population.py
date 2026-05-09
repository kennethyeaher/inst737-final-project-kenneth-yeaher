from __future__ import annotations
from pathlib import Path
import pandas as pd
import requests
from utils.cache import load_or_fetch
from utils.fips import FIPS_TO_STATE
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_county_population")

# main output path for county population reference data
OUTPUT_FILE = Path("data/reference_tables/county_population.csv")

# ACS 5 year is used because it covers all counties, unlike ACS 1 year
ACS_URL = "https://api.census.gov/data/2022/acs/acs5"


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
    """
    Build or load the county population reference table.

    Uses the cached csv unless refresh is True. FIPS columns are read back
    as strings so leading zeros survive the round trip.

    Returns
    pd.DataFrame with county_fips, county_name, state_fips, practice_state,
    and total_population columns.
    """
    try:
        return load_or_fetch(
            OUTPUT_FILE,
            fetcher=lambda: transform_county_population(fetch_county_population()),
            refresh=refresh,
            logger=logger,
            read_kwargs={"dtype": {"county_fips": str, "state_fips": str}},
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Census ACS API request failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building county population: {e}")
        raise


if __name__ == "__main__":
    build_county_population(refresh=True)