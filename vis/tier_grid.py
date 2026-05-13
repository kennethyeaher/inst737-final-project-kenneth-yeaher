"""
Risk tier explainer grid for the Ovara dashboard.

This is the legend the dashboard otherwise would not have. Each tier renders
as its own card with a colored accent, a mono badge, a Fraunces name, the
threshold range, a short description, and a live count of how many states or
counties currently fall into that tier.

Tier data lives in two small tables at the top of the file so the rendering
function stays short and easy to update.
"""

from __future__ import annotations

from dataclasses import dataclass

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

from vis._brand import BRAND, COUNTY_TIER_COLORS, FONT_HEADING, FONT_MONO, STATE_TIER_COLORS
from vis._styles import CARD_STYLE, COLORS


@dataclass(frozen=True)
class _Tier:
    """One row in a risk tier table."""

    key: str
    badge: str
    name: str
    range_text: str
    description: str
    color: str


def _state_tiers(df: pd.DataFrame) -> list[_Tier]:
    """Build the state tier table with quartile cutoffs calculated from the data."""
    q1, q2, q3 = df["residual"].quantile([0.25, 0.5, 0.75]).tolist()

    return [
        _Tier(
            "Critical",
            "Q1 · Most Underserved",
            "Critical",
            f"Residual < {q1:.1f}",
            "Largest negative residual. Actual provider density falls well below model "
            "expectations. Structural intervention and provider recruitment are likely needed.",
            STATE_TIER_COLORS["Critical"],
        ),
        _Tier(
            "At Risk",
            "Q2 · Below Expected",
            "At Risk",
            f"{q1:.1f} ≤ Residual < {q2:.1f}",
            "Supply is meaningfully below expectations. Workforce and geographic barriers "
            "still compound, but the gap is smaller than the Critical tier.",
            STATE_TIER_COLORS["At Risk"],
        ),
        _Tier(
            "Adequate",
            "Q3 · Near Expected",
            "Adequate",
            f"{q2:.1f} ≤ Residual < {q3:.1f}",
            "Supply is close to expected. There can still be local gaps, but the state level "
            "residual is closer to the middle of the distribution.",
            STATE_TIER_COLORS["Adequate"],
        ),
        _Tier(
            "Well Served",
            "Q4 · Above Expected",
            "Well Served",
            f"Residual ≥ {q3:.1f}",
            "Density meets or exceeds expectations. This is often consistent with hub effects "
            "where a state draws providers from surrounding regions.",
            STATE_TIER_COLORS["Well Served"],
        ),
    ]


_COUNTY_TIERS: list[_Tier] = [
    _Tier(
        "access_desert",
        "Tier 0 · No Providers",
        "Access Desert",
        "0 providers per 100k",
        "Zero reproductive health providers are registered. Residents likely have to travel "
        "out of county for fertility, prenatal, or gynecological care.",
        COUNTY_TIER_COLORS["access_desert"],
    ),
    _Tier(
        "critical",
        "Tier 1 · Severely Underserved",
        "Critical",
        "0 to 5 per 100k",
        "At least one provider is registered, but density is far below national norms. "
        "Access exists in theory but is still severely constrained.",
        COUNTY_TIER_COLORS["critical"],
    ),
    _Tier(
        "underserved",
        "Tier 2 · Below Average",
        "Underserved",
        "5 to 10 per 100k",
        "Density is meaningfully below the national median. This is common in rural areas "
        "and points to targeted workforce development opportunities.",
        COUNTY_TIER_COLORS["underserved"],
    ),
    _Tier(
        "adequate",
        "Tier 3 · Near Median",
        "Adequate",
        "10 to 20 per 100k",
        "Provider density approaches or matches the national median. Supply is more "
        "reasonable for the local population.",
        COUNTY_TIER_COLORS["adequate"],
    ),
    _Tier(
        "well_served",
        "Tier 4 · Above Median",
        "Well Served",
        "Over 20 per 100k",
        "Density is well above the national median. These are often urban counties with "
        "academic medical centers or regional referral activity.",
        COUNTY_TIER_COLORS["well_served"],
    ),
]


def _tone(hex_color: str, blend: float = 0.55) -> str:
    """Lighten a hex color toward cream so it works as readable text."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    cr, cg, cb = 245, 239, 228

    r = int(r * (1 - blend) + cr * blend)
    g = int(g * (1 - blend) + cg * blend)
    b = int(b * (1 - blend) + cb * blend)

    return f"rgb({r}, {g}, {b})"


def _tint(hex_color: str, opacity: float = 0.15) -> str:
    """Return a low opacity rgba tint of a hex color for badge backgrounds."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    return f"rgba({r}, {g}, {b}, {opacity})"


