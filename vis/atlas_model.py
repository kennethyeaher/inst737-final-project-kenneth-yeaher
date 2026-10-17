"""County scope, selection and comparison rules for the Iris atlas interface."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from vis.county_visualizations import TIER_LABELS, TIER_ORDER

ROOT = Path(__file__).resolve().parents[1]
COUNTY_FILE = ROOT / "data/model_outputs/county_risk_classified.csv"
GEOMETRY_FILE = ROOT / "data/reference_tables/counties_geojson.json"


def load_atlas_data() -> tuple[pd.DataFrame, dict]:
    """Load a validated snapshot without changing pipeline files.

    Raises OSError, ValueError or JSONDecodeError when the source cannot support
    the interface. Missing records must never become zero provider counties.
    """
    frame = pd.read_csv(COUNTY_FILE, dtype={"county_fips": str, "practice_state": str})
    required = {"county_fips", "county_name", "practice_state", "provider_count",
                "total_population", "providers_per_100k", "risk_tier"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"County dataset is missing columns: {sorted(missing)}")
    if frame.empty or frame[list(required)].isna().any().any():
        raise ValueError("County dataset is empty or contains missing required values")
    if frame["county_fips"].duplicated().any():
        raise ValueError("County dataset contains duplicate FIPS codes")
    if not frame["county_fips"].str.fullmatch(r"\d{5}").all():
        raise ValueError("County FIPS codes must contain five digits")
    for column in ["provider_count", "total_population", "providers_per_100k"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if (frame["provider_count"] < 0).any() or (frame["total_population"] <= 0).any():
        raise ValueError("County counts or population are invalid")
    if not frame["risk_tier"].isin(TIER_ORDER).all():
        raise ValueError("County dataset contains an unknown tier")
    with GEOMETRY_FILE.open() as handle:
        geometry = json.load(handle)
    geometry_ids = {str(feature["id"]) for feature in geometry["features"]}
    if not set(frame["county_fips"]).issubset(geometry_ids):
        raise ValueError("County boundaries do not cover the dataset geography")
    return frame, geometry


def county_scope(frame: pd.DataFrame, scope: dict | None) -> pd.DataFrame:
    """Return records matching an applied state and tier without mutating input."""
    scope = scope or {}
    result = frame
    if scope.get("state"):
        result = result[result["practice_state"] == scope["state"]]
    if scope.get("tier"):
        result = result[result["risk_tier"] == scope["tier"]]
    return result


def search_counties(frame: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """Match literal county names, state abbreviations and FIPS codes.

    With no query, list the lowest density counties that have providers.
    Search results include zero provider counties and use deterministic ordering.
    """
    query = (query or "").strip()
    if query:
        names = frame["county_name"].str.contains(query, case=False, regex=False)
        states = frame["practice_state"].str.casefold() == query.casefold()
        fips = frame["county_fips"].str.startswith(query)
        return frame[names | states | fips].sort_values(["county_name", "county_fips"])
    return frame[frame["provider_count"] > 0].sort_values(
        ["providers_per_100k", "county_fips"]
    )


def county_summary(frame: pd.DataFrame) -> dict:
    """Count zero supply and its population in exactly the supplied scope."""
    deserts = frame[frame["provider_count"] == 0]
    return {
        "counties": len(frame),
        "deserts": len(deserts),
        "residents": int(deserts["total_population"].sum()),
        "share": len(deserts) / len(frame) * 100 if len(frame) else 0,
    }


def comparison_selection(
    frame: pd.DataFrame, selection: list | None, county: str | None
) -> tuple[list[str], str]:
    """Add one valid county to a maximum of two distinct comparison records."""
    known = set(frame["county_fips"])
    selected = list(dict.fromkeys(fips for fips in (selection or []) if fips in known))[:2]
    if county not in known:
        return selected, "Select a county before adding it to comparison."
    if county in selected:
        return selected, "This county is already saved for comparison."
    if len(selected) == 2:
        return selected, "Two counties are saved. Remove one before adding another."
    selected.append(county)
    return selected, f"{len(selected)} of 2 counties saved for comparison."


def comparison_rows(frame: pd.DataFrame, selection: list | None) -> list[pd.Series]:
    """Resolve valid distinct comparison records in the user's chosen order."""
    clean, _ = comparison_selection(frame, selection, None)
    indexed = frame.set_index("county_fips", drop=False)
    return [indexed.loc[fips] for fips in clean]


def tier_label(tier: str) -> str:
    """Return a consistent sentence case label for a known access tier."""
    return TIER_LABELS.get(tier, tier).capitalize()


def state_names(frame: pd.DataFrame) -> dict[str, str]:
    """Derive state labels from county names without another external lookup."""
    return {
        str(row.practice_state): str(row.county_name).rsplit(", ", 1)[-1]
        for row in frame.itertuples()
    }
