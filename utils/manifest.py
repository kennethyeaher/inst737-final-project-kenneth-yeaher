"""
Run manifest for the data vintages behind each pipeline output.

Nothing in the repo used to record which Census year, which NPPES release, or
which HRSA download produced a given set of numbers. That is what let the ZIP
to county crosswalk sit on the 2020 county vintage while county population
moved to 2022, dropping every Connecticut provider without a warning. This
module writes those vintages next to the model outputs after every run.

Every field is optional. A missing file or an unreadable constant logs a
warning and records null rather than failing the pipeline.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from utils.io import save_json
from utils.logging_config import setup_logger

logger = setup_logger("ovara.manifest")

# main output path for the run manifest
OUTPUT_FILE = Path("data/model_outputs/run_manifest.json")

# packages whose versions change model output and so belong in the manifest
TRACKED_PACKAGES = ["pandas", "numpy", "scikit-learn"]


def _describe_file(path: Path | None) -> dict[str, Any] | None:
    """Return a file's name, byte size, and modification time, or None if it is missing."""
    if path is None or not path.exists():
        logger.warning(f"manifest could not find file: {path}")
        return None

    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _year_from_url(url: str) -> int | None:
    """Pull the four digit vintage year out of a Census API url."""
    match = re.search(r"/(\d{4})/", url)
    return int(match.group(1)) if match else None


def _git_commit() -> str | None:
    """Return the current git commit sha, or None outside a git checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"manifest could not read git commit: {e}")
        return None


def _package_versions() -> dict[str, str | None]:
    """Return installed versions for the packages whose behavior affects results."""
    versions: dict[str, str | None] = {}

    for package in TRACKED_PACKAGES:
        try:
            versions[package] = metadata.version(package)

        except metadata.PackageNotFoundError:
            logger.warning(f"manifest could not read version for {package}")
            versions[package] = None

    return versions


def _nppes_source_file() -> Path | None:
    """Locate the NPPES file the extract stage actually reads, or None if it is gone."""
    from etl.extract import find_provider_file

    try:
        return find_provider_file()

    except FileNotFoundError as e:
        logger.warning(f"manifest could not find the NPPES source file: {e}")
        return None


def _zcta_vintage(url: str) -> int | None:
    """Pull the relationship file vintage out of the Census rel folder name."""
    match = re.search(r"/rel(\d{4})/", url)
    return int(match.group(1)) if match else None


def write_run_manifest() -> dict[str, Any]:
    """
    Collect the data vintages behind the current outputs and save them as json.

    Sources are read from the module constants the stages themselves use, so
    the manifest cannot drift from the pipeline the way a hardcoded copy would.

    Returns
    dict, the manifest as written.
    """
    from analysis.build_county_population import ACS_URL as COUNTY_POPULATION_ACS_URL
    from analysis.build_demand_features import ACS_URL as DEMAND_ACS_URL
    from analysis.build_metro_dataset import CBSA_COUNTY_FILE, CBSA_POP_FILE
    from analysis.build_zip_county_crosswalk import CT_CROSSWALK_FILE, ZCTA_COUNTY_URL
    from analysis.hrsa_validation import HRSA_CACHE_FILE
    from etl.build_ct_planning_region_crosswalk import SOURCE_URL as CT_CROSSWALK_URL

    manifest = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "package_versions": _package_versions(),
        "nppes_source_file": _describe_file(_nppes_source_file()),
        "acs_year_county_population": _year_from_url(COUNTY_POPULATION_ACS_URL),
        "acs_year_demand_features": _year_from_url(DEMAND_ACS_URL),
        "cbsa_delineation_file": _describe_file(CBSA_COUNTY_FILE),
        "cbsa_population_file": _describe_file(CBSA_POP_FILE),
        "zcta_relationship_file_vintage": _zcta_vintage(ZCTA_COUNTY_URL),
        "ct_planning_region_crosswalk": {
            "source_url": CT_CROSSWALK_URL,
            "licence": "MIT, CTData Collaborative",
            "vendored": _describe_file(CT_CROSSWALK_FILE),
        },
        "hrsa_cache_file": _describe_file(HRSA_CACHE_FILE),
    }

    save_json(manifest, OUTPUT_FILE, logger)
    return manifest


if __name__ == "__main__":
    write_run_manifest()