def _badge(label: str, color: str) -> html.Div:
    """Build a small colored dot with a mono uppercase label."""
    return html.Div(
        [
            html.Div(style={
                "width": "7px",
                "height": "7px",
                "borderRadius": "50%",
                "backgroundColor": color,
                "flexShrink": "0",
            }),
            html.Span(label),
        ],
        style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "6px",
            "padding": "3px 10px",
            "borderRadius": "4px",
            "backgroundColor": _tint(color),
            "color": _tone(color),
            "fontFamily": FONT_MONO,
            "fontSize": "9px",
            "fontWeight": "500",
            "letterSpacing": "0.1em",
            "textTransform": "uppercase",
            "marginBottom": "12px",
        },
    )


def _tier_card(tier: _Tier, count_text: str) -> dbc.Card:
    """Render one tier as a card with badge, name, range, description, and count."""
    return dbc.Card(
        [
            _badge(tier.badge, tier.color),
            html.Div(tier.name, style={
                "fontFamily": FONT_HEADING,
                "fontSize": "16px",
                "fontWeight": "700",
                "color": COLORS["text"],
                "marginBottom": "4px",
                "lineHeight": "1.2",
            }),
            html.Div(tier.range_text, style={
                "fontFamily": FONT_MONO,
                "fontSize": "10px",
                "color": COLORS["text_muted"],
                "marginBottom": "12px",
            }),
            html.Div(tier.description, style={
                "fontFamily": "'Inter', sans-serif",
                "fontSize": "12px",
                "color": COLORS["text_muted"],
                "lineHeight": "1.6",
                "marginBottom": "14px",
            }),
            html.Div(count_text, style={
                "fontFamily": FONT_MONO,
                "fontSize": "10px",
                "color": _tone(tier.color),
                "paddingTop": "12px",
                "borderTop": f"1px solid {COLORS['card_border']}",
            }),
        ],
        style={
            **CARD_STYLE,
            "padding": "20px",
            "borderTop": f"3px solid {tier.color}",
        },
    )


def _section_header(subtitle: str) -> html.Div:
    """Build the Fraunces section heading with a coral italic accent."""
    return html.Div(
        [
            html.Span(
                [
                    "Reproductive Health Access ",
                    html.Em("Risk Tiers", style={
                        "color": BRAND["coral"],
                        "fontStyle": "italic",
                    }),
                ],
                style={
                    "fontFamily": FONT_HEADING,
                    "fontWeight": "700",
                    "fontSize": "20px",
                    "color": COLORS["text"],
                    "lineHeight": "1.2",
                },
            ),
            html.Span(subtitle, style={
                "fontFamily": FONT_MONO,
                "fontSize": "9px",
                "letterSpacing": "0.13em",
                "textTransform": "uppercase",
                "color": COLORS["text_muted"],
            }),
        ],
        style={
            "display": "flex",
            "alignItems": "baseline",
            "gap": "14px",
            "padding": "0 0 14px 0",
            "marginBottom": "24px",
            "borderBottom": f"1px solid {COLORS['card_border']}",
            "flexWrap": "wrap",
        },
    )


def _render_grid(
    tiers: list[_Tier],
    counts: dict,
    total: int,
    unit: str,
    subtitle: str,
) -> html.Div:
    """Turn a tier table into a section with a header and card grid."""

    def _count_line(key: str) -> str:
        n = int(counts.get(key, 0))
        pct = round(n / total * 100) if total > 0 else 0

        return f"{n:,} {unit} · {pct}%"

    grid = dbc.Row(
        [dbc.Col(_tier_card(tier, _count_line(tier.key)), md=True) for tier in tiers],
        className="g-3",
    )

    return html.Div(
        [_section_header(subtitle), grid],
        style={"paddingTop": "32px", "marginTop": "16px"},
    )


def state_tier_grid(df: pd.DataFrame) -> html.Div:
    """Build the state level tier grid with quartile based thresholds."""
    counts = df["risk_tier"].value_counts().to_dict()

    return _render_grid(
        _state_tiers(df),
        counts,
        len(df),
        "states",
        "Quartile framework · 2026 model",
    )


def county_tier_grid(df: pd.DataFrame, state_filter: str | None = None) -> html.Div:
    """Build the county level tier grid with density based thresholds."""
    scope = df[df["practice_state"] == state_filter] if state_filter else df
    counts = scope["risk_tier"].value_counts().to_dict()

    return _render_grid(
        _COUNTY_TIERS,
        counts,
        len(scope),
        "counties",
        "Density threshold framework · 2026 model",
    )