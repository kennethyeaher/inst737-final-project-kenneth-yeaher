"""
Dash dashboard assembly.

This module pulls the chart builders, summary prose, and styling tokens
together into a runnable interactive dashboard. The build is split into
three pieces:

- _build_layout            assembles the full app.layout tree
- _register_callbacks      wires up every interactivity callback
- run_dashboard            boots the app

Splitting layout from callbacks makes each piece much easier to read
than the original single 350 line function.
"""

from __future__ import annotations

import logging as _logging
import os
from typing import Any

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, Patch, ctx, dcc, html

from vis._components import kpi_card, state_detail_card
from vis._styles import (
    CARD_STYLE,
    CHART_CONFIG,
    COLORS,
    COUNTY_MAP_CONFIG,
    FONT_STACK,
    SUMMARY_CARD_STYLE,
)
from vis.state_charts import build_bar, build_choropleth, build_scatter
from vis.summary_text import generate_state_summary


# small bundle so callbacks have all the data they need without globals
class _CountyBundle:
    """Lightweight container for the optional county data."""

    def __init__(
        self,
        df: pd.DataFrame | None,
        geojson: dict | None,
        available: bool,
    ):
        self.df = df
        self.geojson = geojson
        self.available = available


def _try_load_county_data(logger: _logging.Logger | None) -> _CountyBundle:
    """
    Try to load the county risk classified data and the county geojson.

    The state dashboard runs fine without these, so a missing file is
    logged as a warning rather than an error.

    Returns
    _CountyBundle with available=True only when both files loaded cleanly.
    """
    # imports happen here so the dashboard module loads even if the
    # county helper module is broken
    from vis.county_visualizations import load_county_risk_data, load_geojson

    try:
        df = load_county_risk_data()
        geojson = load_geojson()
        if logger is not None:
            logger.info(f"county data loaded: {len(df):,} counties")
        return _CountyBundle(df=df, geojson=geojson, available=True)

    except FileNotFoundError:
        if logger is not None:
            logger.warning("county data not available, county view disabled")
        return _CountyBundle(df=None, geojson=None, available=False)


def _state_kpi_row(state_df: pd.DataFrame) -> dbc.Row:
    """Build the four KPI tiles that sit above the state level charts."""
    n_states = int(state_df["practice_state"].nunique())
    total_providers = int(state_df["provider_count"].sum())
    avg_dens = state_df["providers_per_100k"].mean()
    med_dens = state_df["providers_per_100k"].median()
    worst_row = state_df.nsmallest(1, "residual").iloc[0]
    worst_name = worst_row.get("state_name", worst_row["practice_state"])
    n_critical = int((state_df["risk_tier"] == "Critical").sum())
    n_at_risk = int((state_df["risk_tier"] == "At Risk").sum())

    return dbc.Row([
        dbc.Col(kpi_card(
            "States Analyzed", str(n_states),
            subtitle=f"{total_providers:,} total providers",
            accent=COLORS["pos_strong"],
        ), md=3),
        dbc.Col(kpi_card(
            "Avg Providers / 100k", f"{avg_dens:.2f}",
            subtitle=f"Median: {med_dens:.2f}",
            accent=COLORS["accent"],
        ), md=3),
        dbc.Col(kpi_card(
            "Critical + At Risk", f"{n_critical + n_at_risk}",
            subtitle=f"{n_critical} critical, {n_at_risk} at risk",
            color=COLORS["kpi_bad"], accent=COLORS["kpi_bad"],
        ), md=3),
        dbc.Col(kpi_card(
            "Most Underserved", worst_name,
            subtitle=f"Gap: {worst_row['residual']:.2f}",
            color=COLORS["kpi_bad"], accent=COLORS["neg_mid"],
        ), md=3),
    ], className="g-3 mb-3")


