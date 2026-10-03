"""
Guards on the county choropleth's map backend.

Plotly's mapbox traces route through Mapbox GL, which stamps an
"API KEY REQUIRED" watermark across the basemap without a token, and the
mapbox subplot is removed entirely in Plotly 7. The county map uses the
MapLibre backed map traces instead, and these tests keep it that way.
"""

import json

import pytest

from vis.county_visualizations import (
    build_county_choropleth,
    load_county_risk_data,
    load_geojson,
)


@pytest.fixture(scope="module")
def county_data():
    return load_county_risk_data()


@pytest.fixture(scope="module")
def county_geojson():
    return load_geojson()


def figure_spec(df, geojson, state_filter=None):
    """Build the choropleth and return its plotly spec as a dict."""
    figure = build_county_choropleth(df, geojson, state_filter=state_filter)
    return json.loads(figure.to_json())


def authored_layout(spec):
    """
    Return the layout keys the code actually set.

    Plotly's default template carries its own scattermapbox entries, so a
    naive substring search over the whole figure always finds "mapbox".
    """
    return {key: value for key, value in spec["layout"].items() if key != "template"}


@pytest.mark.parametrize("state_filter", [None, "CT", "NE"])
def test_county_map_uses_the_maplibre_trace(county_data, county_geojson, state_filter):
    spec = figure_spec(county_data, county_geojson, state_filter)

    assert spec["data"][0]["type"] == "choroplethmap"


@pytest.mark.parametrize("state_filter", [None, "CT", "NE"])
def test_county_map_sets_no_mapbox_keys(county_data, county_geojson, state_filter):
    spec = figure_spec(county_data, county_geojson, state_filter)
    layout = authored_layout(spec)
    blob = json.dumps({"data": spec["data"], "layout": layout}).lower()

    assert "mapbox" not in layout
    assert "mapbox" not in blob


def test_county_map_needs_no_access_token(county_data, county_geojson):
    spec = figure_spec(county_data, county_geojson)

    assert "accesstoken" not in json.dumps(spec).lower()
    assert spec["layout"]["map"]["style"] == "carto-positron"


def test_connecticut_renders_nine_planning_regions(county_data, county_geojson):
    spec = figure_spec(county_data, county_geojson, state_filter="CT")
    locations = sorted(spec["data"][0]["locations"])

    assert len(locations) == 9
    assert all(code.startswith("091") for code in locations)
