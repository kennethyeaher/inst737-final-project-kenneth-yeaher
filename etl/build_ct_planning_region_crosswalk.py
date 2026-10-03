"""
One time vendoring of the Connecticut ZIP to planning region crosswalk.

Connecticut replaced its eight legacy counties with nine planning regions as
the county equivalent, and the 2022 ACS is the first vintage to publish
population on the new geography. The Census ZCTA relationship file the rest of
the pipeline uses is still on the 2020 county vintage, so Connecticut ZIPs need
a separate lookup to reach a population row.

CTData Collaborative publishes that lookup under an MIT licence. Their method
was a centroid nearest neighbour spatial join in QGIS against 2022 Census
boundaries, so a ZIP that straddles a planning region boundary is assigned
whole to whichever region its centroid falls in.

Run this once to refresh the vendored csv, which is what the pipeline reads:
    python etl/build_ct_planning_region_crosswalk.py
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

from utils.fips import CT_PLANNING_REGIONS
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_ct_planning_region_crosswalk")

SOURCE_URL = (
    "https://github.com/CT-Data-Collaborative/zip-to-planningregion/raw/main/"
    "ZIP-to-PlanningRegion.xlsx"
)

FETCH_TIMEOUT = 60

# main output path for the vendored Connecticut crosswalk
OUTPUT_FILE = Path("data/reference_tables/ct_zip_planning_region.csv")

# workbook column names as published by CTData
ZCTA_COLUMN = "ZCTA_5"
GEOID_COLUMN = "PlanningRegion_GeoID"
REGION_NAME_COLUMN = "PlanningRegion"


def download_workbook() -> pd.DataFrame:
    """Pull the CTData workbook and parse its single sheet as strings."""
    logger.info(f"fetching CT planning region crosswalk from {SOURCE_URL}")
    resp = requests.get(SOURCE_URL, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()

    raw = pd.read_excel(BytesIO(resp.content), dtype=str)
    logger.info(f"workbook rows: {len(raw):,}, columns: {list(raw.columns)}")
    return raw


def transform_workbook(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Reshape the workbook into a zip5, county_fips, planning_region_name table.

    The workbook stores both the GeoID and the region name, but Excel strips
    the leading zero from each, so the GeoID is padded back to five digits and
    checked against the known nine regions.

    Parameters
    raw : pd.DataFrame
        The workbook sheet as published.

    Returns
    pd.DataFrame with one row per Connecticut ZCTA.
    """
    missing = {ZCTA_COLUMN, GEOID_COLUMN, REGION_NAME_COLUMN} - set(raw.columns)
    if missing:
        raise ValueError(f"CTData workbook is missing expected columns: {sorted(missing)}")

    out = pd.DataFrame(
        {
            "zip5": pd.to_numeric(raw[ZCTA_COLUMN], errors="coerce").astype("Int64"),
            "county_fips": raw[GEOID_COLUMN].str.strip().str.zfill(5),
            "planning_region_name": raw[REGION_NAME_COLUMN].str.strip(),
        }
    )

    out = out.dropna(subset=["zip5"]).drop_duplicates(subset=["zip5"])
    out["zip5"] = out["zip5"].astype(int)

    return out.sort_values("zip5").reset_index(drop=True)


def validate_planning_regions(crosswalk: pd.DataFrame) -> None:
    """Raise if any row carries a planning region code or name we do not recognize."""
    unknown_codes = sorted(set(crosswalk["county_fips"]) - set(CT_PLANNING_REGIONS))
    if unknown_codes:
        raise ValueError(f"unrecognized CT planning region FIPS codes: {unknown_codes}")

    # the workbook ships names alongside the codes, so a disagreement between
    # the two means the source changed shape and the vendored file cannot be trusted
    expected = crosswalk["county_fips"].map(CT_PLANNING_REGIONS)
    mismatched = crosswalk[expected != crosswalk["planning_region_name"]]
    if not mismatched.empty:
        pairs = sorted(set(zip(mismatched["county_fips"], mismatched["planning_region_name"])))
        raise ValueError(f"planning region names do not match their FIPS codes: {pairs}")

    logger.info(f"planning regions covered: {crosswalk['county_fips'].nunique()}")


def build_ct_planning_region_crosswalk() -> pd.DataFrame:
    """Download, reshape, validate, and save the Connecticut ZIP to planning region crosswalk."""
    raw = download_workbook()
    crosswalk = transform_workbook(raw)
    validate_planning_regions(crosswalk)

    save_csv(crosswalk, OUTPUT_FILE, logger)
    logger.info(f"CT ZIPs mapped to planning regions: {len(crosswalk):,}")
    return crosswalk


if __name__ == "__main__":
    build_ct_planning_region_crosswalk()
