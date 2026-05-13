"""
Shared style constants for the Ovara dashboard.

Every chart, card, and layout block pulls colors, fonts, and graph config
from this file. The tokens come from the brand palette in vis/_brand.py so
the dashboard keeps one consistent visual identity.
"""

from __future__ import annotations

from typing import Final

from vis._brand import (
    BRAND,
    FONT_BODY,
    FONT_HEADING,
    FONT_MONO,
    STATE_TIER_COLORS,
    UI,
)

# semantic color tokens used across charts and cards
COLORS: Final[dict[str, str]] = {
    "neg_strong": BRAND["iris_deep"],
    "neg_mid": BRAND["coral"],
    "neutral": BRAND["cream_deep"],
    "pos_mid": BRAND["marigold"],
    "pos_strong": BRAND["sage"],
    "bg": UI["bg"],
    "card_bg": UI["surface"],
    "card_border": UI["border"],
    "text": UI["text"],
    "text_muted": UI["text_muted"],
    "accent": UI["accent"],
    "kpi_bad": UI["bad"],
    "kpi_good": UI["good"],
}

# diverging palette for access gap maps and residual scatter plots
# the center anchor uses the dashboard surface color so zero residual states recede
# under supplied states use coral so they stay visually separate from the dashboard chrome
UNIFIED_COLORSCALE: Final[list[list]] = [
    [0.0, BRAND["coral"]],
    [0.25, BRAND["marigold"]],
    [0.5, UI["surface_alt"]],
    [0.75, "#7FB389"],
    [1.0, BRAND["sage"]],
]

# state level risk tiers ordered from most underserved to best served
RISK_TIERS: Final[list[dict]] = [
    {"label": "Critical", "color": STATE_TIER_COLORS["Critical"]},
    {"label": "At Risk", "color": STATE_TIER_COLORS["At Risk"]},
    {"label": "Adequate", "color": STATE_TIER_COLORS["Adequate"]},
    {"label": "Well Served", "color": STATE_TIER_COLORS["Well Served"]},
]

RISK_TIER_LABELS: Final[list[str]] = [tier["label"] for tier in RISK_TIERS]
RISK_TIER_COLORS: Final[dict[str, str]] = {
    tier["label"]: tier["color"]
    for tier in RISK_TIERS
}

# discrete colorscale so each risk tier renders as one solid map color
RISK_COLORSCALE: Final[list[list]] = [
    [0.0, STATE_TIER_COLORS["Critical"]],
    [0.249, STATE_TIER_COLORS["Critical"]],
    [0.25, STATE_TIER_COLORS["At Risk"]],
    [0.499, STATE_TIER_COLORS["At Risk"]],
    [0.5, STATE_TIER_COLORS["Adequate"]],
    [0.749, STATE_TIER_COLORS["Adequate"]],
    [0.75, STATE_TIER_COLORS["Well Served"]],
    [1.0, STATE_TIER_COLORS["Well Served"]],
]

# layout tokens shared by every chart
FONT_STACK: Final[str] = FONT_BODY
FONT_SERIF: Final[str] = FONT_HEADING
FONT_TECHNICAL: Final[str] = FONT_MONO
CHART_HEIGHT: Final[int] = 420

# typography tokens for Plotly chart elements
# chart titles stay simple, while axis ticks use the mono font so numbers feel more data focused
CHART_TITLE_FONT: Final[dict] = {
    "family": FONT_STACK,
    "size": 13,
    "color": COLORS["text"],
}

CHART_AXIS_TICK_FONT: Final[dict] = {
    "family": FONT_TECHNICAL,
    "size": 10,
    "color": COLORS["text_muted"],
}

CHART_AXIS_TITLE_FONT: Final[dict] = {
    "family": FONT_STACK,
    "size": 11,
    "color": COLORS["text_muted"],
}

CARD_STYLE: Final[dict] = {
    "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "10px",
    "boxShadow": "0 2px 8px rgba(0, 0, 0, 0.25)",
    "backgroundColor": COLORS["card_bg"],
}

# variant card style for the written summary panels.
# uses surface_alt so the summary reads as a distinct block from charts without leaving the dark theme.
SUMMARY_CARD_STYLE: Final[dict] = {
    **CARD_STYLE,
    "backgroundColor": UI["surface_alt"],
    "borderLeft": f"3px solid {COLORS['accent']}",
}

BASE_LAYOUT: Final[dict] = {
    "template": "plotly_white",
    "margin": {"l": 10, "r": 20, "t": 50, "b": 40},
    "height": CHART_HEIGHT,
    "font": {"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
}

# axis defaults get applied after update_layout so chart specific settings still work
AXIS_DEFAULTS: Final[dict] = {
    "tickfont": CHART_AXIS_TICK_FONT,
    "title_font": CHART_AXIS_TITLE_FONT,
    "gridcolor": "rgba(245,239,228,0.06)",
    "zerolinecolor": "rgba(245,239,228,0.12)",
}


def apply_axis_defaults(fig) -> None:
    """
    Apply the shared axis styling to a Plotly figure.

    Call this after update_layout so chart specific titles and ranges stay intact.
    """
    fig.update_xaxes(**AXIS_DEFAULTS)
    fig.update_yaxes(**AXIS_DEFAULTS)

# graph config for inline charts where zoom would make the dashboard feel messy
CHART_CONFIG: Final[dict] = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "staticPlot": False,
}

# county map gets scroll zoom because counties are tiny at national scale
COUNTY_MAP_CONFIG: Final[dict] = {
    "displayModeBar": False,
    "scrollZoom": True,
    "doubleClick": "reset",
    "staticPlot": False,
}