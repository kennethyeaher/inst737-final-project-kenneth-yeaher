from __future__ import annotations

import json
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import html

from vis._brand import COUNTY_TIER_COLORS
from vis._components import county_detail_card as _county_detail_card
from vis._components import kpi_card
from vis._styles import (
    CHART_TITLE_FONT,
    COLORS,
    FONT_STACK,
    apply_axis_defaults,
)

# main file paths for county dashboard data
GEOJSON_FILE = Path("data/reference_tables/counties_geojson.json")
COUNTY_RISK_FILE = Path("data/model_outputs/county_risk_classified.csv")

# county tier setup ordered from worst access to strongest access
TIER_COLORS = COUNTY_TIER_COLORS
TIER_ORDER = ["access_desert", "critical", "underserved", "adequate", "well_served"]

TIER_LABELS = {
    "access_desert": "Access Desert",
    "critical": "Critical",
    "underserved": "Underserved",
    "adequate": "Adequate",
    "well_served": "Well Served",
}

# mapbox view settings used when the user filters down to one state
STATE_VIEW_PARAMS: dict[str, dict] = {
    "AL": {"center": {"lat": 32.8, "lon": -86.8}, "zoom": 5.5},
    "AK": {"center": {"lat": 64.2, "lon": -153.4}, "zoom": 3.5},
    "AZ": {"center": {"lat": 34.3, "lon": -111.1}, "zoom": 5.5},
    "AR": {"center": {"lat": 34.8, "lon": -92.2}, "zoom": 5.5},
    "CA": {"center": {"lat": 37.3, "lon": -119.7}, "zoom": 4.8},
    "CO": {"center": {"lat": 39.0, "lon": -105.5}, "zoom": 5.5},
    "CT": {"center": {"lat": 41.6, "lon": -72.7}, "zoom": 7.5},
    "DC": {"center": {"lat": 38.9, "lon": -77.0}, "zoom": 10.0},
    "DE": {"center": {"lat": 38.9, "lon": -75.5}, "zoom": 7.5},
    "FL": {"center": {"lat": 27.8, "lon": -83.7}, "zoom": 5.5},
    "GA": {"center": {"lat": 32.6, "lon": -83.4}, "zoom": 5.5},
    "HI": {"center": {"lat": 20.3, "lon": -156.4}, "zoom": 5.5},
    "ID": {"center": {"lat": 44.5, "lon": -114.6}, "zoom": 5.0},
    "IL": {"center": {"lat": 40.0, "lon": -89.2}, "zoom": 5.5},
    "IN": {"center": {"lat": 40.0, "lon": -86.1}, "zoom": 6.0},
    "IA": {"center": {"lat": 42.1, "lon": -93.5}, "zoom": 5.5},
    "KS": {"center": {"lat": 38.5, "lon": -98.4}, "zoom": 5.5},
    "KY": {"center": {"lat": 37.5, "lon": -85.3}, "zoom": 5.8},
    "LA": {"center": {"lat": 31.0, "lon": -91.8}, "zoom": 5.8},
    "ME": {"center": {"lat": 45.2, "lon": -69.0}, "zoom": 5.8},
    "MD": {"center": {"lat": 39.0, "lon": -76.8}, "zoom": 6.5},
    "MA": {"center": {"lat": 42.3, "lon": -71.8}, "zoom": 7.0},
    "MI": {"center": {"lat": 44.3, "lon": -85.4}, "zoom": 5.5},
    "MN": {"center": {"lat": 46.4, "lon": -93.1}, "zoom": 5.0},
    "MS": {"center": {"lat": 32.7, "lon": -89.7}, "zoom": 5.8},
    "MO": {"center": {"lat": 38.5, "lon": -92.4}, "zoom": 5.5},
    "MT": {"center": {"lat": 46.9, "lon": -110.4}, "zoom": 5.0},
    "NE": {"center": {"lat": 41.5, "lon": -99.9}, "zoom": 5.5},
    "NV": {"center": {"lat": 38.5, "lon": -117.1}, "zoom": 5.0},
    "NH": {"center": {"lat": 43.7, "lon": -71.6}, "zoom": 6.5},
    "NJ": {"center": {"lat": 40.1, "lon": -74.4}, "zoom": 7.0},
    "NM": {"center": {"lat": 34.4, "lon": -106.1}, "zoom": 5.5},
    "NY": {"center": {"lat": 42.9, "lon": -75.6}, "zoom": 5.8},
    "NC": {"center": {"lat": 35.5, "lon": -79.4}, "zoom": 5.8},
    "ND": {"center": {"lat": 47.5, "lon": -100.5}, "zoom": 5.5},
    "OH": {"center": {"lat": 40.4, "lon": -82.8}, "zoom": 6.0},
    "OK": {"center": {"lat": 35.5, "lon": -97.5}, "zoom": 5.8},
    "OR": {"center": {"lat": 44.0, "lon": -120.5}, "zoom": 5.5},
    "PA": {"center": {"lat": 40.9, "lon": -77.8}, "zoom": 6.0},
    "RI": {"center": {"lat": 41.7, "lon": -71.5}, "zoom": 8.5},
    "SC": {"center": {"lat": 33.8, "lon": -80.9}, "zoom": 6.0},
    "SD": {"center": {"lat": 44.4, "lon": -100.2}, "zoom": 5.5},
    "TN": {"center": {"lat": 35.9, "lon": -86.4}, "zoom": 5.8},
    "TX": {"center": {"lat": 31.5, "lon": -99.3}, "zoom": 4.8},
    "UT": {"center": {"lat": 39.4, "lon": -111.1}, "zoom": 5.5},
    "VT": {"center": {"lat": 44.1, "lon": -72.7}, "zoom": 6.5},
    "VA": {"center": {"lat": 37.5, "lon": -79.4}, "zoom": 5.8},
    "WA": {"center": {"lat": 47.4, "lon": -120.4}, "zoom": 5.5},
    "WV": {"center": {"lat": 38.6, "lon": -80.6}, "zoom": 6.0},
    "WI": {"center": {"lat": 44.6, "lon": -89.8}, "zoom": 5.5},
    "WY": {"center": {"lat": 43.0, "lon": -107.5}, "zoom": 5.5},
}