def _state_view(state_df: pd.DataFrame) -> html.Div:
    """Build the full state level dashboard view (KPIs, charts, map, summary)."""
    return html.Div(id="state-view", children=[
        _state_kpi_row(state_df),

        # bar plus scatter row
        dbc.Row([
            dbc.Col(dbc.Card([
                dcc.Graph(id="bar-chart", figure=build_bar(state_df), config=CHART_CONFIG),
                html.Div(
                    dbc.Button("Reset filter", id="reset-bar", size="sm",
                               color="secondary", outline=True),
                    style={"textAlign": "right", "padding": "6px 12px 10px 0"},
                ),
            ], style=CARD_STYLE), md=5),
            dbc.Col(dbc.Card(
                dcc.Graph(id="scatter-chart", figure=build_scatter(state_df), config=CHART_CONFIG),
                style=CARD_STYLE,
            ), md=7),
        ], className="g-3 mb-3"),

        # toggle between continuous gap and discrete tier views
        dbc.Row(dbc.Col(html.Div(
            dcc.RadioItems(
                id="map-view-toggle",
                options=[
                    {"label": " Access Gap", "value": "gap"},
                    {"label": " Risk Tier", "value": "tier"},
                ],
                value="gap",
                inline=True,
                inputStyle={"marginRight": "6px"},
                labelStyle={
                    "marginRight": "24px", "fontSize": "0.9rem",
                    "cursor": "pointer", "color": COLORS["text"],
                },
            ),
            style={"textAlign": "center", "padding": "6px 0"},
        ), width=12)),

        # the choropleth itself
        dbc.Row(dbc.Col(dbc.Card(
            dcc.Graph(id="choropleth", figure=build_choropleth(state_df), config=CHART_CONFIG),
            style=CARD_STYLE,
        ), width=12), className="mb-3"),

        # detail panel that fills in when a state is clicked
        dbc.Row(dbc.Col(html.Div(id="state-detail-panel"), width=12), className="mb-3"),

        # written summary panel
        dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Executive Summary", style={
                "fontWeight": "700", "textTransform": "uppercase",
                "letterSpacing": "0.05em", "color": COLORS["text_muted"],
                "fontSize": "0.8rem",
            }),
            html.Div(generate_state_summary(state_df), style={
                "fontSize": "0.95rem", "lineHeight": "1.7",
                "color": COLORS["text"], "marginBottom": "0",
            }),
        ]), style=SUMMARY_CARD_STYLE), width=12), className="mb-4"),
    ])


def _county_view(county: _CountyBundle) -> html.Div:
    """Build the county level dashboard view, or an empty container if county data is missing."""
    # imports here so this file does not require county_visualizations
    # to import successfully when county data is absent
    from vis.county_visualizations import (
        build_county_bar,
        build_county_choropleth,
        county_kpi_cards,
        generate_county_summary,
    )

    return html.Div(id="county-view", style={"display": "none"}, children=[
        dbc.Row(
            county_kpi_cards(county.df) if county.available else [],
            id="county-kpi-row",
            className="g-3 mb-3",
        ),

        # bar chart on the left, written county summary on the right
        dbc.Row([
            dbc.Col(dbc.Card([
                dcc.Graph(
                    id="county-bar-chart",
                    figure=build_county_bar(county.df) if county.available else go.Figure(),
                    config=CHART_CONFIG,
                ),
                html.Div(
                    dbc.Button("Reset", id="county-reset", size="sm",
                               color="secondary", outline=True),
                    style={"textAlign": "right", "padding": "6px 12px 10px 0"},
                ),
            ], style=CARD_STYLE), md=5),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("County Analysis", style={
                    "fontWeight": "700", "textTransform": "uppercase",
                    "letterSpacing": "0.05em", "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                }),
                html.Div(
                    generate_county_summary(county.df) if county.available else [],
                    id="county-summary-text",
                    style={
                        "fontSize": "0.95rem", "lineHeight": "1.7",
                        "color": COLORS["text"], "marginBottom": "0",
                    },
                ),
            ]), style=SUMMARY_CARD_STYLE), md=7),
        ], className="g-3 mb-3"),

        # the county map (scroll zoom enabled in COUNTY_MAP_CONFIG)
        dbc.Row(dbc.Col(dbc.Card(
            dcc.Loading(
                dcc.Graph(
                    id="county-choropleth",
                    figure=build_county_choropleth(county.df, county.geojson)
                    if county.available else go.Figure(),
                    config=COUNTY_MAP_CONFIG,
                ),
                type="circle",
            ),
            style=CARD_STYLE,
        ), width=12), className="mb-3"),

        dbc.Row(dbc.Col(html.Div(id="county-detail-panel"), width=12), className="mb-3"),
    ])


