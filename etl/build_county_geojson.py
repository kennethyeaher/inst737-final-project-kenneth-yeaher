"""
One time rebuild of the county boundary geojson used by the county choropleth.

The map keys on five digit county FIPS codes, so its boundary file has to be on
the same Census vintage as the county population table. The previous geojson
predated Connecticut's switch from eight counties to nine planning regions,
which left Connecticut as a hole in the map even once the data behind it was
correct. This script rebuilds the file from the Census 2023 cartographic
boundary release, where the planning regions are present.

geopandas is only needed to regenerate this file. The pipeline itself reads the
saved geojson and never imports geopandas.

Run this once when the Census boundary vintage changes:
    python etl/build_county_geojson.py
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd

from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_county_geojson")

# 20m resolution keeps the file small enough for a browser to render smoothly
SOURCE_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip"
)

# main output path for the county boundary file
OUTPUT_FILE = Path("data/reference_tables/counties_geojson.json")

# the choropleth passes featureidkey="id", so GEOID has to land on the feature id
GEOID_COLUMN = "GEOID"

# floor for the sanity check, the modeled universe is 3,144 counties
MIN_COUNTY_FEATURES = 3_000


def download_county_boundaries() -> gpd.GeoDataFrame:
    """Read the Census cartographic boundary shapefile straight from its zip archive."""
    logger.info(f"reading county boundaries from {SOURCE_URL}")
    counties = gpd.read_file(SOURCE_URL)

    # the choropleth expects plain latitude and longitude
    counties = counties.to_crs("EPSG:4326")

    logger.info(f"counties read: {len(counties):,}")
    return counties


def to_geojson_keyed_on_geoid(counties: gpd.GeoDataFrame) -> dict:
    """Convert the boundary frame to a geojson mapping whose feature ids are county FIPS codes."""
    geojson = json.loads(counties.to_json())

    for feature in geojson["features"]:
        feature["id"] = feature["properties"][GEOID_COLUMN]

    return geojson


def validate_geojson(geojson: dict) -> None:
    """Raise unless the new file covers the nine CT planning regions and enough counties overall."""
    feature_ids = {feature["id"] for feature in geojson["features"]}

    ct_regions = sorted(code for code in feature_ids if code.startswith("091"))
    if len(ct_regions) != 9:
        raise ValueError(
            f"expected 9 CT planning region features, found {len(ct_regions)}: {ct_regions}"
        )

    if len(feature_ids) < MIN_COUNTY_FEATURES:
        raise ValueError(
            f"only {len(feature_ids):,} county features, expected at least "
            f"{MIN_COUNTY_FEATURES:,}"
        )

    logger.info(f"validated {len(feature_ids):,} features including CT regions {ct_regions}")


def build_county_geojson() -> dict:
    """Download, convert, validate, and save the county boundary geojson."""
    counties = download_county_boundaries()
    geojson = to_geojson_keyed_on_geoid(counties)

    # validate before writing so a bad download cannot replace a working map
    validate_geojson(geojson)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(geojson, f)

    logger.info(f"saved -> {OUTPUT_FILE}")
    return geojson


if __name__ == "__main__":
    build_county_geojson()
