"""
Small reusable Dash widgets shared across the state and county views.

These are the tiles you see at the top of each dashboard view (kpi_card)
and the detail strip that appears below the map when a state is selected
(state_detail_card). Pulling them out keeps the layout file focused on
arrangement instead of presentation.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

from vis._styles import CARD_STYLE, COLORS, RISK_TIER_COLORS


def kpi_card(
    title: str,
    value: str,
    *,
    subtitle: str = "",
    color: str = COLORS["text"],
    accent: str = COLORS["card_border"],
) -> dbc.Card:
    """
    Build a single KPI tile with a colored top accent bar.

    Parameters
    title : str
        Small uppercase label above the value (e.g. "States Analyzed").
    value : str
        The big number or word to display.
    subtitle : str
        Optional smaller caption below the value.
    color : str
        Color of the value text. Use kpi_bad to flag concerning numbers.
    accent : str
        Color of the thin top border. Picks up the risk tier or accent palette.

    Returns
    dbc.Card laid out as a centered tile.
    """
    children: list = [
        html.P(title, className="mb-1", style={
            "fontSize": "0.85rem", "color": COLORS["text_muted"],
            "fontWeight": "600", "textTransform": "uppercase",
            "letterSpacing": "0.05em",
        }),
        html.H2(value, className="mb-0", style={
            "fontSize": "2.2rem", "fontWeight": "700", "color": color,
        }),
    ]

    if subtitle:
        children.append(html.P(subtitle, className="mb-0 mt-1", style={
            "fontSize": "0.8rem", "color": COLORS["text_muted"],
        }))

    return dbc.Card(
        dbc.CardBody(children),
        style={**CARD_STYLE, "textAlign": "center", "borderTop": f"4px solid {accent}"},
    )


def state_detail_card(row: pd.Series) -> dbc.Card:
    """
    Build the detail strip shown when a user clicks a state on the map.

    Shows the state name, the assigned risk tier as a colored pill, and
    five or six headline metrics (provider count, density, metro pop, gap,
    predicted density, and demand adjusted density when available).

    Parameters
    row : pd.Series
        One row from the regression results frame.

    Returns
    dbc.Card with a colored left border that matches the risk tier.
    """
    name = row.get("state_name", row["practice_state"])
    tier = str(row["risk_tier"])
    tier_color = RISK_TIER_COLORS.get(tier, COLORS["text"])

    metrics: list[tuple[str, str]] = [
        ("Providers", f"{int(row['provider_count']):,}"),
        ("Providers / 100k", f"{row['providers_per_100k']:.2f}"),
        ("Metro Population", f"{int(row['metro_population']):,}"),
        ("Access Gap", f"{row['residual']:.2f}"),
        ("Predicted Density", f"{row['predicted_provider_density']:.2f}"),
    ]

    # the demand adjusted density is only available when build_demand_features
    # ran successfully, so add it conditionally to keep the card from breaking
    if "providers_per_100k_demand" in row.index and pd.notna(row.get("providers_per_100k_demand")):
        metrics.append(("Providers / 100k (demand)", f"{row['providers_per_100k_demand']:.2f}"))

    metric_cols = [
        dbc.Col(html.Div([
            html.P(label, className="mb-0", style={
                "fontSize": "0.75rem", "color": COLORS["text_muted"],
                "textTransform": "uppercase", "fontWeight": "600",
            }),
            html.P(value, className="mb-0", style={
                "fontSize": "1.3rem", "fontWeight": "700", "color": COLORS["text"],
            }),
        ], style={"textAlign": "center"}), md=2)
        for label, value in metrics
    ]

    return dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col(html.Div([
                html.H5(name, className="mb-1", style={"fontWeight": "700"}),
                html.Span(tier, style={
                    "fontSize": "0.85rem", "fontWeight": "600",
                    "color": "white", "backgroundColor": tier_color,
                    "padding": "3px 12px", "borderRadius": "12px",
                }),
            ]), md=2),
            *metric_cols,
        ], className="align-items-center"),
    ]), style={**CARD_STYLE, "borderLeft": f"5px solid {tier_color}"})
