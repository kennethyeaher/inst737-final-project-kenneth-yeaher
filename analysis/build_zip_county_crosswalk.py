from __future__ import annotations
from io import StringIO
from pathlib import Path
import pandas as pd
import requests
from utils.cache import load_or_fetch
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_zip_county_crosswalk")

ZCTA_COUNTY_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
    "tab20_zcta520_county20_natl.txt"
)

FETCH_TIMEOUT = 60

# main file paths for the ZCTA to county lookup
CACHE_FILE = Path("data/reference_tables/zcta_county_crosswalk.csv")
OUTPUT_FILE = Path("data/reference_tables/zip_county_lookup.csv")


def _download_crosswalk() -> pd.DataFrame:
    """Pull the Census ZCTA to county crosswalk text file and parse it as a DataFrame."""
    logger.info("fetching ZCTA county crosswalk from Census...")
    resp = requests.get(ZCTA_COUNTY_URL, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), sep="|", dtype=str)


def fetch_zcta_crosswalk(refresh: bool = False) -> pd.DataFrame:
    """Return the cached Census crosswalk if present, otherwise download and cache it."""
    return load_or_fetch(
        CACHE_FILE,
        fetcher=_download_crosswalk,
        refresh=refresh,
        logger=logger,
        read_kwargs={"dtype": str},
    )


def build_largest_share_lookup(raw: pd.DataFrame) -> pd.DataFrame:
    """map each ZCTA to the county that contains its largest land area share."""
    raw = raw.copy()

    # find the needed columns by name so small Census column naming changes do not break the script
    zcta_col = [col for col in raw.columns if "ZCTA" in col.upper() and "GEOID" in col.upper()]
    county_col = [col for col in raw.columns if "COUNTY" in col.upper() and "GEOID" in col.upper()]
    area_col = [col for col in raw.columns if "AREALAND" in col.upper() and "PART" in col.upper()]

    if not zcta_col or not county_col or not area_col:
        logger.warning(f"unexpected columns: {list(raw.columns)}")
        raise ValueError("cannot identify ZCTA, county, or area columns in crosswalk")

    zcta_col, county_col, area_col = zcta_col[0], county_col[0], area_col[0]

    # convert land area to numeric so idxmax can safely pick the largest county share
    raw[area_col] = pd.to_numeric(raw[area_col], errors="coerce").fillna(0)

    idx = raw.groupby(zcta_col)[area_col].idxmax()
    lookup = raw.loc[idx, [zcta_col, county_col]].copy()

    lookup = lookup.rename(columns={zcta_col: "zcta5", county_col: "county_fips"})

    # keep county FIPS as five digits because leading zeros matter
    lookup["county_fips"] = lookup["county_fips"].str.zfill(5)
    lookup["zip5"] = lookup["zcta5"].astype(int)
    lookup["state_fips"] = lookup["county_fips"].str[:2]

    lookup = lookup[["zip5", "county_fips", "state_fips"]].reset_index(drop=True)

    logger.info(f"unique ZCTAs mapped: {len(lookup):,}")
    return lookup


def build_zip_county_crosswalk(refresh: bool = False) -> pd.DataFrame:
    """Run the full ZCTA to county lookup workflow and save the output."""
    try:
        raw = fetch_zcta_crosswalk(refresh=refresh)
        lookup = build_largest_share_lookup(raw)
        save_csv(lookup, OUTPUT_FILE, logger)
        return lookup

    except requests.exceptions.RequestException as e:
        logger.error(f"crosswalk fetch failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building crosswalk: {e}")
        raise


if __name__ == "__main__":
    build_zip_county_crosswalk()