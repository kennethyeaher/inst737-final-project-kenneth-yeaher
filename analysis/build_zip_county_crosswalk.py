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

# vendored by etl/build_ct_planning_region_crosswalk.py from CTData Collaborative
CT_CROSSWALK_FILE = Path("data/reference_tables/ct_zip_planning_region.csv")

CT_STATE_FIPS = "09"


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


def apply_connecticut_planning_regions(lookup: pd.DataFrame) -> pd.DataFrame:
    """
    Re point Connecticut ZIPs from legacy counties onto the nine planning regions.

    The Census relationship file is still on the 2020 county vintage, so it
    hands Connecticut the eight legacy county codes 09001 through 09015. County
    population comes from the 2022 ACS, where the nine planning regions are the
    county equivalent, so the two vintages share no codes and every Connecticut
    provider is lost at the population join. This swaps in the planning region
    code from the vendored CTData crosswalk before that join happens.

    Parameters
    lookup : pd.DataFrame
        The national ZIP to county lookup, one row per ZCTA.

    Returns
    pd.DataFrame with the same shape minus any Connecticut ZIP that the CTData
    crosswalk does not cover, since a legacy code would only be dropped later.
    """
    ct_crosswalk = pd.read_csv(CT_CROSSWALK_FILE, dtype={"county_fips": str})
    planning_region_by_zip = dict(zip(ct_crosswalk["zip5"], ct_crosswalk["county_fips"]))

    lookup = lookup.copy()
    is_ct = lookup["state_fips"] == CT_STATE_FIPS
    reassigned = lookup.loc[is_ct, "zip5"].map(planning_region_by_zip)

    unmatched = int(reassigned.isna().sum())
    if unmatched > 0:
        logger.warning(
            f"CT ZIPs with no planning region match, dropped from the lookup: {unmatched}"
        )

    lookup.loc[is_ct, "county_fips"] = reassigned

    # a Connecticut ZIP the CTData file does not cover keeps no usable code,
    # so drop it rather than leave a legacy county behind
    lookup = lookup.dropna(subset=["county_fips"])

    # recompute state FIPS from the new code so the two columns stay consistent
    lookup["state_fips"] = lookup["county_fips"].str[:2]

    ct_codes = set(lookup.loc[lookup["state_fips"] == CT_STATE_FIPS, "county_fips"])
    assert len(ct_codes) == 9, (
        f"expected 9 CT planning regions, found {len(ct_codes)}: {sorted(ct_codes)}"
    )
    assert all(code.startswith("091") for code in ct_codes), (
        f"non planning region CT codes: {sorted(ct_codes)}"
    )

    logger.info(f"CT ZIPs reassigned to planning regions: {int(is_ct.sum()) - unmatched:,}")
    return lookup.reset_index(drop=True)


def build_zip_county_crosswalk(refresh: bool = False) -> pd.DataFrame:
    """Run the full ZCTA to county lookup workflow and save the output."""
    try:
        raw = fetch_zcta_crosswalk(refresh=refresh)
        lookup = build_largest_share_lookup(raw)
        lookup = apply_connecticut_planning_regions(lookup)
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