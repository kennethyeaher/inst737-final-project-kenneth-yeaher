"""Application factory and preserved state diagnostics for the Ovara dashboard."""

from __future__ import annotations

import logging as _logging
import os

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Dash, Input, Output, ctx, dcc, html

from vis._components import kpi_card, state_detail_card
from vis._styles import CARD_STYLE, CHART_CONFIG, COLORS
from vis.findings_card import state_findings_card
from vis.state_charts import build_bar, build_choropleth, build_scatter, national_density


def _state_kpi_row(state_df: pd.DataFrame) -> dbc.Row:
    """Build the four KPI tiles that sit above the state level charts."""
    n_states = int(state_df["practice_state"].nunique())
    total_providers = int(state_df["provider_count"].sum())
    national = national_density(state_df)
    med_dens = state_df["providers_per_100k"].median()

    thinnest_row = state_df.nsmallest(1, "providers_per_100k").iloc[0]
    thinnest_name = thinnest_row.get("state_name", thinnest_row["practice_state"])
    below_national = int((state_df["providers_per_100k"] < national).sum())

    return dbc.Row([
    dbc.Col(kpi_card(
        "States Analyzed",
        str(n_states),
        subtitle=f"{total_providers:,} total providers",
        accent=COLORS["pos_strong"],
    ), md=3),
    dbc.Col(kpi_card(
        "National Providers / 100k",
        f"{national:.2f}",
        subtitle=f"Median state: {med_dens:.2f}",
        accent=COLORS["accent"],
    ), md=3),
    dbc.Col(kpi_card(
        "Thinnest State",
        thinnest_name,
        subtitle=f"{thinnest_row['providers_per_100k']:.1f} per 100k",
        color=COLORS["kpi_bad"],
        accent=COLORS["neg_mid"],
        style="serif",
    ), md=3),
    dbc.Col(kpi_card(
        "Below the National Rate",
        f"{below_national}",
        subtitle=f"of {n_states} states",
        accent=COLORS["accent"],
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

        # main state choropleth, a continuous density scale with no tiers
        dbc.Row(dbc.Col(dbc.Card(
            dcc.Graph(id="choropleth", figure=build_choropleth(state_df), config=CHART_CONFIG),
            style=CARD_STYLE,
        ), width=12), className="mb-3"),

        # state detail panel appears after a user clicks a state
        dbc.Row(dbc.Col(html.Div(id="state-detail-panel"), width=12), className="mb-3"),

        # findings card gives the map a clearer written takeaway before the rest of the page
        dbc.Row(dbc.Col(state_findings_card(state_df), width=12)),
    ])


def _register_state_callbacks(app: Dash, state_df: pd.DataFrame) -> None:
    """Wire up the state level interactivity (map, bar chart, detail panel)."""

    @app.callback(
        Output("choropleth", "figure"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def update_map(click_data, _n_clicks):
        """Redraw the state map when a state is clicked or the filter is reset."""
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return build_choropleth(state_df)
        state = click_data["points"][0]["location"]
        return build_choropleth(state_df, selected_state=state)

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



def create_dashboard(state_df: pd.DataFrame | None = None) -> Dash:
    """Create the Iris atlas app without exporting files or launching a server.

    The data snapshot is shared read only. County selection, filters and
    comparison remain in each browser's memory stores.
    """
    from pathlib import Path

    from vis.atlas_callbacks import register_atlas_callbacks
    from vis.atlas_map import CountyAtlas
    from vis.atlas_model import load_atlas_data, state_names
    from vis.atlas_view import build_atlas_layout
    from vis.state_charts import load_state_density_ranking

    if state_df is None:
        state_df = load_state_density_ranking()

    def refresh():
        """Reload county files safely and represent failures as unavailable data."""
        try:
            frame, geometry = load_atlas_data()
            return {"frame": frame, "atlas": CountyAtlas(frame, geometry), "error": None}
        except (OSError, ValueError, KeyError, TypeError) as error:
            _logging.getLogger(__name__).warning("County snapshot unavailable: %s", error)
            return {"frame": None, "atlas": None, "error": str(error)}

    snapshot = refresh()
    frame = snapshot["frame"]
    names = state_names(frame) if frame is not None else dict(
        zip(state_df["practice_state"], state_df.get("state_name", state_df["practice_state"]))
    )
    options = [{"label": name, "value": code} for code, name in sorted(names.items(), key=lambda pair: pair[1])]
    default = "29037" if frame is not None and "29037" in set(frame["county_fips"]) else None
    app = Dash(
        __name__, assets_folder=str(Path(__file__).parent / "assets"),
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Ovara · Reproductive health provider access", update_title="Updating county view…",
    )
    app.index_string = """<!DOCTYPE html>
<html lang="en">
<head>
{%metas%}<title>{%title%}</title>{%favicon%}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
{%css%}
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""
    app.layout = build_atlas_layout(_state_view(state_df), options, default)
    register_atlas_callbacks(app, snapshot, refresh)
    _register_state_callbacks(app, state_df)
    return app


def run_dashboard(state_df, *, debug=False, logger=None) -> None:
    """Launch the dashboard using the supplied state snapshot and DASH_PORT."""
    port = int(os.environ.get("DASH_PORT", 8050))
    if logger is not None:
        logger.info("Dashboard running at http://127.0.0.1:%s", port)
    _logging.getLogger("werkzeug").setLevel(_logging.ERROR)
    create_dashboard(state_df).run(debug=debug, port=port)


if __name__ == "__main__":
    from vis.state_charts import load_state_density_ranking

    run_dashboard(load_state_density_ranking())