def _header() -> dbc.Row:
    """The dashboard title and subtitle row at the top of the page."""
    return dbc.Row(dbc.Col(html.Div([
        html.H3(
            "Reproductive Health Provider Access Dashboard",
            className="mb-2",
            style={
                "fontWeight": "700",
                "color": COLORS["text"],
                "letterSpacing": "-0.01em",
            },
        ),
        html.P(
            "Residuals highlight where reproductive health provider supply "
            "falls below or exceeds model expectations. Click a state on the "
            "map to filter the bar chart. Toggle between access gap and risk "
            "tier views.",
            className="mb-0",
            style={
                "color": COLORS["text_muted"],
                "fontSize": "0.9rem",
                "maxWidth": "780px",
                "margin": "0 auto",
            },
        ),
    ], style={"textAlign": "center", "padding": "24px 0 14px 0"}), width=12))


def _geo_toggle_row(county: _CountyBundle) -> dbc.Row:
    """Geographic level toggle plus the optional state filter dropdown."""
    level_options = [{"label": " State Level", "value": "state"}]
    if county.available:
        level_options.append({"label": " County Level", "value": "county"})

    state_options: list = []
    if county.available:
        state_options = [{"label": s, "value": s} for s in sorted(county.df["practice_state"].unique())]

    return dbc.Row([
        dbc.Col(html.Div(
            dcc.RadioItems(
                id="geo-level-toggle",
                options=level_options,
                value="state",
                inline=True,
                inputStyle={"marginRight": "6px"},
                labelStyle={
                    "marginRight": "24px", "fontSize": "0.95rem",
                    "cursor": "pointer", "color": COLORS["text"],
                    "fontWeight": "600",
                },
            ),
            style={"textAlign": "center"},
        ), md=8),
        dbc.Col(html.Div(
            dcc.Dropdown(
                id="county-state-filter",
                options=state_options,
                value=None,
                placeholder="All states",
                clearable=True,
                style={"fontSize": "0.9rem"},
            ),
            id="county-state-filter-wrap",
            style={"display": "none"},
        ), md=4),
    ], className="align-items-center mb-3")


def _build_layout(state_df: pd.DataFrame, county: _CountyBundle) -> dbc.Container:
    """Compose the full app.layout from the header, toggle, and two view sections."""
    return dbc.Container([
        _header(),
        html.Hr(style={"margin": "0 0 16px 0", "borderColor": COLORS["card_border"]}),
        _geo_toggle_row(county),
        _state_view(state_df),
        _county_view(county),
    ], fluid=True, style={
        "backgroundColor": COLORS["bg"],
        "fontFamily": FONT_STACK,
        "maxWidth": "1440px",
        "paddingBottom": "40px",
    })


