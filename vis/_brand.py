"""
Ovara brand 

Single source of truth for the brand palette, typography stack, and tier color mapping. 
Every dashboard module reads its visual identity from this file so brand changes happen in one place.

Palette role reference
- iris        primary
- iris_deep   pressed / hover, deepest tier
- coral       secondary, attention
- sage        tier: well served
- marigold    tier: adequate
- cream       surface
- cream_deep  surface 2
- plum_ink    text on light, deep bg
"""

from __future__ import annotations
from typing import Final


# brand palette

BRAND: Final[dict[str, str]] = {
    "iris":       "#6846AA",
    "iris_deep":  "#4A3698",
    "coral":      "#C45B32",
    "sage":       "#5B9066",
    "marigold":   "#C9A652",
    "cream":      "#F7F4EE",
    "cream_deep": "#ECE3D2",
    "plum_ink":   "#2F1A3E",
    "teal":       "#1A89C5",
}


# typography stacks

FONT_HEADING: Final[str] = "'Fraunces', Georgia, serif"
FONT_BODY: Final[str] = "'Inter', 'Segoe UI', sans-serif"
FONT_MONO: Final[str] = "'JetBrains Mono', 'Menlo', monospace"


# County tiers use an ordered iris ramp. Zero registered supply stays separate
# in burnt coral. Labels and exact values provide the same meaning without hue.
SUPPLY_TIER_RAMP: Final[list[str]] = [
    "#6041A0",  # lowest supply
    "#8A6CBD",
    "#B59DD6",
    "#DBCEEE",  # highest supply
]

# zero providers is a different state rather than a smaller amount, so it sits
# off the ramp in coral. that also leaves the ramp free to carry a no data
# colour later without colliding with a real value.

ACCESS_DESERT_COLOR: Final[str] = BRAND["coral"]

# no county currently lacks data, but an ordered ramp with no slot for unknown
# is how a join failure gets published as a real low value

NO_DATA_COLOR: Final[str] = "#CFCBC4"


# Legacy color names retained for exported analysis consumers.
# The interactive state overview does not classify states into risk tiers.

STATE_TIER_COLORS: Final[dict[str, str]] = dict(
    zip(["Critical", "At Risk", "Adequate", "Well Served"], SUPPLY_TIER_RAMP)
)


# county level risk tiers, the same ramp plus the off ramp desert colour, so a
# tier means the same thing visually in both views

COUNTY_TIER_COLORS: Final[dict[str, str]] = {
    "access_desert": ACCESS_DESERT_COLOR,
    **dict(zip(["critical", "underserved", "adequate", "well_served"], SUPPLY_TIER_RAMP)),
}


# Iris atlas semantic surfaces shared by the interactive dashboard and charts.
UI: Final[dict[str, str]] = {
    "bg": "#F7F4EE",
    "surface": "#FFFFFF",
    "surface_alt": "#EEE7FA",
    "border": "#DCD5E2",
    "text": "#2F1A3E",
    "text_muted": "#645B6F",
    "accent": "#6846AA",
    "accent_deep": "#54388F",
    "attention": "#C45B32",
    "good": "#5B9066",
    "warn": "#C9A652",
    "bad": "#C45B32",
}
