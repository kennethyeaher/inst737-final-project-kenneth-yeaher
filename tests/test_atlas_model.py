"""Behavioral checks for county scope, comparison and dynamic map geography."""

import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from vis.atlas_map import CountyAtlas
from vis.atlas_model import (
    comparison_rows, comparison_selection, county_scope, county_summary,
    load_atlas_data, search_counties,
)


@pytest.fixture(scope="module")
def snapshot():
    """Use the supplied project snapshot rather than invented county totals."""
    return load_atlas_data()


def test_national_count_and_denominator(snapshot):
    """Keep the corrected national finding and population together."""
    frame, _ = snapshot
    result = county_summary(frame)
    assert (result["counties"], result["deserts"], result["residents"]) == (
        3144, 1029, 10917875
    )


def test_missouri_scope_updates_every_total(snapshot):
    """Filter before computing summaries so national totals cannot leak into state views."""
    frame, _ = snapshot
    result = county_summary(county_scope(frame, {"state": "MO"}))
    assert (result["counties"], result["deserts"], result["residents"]) == (115, 48, 614052)


def test_tier_and_state_filters_compose(snapshot):
    """Only Missouri counties with zero registered providers match this scope."""
    frame, _ = snapshot
    result = county_scope(frame, {"state": "MO", "tier": "access_desert"})
    assert len(result) == 48
    assert (result["provider_count"] == 0).all()


@pytest.mark.parametrize("query, expected", [
    ("29037", "29037"), ("Cass County, Missouri", "29037"),
    ("Livingston Parish", "22063"), ("Starr County", "48427"),
])
def test_search_resolves_real_counties(snapshot, query, expected):
    """Names and FIPS support exact selection without clicking a map."""
    frame, _ = snapshot
    assert expected in set(search_counties(frame, query)["county_fips"])


@pytest.mark.parametrize("query", ["[", ".*", "<script>", "zzzzz"])
def test_search_is_literal_and_handles_no_matches(snapshot, query):
    """Regex and markup are ordinary search text, never executable patterns."""
    frame, _ = snapshot
    assert search_counties(frame, query).empty


def test_comparison_rejects_duplicates_third_county_and_unknown_ids(snapshot):
    """Comparison contains at most two distinct known records."""
    frame, _ = snapshot
    first, _ = comparison_selection(frame, [], "29037")
    duplicate, _ = comparison_selection(frame, first, "29037")
    second, _ = comparison_selection(frame, duplicate, "22063")
    third, _ = comparison_selection(frame, second, "48427")
    unknown, _ = comparison_selection(frame, third, "00000")
    assert first == duplicate == ["29037"]
    assert second == third == unknown == ["29037", "22063"]


def test_comparison_preserves_selection_order_and_denominators(snapshot):
    """Each comparison rate remains paired with its own count and population."""
    frame, _ = snapshot
    rows = comparison_rows(frame, ["22063", "29037"])
    assert [row["county_fips"] for row in rows] == ["22063", "29037"]
    for row in rows:
        assert row["providers_per_100k"] == pytest.approx(
            row["provider_count"] / row["total_population"] * 100000, abs=0.0001
        )


def test_empty_scope_is_empty_without_fabricated_records(snapshot):
    """An empty result remains distinguishable from a real zero supply county."""
    frame, _ = snapshot
    result = county_scope(frame, {"state": "ZZ"})
    assert result.empty
    assert county_summary(result)["counties"] == 0


def test_map_joins_all_county_equivalents_and_preserves_fips(snapshot):
    """Local geometry covers the corrected Connecticut units and every county record."""
    frame, geometry = snapshot
    atlas = CountyAtlas(frame, geometry)
    svg = ET.fromstring(atlas.render(frame))
    paths = svg.findall("{http://www.w3.org/2000/svg}path")
    assert len(paths) == 3144
    assert sum(path.attrib["data-fips"].startswith("091") for path in paths) == 9
    assert all(path.attrib["d"] for path in paths)
    assert "https://" not in atlas.render(frame)


def test_state_and_tier_map_only_includes_matching_counties(snapshot):
    """Map paths use the same active scope as the totals and county list."""
    frame, geometry = snapshot
    atlas = CountyAtlas(frame, geometry)
    scoped = county_scope(frame, {"state": "MO", "tier": "access_desert"})
    svg = ET.fromstring(atlas.render(scoped, state="MO"))
    assert len(svg.findall("{http://www.w3.org/2000/svg}path")) == 48


def test_summary_does_not_mutate_input(snapshot):
    """Rendering cannot alter source records used by other browser sessions."""
    frame, _ = snapshot
    before = frame.copy()
    county_summary(county_scope(frame, {"state": "MO"}))
    search_counties(frame, "Cass")
    pd.testing.assert_frame_equal(before, frame)
