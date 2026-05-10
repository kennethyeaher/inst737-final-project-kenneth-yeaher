"""
Shared style constants for the Ovara dashboard.

Every chart, card, and layout block reads its colors, fonts, and config
from this module. Keeping the design tokens in one place means visual
tweaks happen in one file instead of being scattered across the dashboard.
"""

from __future__ import annotations

from typing import Final


# core color system used by charts and cards
COLORS: Final[dict[str, str]] = {
    "neg_strong":  "#b2182b",
    "neg_mid":     "#ef8a62",
    "neutral":     "#f7f7f7",
    "pos_mid":     "#67a9cf",
    "pos_strong":  "#2166ac",
    "bg":          "#f8f9fa",
    "card_bg":     "#ffffff",
    "card_border": "#e0e0e0",
    "text":        "#212529",
    "text_muted":  "#6c757d",
    "accent":      "#2ca25f",
    "kpi_bad":     "#c0392b",
    "kpi_good":    "#27ae60",
}


# diverging palette used by access gap maps and the residual scatter
UNIFIED_COLORSCALE: Final[list[list]] = [
    [0.0,  COLORS["neg_strong"]],
    [0.25, COLORS["neg_mid"]],
    [0.5,  COLORS["neutral"]],
    [0.75, COLORS["pos_mid"]],
    [1.0,  COLORS["pos_strong"]],
]


# risk tier labels and colors used by the state level dashboard
RISK_TIERS: Final[list[dict]] = [
    {"label": "Critical",    "color": "#b2182b"},
    {"label": "At Risk",     "color": "#ef8a62"},
    {"label": "Adequate",    "color": "#67a9cf"},
    {"label": "Well Served", "color": "#2166ac"},
]

RISK_TIER_LABELS: Final[list[str]] = [t["label"] for t in RISK_TIERS]
RISK_TIER_COLORS: Final[dict[str, str]] = {t["label"]: t["color"] for t in RISK_TIERS}


# discrete colorscale built so each tier shows up as a solid block on the map
RISK_COLORSCALE: Final[list[list]] = [
    [0.0,  "#b2182b"], [0.249, "#b2182b"],
    [0.25, "#ef8a62"], [0.499, "#ef8a62"],
    [0.5,  "#67a9cf"], [0.749, "#67a9cf"],
    [0.75, "#2166ac"], [1.0,   "#2166ac"],
]


# layout tokens that every chart shares
FONT_STACK: Final[str] = "Inter, Segoe UI, sans-serif"
CHART_HEIGHT: Final[int] = 420

CARD_STYLE: Final[dict] = {
    "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "10px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.06)",
}

BASE_LAYOUT: Final[dict] = {
    "template": "plotly_white",
    "margin": {"l": 10, "r": 20, "t": 50, "b": 40},
    "height": CHART_HEIGHT,
    "font": {"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
}


# dcc.Graph configs
# CHART_CONFIG locks down zoom and pan for the small inline charts where
# zoom would only confuse the reader.
CHART_CONFIG: Final[dict] = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "staticPlot": False,
}

# COUNTY_MAP_CONFIG is the opposite. Scroll zoom is essential for the
# county choropleth because counties are tiny at the national zoom level.
COUNTY_MAP_CONFIG: Final[dict] = {
    "displayModeBar": False,
    "scrollZoom": True,
    "doubleClick": "reset",
    "staticPlot": False,
}