def _register_state_callbacks(app: Dash, state_df: pd.DataFrame) -> None:
    """Wire up the state level interactivity (map, bar chart, detail panel)."""

    @app.callback(
        Output("choropleth", "figure"),
        Input("map-view-toggle", "value"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def update_map(view_mode, click_data, _n_clicks):
        """Redraw the state map when the view mode changes or a state is clicked."""
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return build_choropleth(state_df, view_mode=view_mode)
        state = click_data["points"][0]["location"]
        return build_choropleth(state_df, selected_state=state, view_mode=view_mode)

    @app.callback(
        Output("bar-chart", "figure"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def update_bar(click_data, _n_clicks):
        """Filter the bar chart to the clicked state, or reset to the top ten view."""
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return build_bar(state_df)
        return build_bar(state_df, selected_states=[click_data["points"][0]["location"]])

    @app.callback(
        Output("state-detail-panel", "children"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def update_detail(click_data, _n_clicks):
        """Show the selected state's metrics card below the map."""
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return None
        state = click_data["points"][0]["location"]
        match = state_df[state_df["practice_state"] == state]
        if len(match) == 0:
            return None
        return state_detail_card(match.iloc[0])


def _register_county_callbacks(app: Dash, county: _CountyBundle) -> None:
    """Wire up the county level interactivity (state filter, county click, detail panel)."""
    from vis.county_visualizations import (
        build_county_bar,
        build_county_choropleth,
        county_detail_card,
    )

    @app.callback(
        Output("county-choropleth", "figure"),
        Input("county-state-filter", "value"),
        Input("county-choropleth", "clickData"),
        Input("county-reset", "n_clicks"),
    )
    def update_county_map(state_filter, click_data, _n_clicks):
        """
        Update the county map.

        State filter change or reset triggers a full rebuild because the
        polygon set changes. A county click only patches the marker
        borders, which keeps the map from re rendering all 3,144 polygons.
        """
        triggered = ctx.triggered_id

        if triggered == "county-choropleth" and click_data is not None:
            fips = click_data["points"][0]["location"]
            sub = county.df.copy()
            if state_filter:
                sub = sub[sub["practice_state"] == state_filter]

            line_widths = [3.0 if f == fips else 0.3 for f in sub["county_fips"]]
            line_colors = ["#000" if f == fips else "#ccc" for f in sub["county_fips"]]

            patched = Patch()
            patched["data"][0]["marker"]["line"]["width"] = line_widths
            patched["data"][0]["marker"]["line"]["color"] = line_colors
            return patched

        return build_county_choropleth(county.df, county.geojson, state_filter=state_filter)

    @app.callback(
        Output("county-bar-chart", "figure"),
        Input("county-state-filter", "value"),
        Input("county-reset", "n_clicks"),
    )
    def update_county_bar(state_filter, _n_clicks):
        """Filter the most underserved bar chart to the selected state, or reset."""
        if ctx.triggered_id == "county-reset":
            return build_county_bar(county.df)
        return build_county_bar(county.df, state_filter=state_filter)

    @app.callback(
        Output("county-detail-panel", "children"),
        Input("county-choropleth", "clickData"),
        Input("county-reset", "n_clicks"),
    )
    def update_county_detail(click_data, _n_clicks):
        """Show the clicked county's metrics card below the map."""
        if ctx.triggered_id == "county-reset" or click_data is None:
            return None
        fips = click_data["points"][0]["location"]
        match = county.df[county.df["county_fips"] == fips]
        if len(match) == 0:
            return None
        return county_detail_card(match.iloc[0])


def _register_view_toggle(app: Dash) -> None:
    """Wire up the State vs County toggle that swaps which view is visible."""

    @app.callback(
        Output("state-view", "style"),
        Output("county-view", "style"),
        Output("county-state-filter-wrap", "style"),
        Input("geo-level-toggle", "value"),
    )
    def toggle_view(level):
        """Show either the state or county dashboard based on the radio button."""
        if level == "county":
            return {"display": "none"}, {"display": "block"}, {"display": "block"}
        return {"display": "block"}, {"display": "none"}, {"display": "none"}


def run_dashboard(
    state_df: pd.DataFrame,
    *,
    debug: bool = False,
    logger: _logging.Logger | None = None,
) -> None:
    """
    Build and launch the Dash dashboard at http://127.0.0.1:DASH_PORT.

    Parameters
    state_df : pd.DataFrame
        Regression results frame with risk tiers already assigned.
    debug : bool
        Pass through to Dash's run() method.
    logger : logging.Logger or None
        Optional logger for the boot messages.

    Returns
    None (the call blocks while the server runs).
    """
    if logger is not None:
        logger.info("launching interactive Dash dashboard...")

    county = _try_load_county_data(logger)

    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Ovara: A Reproductive Health Access Dashboard",
    )

    # set the page background at the body level so the dashboard surface extends to the edges of the viewport instead of bleeding to default white
    app.index_string = f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,700;0,9..144,900;1,9..144,400;1,9..144,700;1,9..144,900&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        {{%css%}}
        <style>
            html, body {{
                background-color: {COLORS["bg"]};
                margin: 0;
                padding: 0;
                min-height: 100vh;
            }}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
"""

    app.layout = _build_layout(state_df, county)

    _register_view_toggle(app)
    _register_state_callbacks(app, state_df)
    if county.available:
        _register_county_callbacks(app, county)

    # silence per request access logs so the terminal stays readable
    _logging.getLogger("werkzeug").setLevel(_logging.ERROR)

    port = int(os.environ.get("DASH_PORT", 8050))
    if logger is not None:
        logger.info(f"dashboard running at http://127.0.0.1:{port}")
    app.run(debug=debug, port=port)
