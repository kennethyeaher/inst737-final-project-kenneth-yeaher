"""
Small reusable Dash widgets shared across the state and county views.

These are the tiles at the top of each dashboard view and the detail strip
that appears below the map when a state or county is selected. Pulling them
out keeps the layout file focused on structure instead of presentation.

Typography follows the Ovara brand system:
- eyebrow labels use JetBrains Mono with letter spacing
- numeric values use JetBrains Mono so digits feel more data focused
- state and county names use Fraunces for more editorial weight
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

from vis._brand import FONT_HEADING, FONT_MONO
from vis._styles import CARD_STYLE, COLORS, RISK_TIER_COLORS

# typography presets used by KPI cards and detail strips
_EYEBROW_STYLE: dict = {
    "fontFamily": FONT_MONO,
    "fontSize": "9px",
    "letterSpacing": "0.14em",
    "textTransform": "uppercase",
    "color": COLORS["text_muted"],
    "marginBottom": "10px",
    "fontWeight": "500",
}

_KPI_NUMERIC_STYLE: dict = {
    "fontFamily": FONT_MONO,
    "fontSize": "40px",
    "fontWeight": "500",
    "lineHeight": "1",
    "marginBottom": "8px",
}

_KPI_SERIF_STYLE: dict = {
    "fontFamily": FONT_HEADING,
    "fontSize": "28px",
    "fontWeight": "900",
    "lineHeight": "1.05",
    "letterSpacing": "-0.01em",
    "marginBottom": "8px",
}

_KPI_SUBTITLE_STYLE: dict = {
    "fontFamily": FONT_MONO,
    "fontSize": "10px",
    "color": COLORS["text_muted"],
    "marginBottom": "0",
}


def kpi_card(
    title: str,
    value: str,
    *,
    subtitle: str = "",
    color: str = COLORS["text"],
    accent: str = COLORS["card_border"],
    style: str = "numeric",
) -> dbc.Card:
    """
    Build a single KPI tile with a colored top accent bar.

    title: small uppercase label above the value.
    value: main number or word displayed in the card.
    subtitle: optional caption below the value.
    color: value text color.
    accent: thin top border color.
    style: numeric uses JetBrains Mono, while serif uses Fraunces for names.
    """
    value_style = {
        **(_KPI_NUMERIC_STYLE if style == "numeric" else _KPI_SERIF_STYLE),
        "color": color,
    }

    children: list = [
        html.Div(title, style=_EYEBROW_STYLE),
        html.Div(value, style=value_style),
    ]

    if subtitle:
        children.append(html.Div(subtitle, style=_KPI_SUBTITLE_STYLE))

    return dbc.Card(
        dbc.CardBody(children, style={"padding": "20px 24px 18px"}),
        style={
            **CARD_STYLE,
            "borderTop": f"3px solid {accent}",
            "position": "relative",
            "overflow": "hidden",
        },
    )


def state_detail_card(row: pd.Series) -> dbc.Card:
    """
    Build the detail strip shown when a user clicks a state on the map.

    The card shows the state name, the assigned risk tier, and a row of key
    metrics. Demand adjusted density is included only when that column exists.
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

    # demand adjusted density only appears if the demand feature stage ran successfully
    if "providers_per_100k_demand" in row.index and pd.notna(row.get("providers_per_100k_demand")):
        metrics.append(("Providers / 100k (demand)", f"{row['providers_per_100k_demand']:.2f}"))

    return _detail_card(name, tier, tier_color, metrics)


def county_detail_card(row: pd.Series, tier_color: str, tier_label: str) -> dbc.Card:
    """
    Build the detail strip shown when a user clicks a county on the map.

    This uses the same layout as the state detail card, but with county metrics.
    County tier color and label are passed in because that tier setup lives in
    vis/county_visualizations.py.
    """
    metrics: list[tuple[str, str]] = [
        ("Providers", f"{int(row['provider_count']):,}"),
        ("Density / 100k", f"{row['providers_per_100k']:.1f}"),
        ("Population", f"{int(row['total_population']):,}"),
        ("Specialties", f"{int(row.get('unique_taxonomies', 0))}"),
        ("Recent Growth", f"{int(row.get('recent_provider_growth', 0))}"),
    ]

    return _detail_card(row["county_name"], tier_label, tier_color, metrics)


def _detail_card(
    name: str,
    tier_label: str,
    tier_color: str,
    metrics: list[tuple[str, str]],
) -> dbc.Card:
    """
    Shared layout for state and county detail strips.

    The name uses Fraunces, the tier appears as a colored pill, and the metrics
    fill the rest of the row in a clean monospace grid.
    """
    name_block = html.Div(
        [
            html.Div(name, style={
                "fontFamily": FONT_HEADING,
                "fontSize": "18px",
                "fontWeight": "700",
                "color": COLORS["text"],
                "marginBottom": "6px",
                "lineHeight": "1.2",
            }),
            html.Span(tier_label, style={
                "fontFamily": FONT_MONO,
                "fontSize": "9px",
                "fontWeight": "600",
                "letterSpacing": "0.1em",
                "textTransform": "uppercase",
                "color": COLORS["text"],
                "backgroundColor": tier_color,
                "padding": "3px 10px",
                "borderRadius": "4px",
            }),
        ],
    )

    metric_cols = [
        dbc.Col(
            html.Div([
                html.Div(label, style=_EYEBROW_STYLE),
                html.Div(value, style={
                    "fontFamily": FONT_MONO,
                    "fontSize": "20px",
                    "fontWeight": "500",
                    "color": COLORS["text"],
                    "lineHeight": "1",
                }),
            ], style={"textAlign": "center"}),
            md=True,
        )
        for label, value in metrics
    ]

    return dbc.Card(
        dbc.CardBody(
            dbc.Row(
                [dbc.Col(name_block, md=2), *metric_cols],
                className="align-items-center g-3",
            ),
            style={"padding": "20px 24px"},
        ),
        style={**CARD_STYLE, "borderLeft": f"4px solid {tier_color}"},
    )