_geojson_cache: dict | None = None


def load_geojson() -> dict:
    """load county boundaries once so the dashboard does not keep rereading the same file."""
    global _geojson_cache

    if _geojson_cache is None:
        with open(GEOJSON_FILE) as f:
            _geojson_cache = json.load(f)

    return _geojson_cache


def load_county_risk_data() -> pd.DataFrame:
    """load county risk data and keep FIPS codes as strings so leading zeros do not get dropped."""
    return pd.read_csv(COUNTY_RISK_FILE, dtype={"county_fips": str, "state_fips": str})


def build_county_choropleth(
    df: pd.DataFrame,
    geojson: dict,
    selected_county: str | None = None,
    state_filter: str | None = None,
) -> go.Figure:
    """
    Build a county level map that users can zoom and pan.

    Selection is shown through county borders because mapbox choropleth opacity
    only works for the full trace, not each county separately.
    """
    plot_df = df.copy()

    if state_filter:
        plot_df = plot_df[plot_df["practice_state"] == state_filter]

    tier_to_num = {tier: i for i, tier in enumerate(TIER_ORDER)}
    plot_df["tier_num"] = plot_df["risk_tier"].map(tier_to_num)

    # build hard color bands so each tier keeps a solid color
    colorscale: list[list] = []
    for i, tier in enumerate(TIER_ORDER):
        lo = i / len(TIER_ORDER)
        hi = (i + 1) / len(TIER_ORDER)
        colorscale.append([lo, TIER_COLORS[tier]])

        edge = 1.0 if i == len(TIER_ORDER) - 1 else hi - 0.001
        colorscale.append([edge, TIER_COLORS[tier]])

    n = len(plot_df)

    # highlight selected county with a stronger border without hiding the rest of the map
    if selected_county:
        line_widths = [3.0 if f == selected_county else 0.3 for f in plot_df["county_fips"]]
        line_colors = ["#000" if f == selected_county else "#ccc" for f in plot_df["county_fips"]]
    else:
        line_widths = [0.3] * n
        line_colors = ["#ccc"] * n

    hover_text = [
        f"<b>{row['county_name']}</b><br>"
        f"Providers: {int(row['provider_count'])}<br>"
        f"Density: {row['providers_per_100k']:.1f} / 100k<br>"
        f"Tier: {TIER_LABELS.get(row['risk_tier'], row['risk_tier'])}<br>"
        f"Population: {int(row['total_population']):,}"
        for _, row in plot_df.iterrows()
    ]

    # snap the map to a state when the user filters, otherwise center on the contiguous 
    # US at a zoom that fills the available width
    if state_filter and state_filter in STATE_VIEW_PARAMS:
        map_center = STATE_VIEW_PARAMS[state_filter]["center"]
        map_zoom = STATE_VIEW_PARAMS[state_filter]["zoom"]
    else:
        map_center = {"lat": 39.5, "lon": -98.0}
        map_zoom = 3.6

    title = "County Level Reproductive Health Access"
    if state_filter:
        title = f"County Access for {state_filter}"

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=plot_df["county_fips"],
        z=plot_df["tier_num"],
        featureidkey="id",
        colorscale=colorscale,
        zmin=0,
        zmax=len(TIER_ORDER),
        marker={
            "line": {"color": line_colors, "width": line_widths},
            "opacity": 0.85,
        },
        colorbar={
            "title": "Risk Tier",
            "thickness": 14,
            "len": 0.75,
            "tickvals": [i + 0.5 for i in range(len(TIER_ORDER))],
            "ticktext": [TIER_LABELS[tier] for tier in TIER_ORDER],
            "tickfont": {"size": 10},
            "title_font": {"size": 12},
        },
        text=hover_text,
        hovertemplate="%{text}<extra></extra>",
    ))

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=map_zoom,
        mapbox_center=map_center,
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        height=560,
        font={"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
        title={"text": title, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        paper_bgcolor="rgba(0,0,0,0)",
    )

    return fig


def build_county_bar(
    df: pd.DataFrame,
    state_filter: str | None = None,
    top_n: int = 15,
) -> go.Figure:
    """
    Build the bar chart for the most underserved counties that still have providers.

    Counties with zero providers are excluded from this chart because they all have
    density 0.0, which makes the bar chart hard to read. They are still shown in
    the Access Deserts KPI card, and the title says how many were excluded.
    """
    base = df[df["total_population"] > 0].copy()

    if state_filter:
        base = base[base["practice_state"] == state_filter]

    n_deserts = int((base["provider_count"] == 0).sum())
    plot_df = base[base["provider_count"] > 0].copy()

    layout_base = dict(
        template="plotly_white",
        margin={"l": 10, "r": 20, "t": 60, "b": 40},
        height=420,
        font={"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # show a clean empty state when every county in the filter has zero providers
    if len(plot_df) == 0:
        msg = (
            f"All populated counties in {state_filter} are Access Deserts"
            if state_filter else "No counties with providers found"
        )

        fig = go.Figure()
        fig.update_layout(**layout_base, title={
            "text": msg, "font": CHART_TITLE_FONT,
            "x": 0.02, "xanchor": "left",
        })
        apply_axis_defaults(fig)
        return fig

    show_n = min(top_n, len(plot_df))
    worst = plot_df.nsmallest(show_n, "providers_per_100k").sort_values("providers_per_100k")

    short_names = worst["county_name"].str.replace(r",.*", "", regex=True)
    bar_colors = [TIER_COLORS.get(tier, "#999") for tier in worst["risk_tier"]]

    desert_note = f" ({n_deserts} access desert counties excluded)" if n_deserts > 0 else ""

    if state_filter:
        title = f"Most Underserved for {state_filter}{desert_note}"
    else:
        title = f"Top {show_n} Most Underserved Counties{desert_note}"

    x_max = max(worst["providers_per_100k"].max() * 1.4, 1.0)

    fig = go.Figure(go.Bar(
        x=worst["providers_per_100k"],
        y=short_names,
        orientation="h",
        text=worst["providers_per_100k"].round(1),
        textposition="outside",
        textfont={"size": 11, "color": COLORS["text"]},
        marker={"color": bar_colors},
        hovertemplate="<b>%{y}</b><br>Density: %{x:.1f} / 100k<extra></extra>",
    ))

    fig.update_layout(
        **layout_base,
        title={"text": title, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        xaxis={"title": "Providers per 100k", "range": [0, x_max]},
        yaxis={"title": ""},
    )
    apply_axis_defaults(fig)

    return fig


def county_kpi_cards(df: pd.DataFrame, state_filter: str | None = None) -> list:
    """
    Build the four KPI cards for the county view.

    Uses the same kpi_card component as the state view so both views keep the
    same typography, spacing, and accent rules. When a state is selected, the
    cards update to show only that state's counties.
    """
    scope = df[df["practice_state"] == state_filter] if state_filter else df

    n_counties = len(scope)
    n_desert = int((scope["provider_count"] == 0).sum())
    pop_desert = int(scope[scope["provider_count"] == 0]["total_population"].sum())

    populated = scope[scope["total_population"] > 0]
    med_density = populated["providers_per_100k"].median() if len(populated) > 0 else 0.0

    # match the bar chart logic so the KPI and chart agree on most underserved
    # access deserts already have their own card, so this shows the worst county with at least one provider
    worst_pool = scope[(scope["total_population"] > 1000) & (scope["provider_count"] > 0)]
    worst = worst_pool.nsmallest(1, "providers_per_100k")
    worst_name = (
        worst["county_name"].str.replace(r",.*", "", regex=True).iloc[0]
        if len(worst) > 0 else "N/A"
    )

    counties_label = "Counties in State" if state_filter else "Counties Analyzed"

    return [
        dbc.Col(kpi_card(
            counties_label,
            f"{n_counties:,}",
            accent=TIER_COLORS["well_served"],
        ), md=3),
        dbc.Col(kpi_card(
            "Access Deserts",
            f"{n_desert:,}",
            subtitle=f"{pop_desert:,} residents affected",
            color=COLORS["kpi_bad"],
            accent=TIER_COLORS["access_desert"],
        ), md=3),
        dbc.Col(kpi_card(
            "Median Density",
            f"{med_density:.1f}",
            subtitle="providers per 100k",
            accent=COLORS["accent"],
        ), md=3),
        dbc.Col(kpi_card(
            "Most Underserved",
            worst_name,
            color=COLORS["kpi_bad"],
            accent=TIER_COLORS["critical"],
            style="serif",
        ), md=3),
    ]


def county_detail_card(row: pd.Series) -> dbc.Card:
    """
    Small wrapper around the shared county detail card.

    County tier labels and colors live in this file, so this function resolves
    them first and then sends the row to the shared layout component.
    """
    tier = str(row["risk_tier"])
    tier_color = TIER_COLORS.get(tier, COLORS["text"])
    tier_label = TIER_LABELS.get(tier, tier)

    return _county_detail_card(row, tier_color=tier_color, tier_label=tier_label)


