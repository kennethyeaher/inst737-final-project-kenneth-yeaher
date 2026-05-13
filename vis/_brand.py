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
    "iris":       "#6B4FBF",
    "iris_deep":  "#4A3698",
    "coral":      "#E87A3C",
    "sage":       "#5B9066",
    "marigold":   "#C9A652",
    "cream":      "#F5EFE4",
    "cream_deep": "#ECE3D2",
    "plum_ink":   "#2F1A3E",
}


# typography stacks

FONT_HEADING: Final[str] = "'Fraunces', Georgia, serif"
FONT_BODY: Final[str] = "'Inter', 'Segoe UI', sans-serif"
FONT_MONO: Final[str] = "'JetBrains Mono', 'Menlo', monospace"


# state level risk tier mapping ordered from most underserved to best served so quartile codes 0..3
# line up with the residual ranking

STATE_TIER_COLORS: Final[dict[str, str]] = {
    "Critical":    BRAND["iris_deep"],
    "At Risk":     BRAND["coral"],
    "Adequate":    BRAND["marigold"],
    "Well Served": BRAND["sage"],
}


# county level risk tier mapping access desert is the deepest plum because it represents zero supply, not just a low quartile

COUNTY_TIER_COLORS: Final[dict[str, str]] = {
    "access_desert": BRAND["plum_ink"],
    "critical":      BRAND["iris_deep"],
    "underserved":   BRAND["coral"],
    "adequate":      BRAND["marigold"],
    "well_served":   BRAND["sage"],
}


# semantic ui 
# dark mode by default to match the brand guide's primary aesthetic.
# bg and surface are derived from plum ink with depth steps, text is cream with alpha for muted variants.

UI: Final[dict[str, str]] = {
    "bg":          "#17102C",
    "surface":     "#201440",
    "surface_alt": "#2A1A52",
    "border":      "rgba(245, 239, 228, 0.10)",
    "text":        BRAND["cream"],
    "text_muted":  "rgba(245, 239, 228, 0.65)",
    "accent":      BRAND["iris"],
    "accent_deep": BRAND["iris_deep"],
    "attention":   BRAND["coral"],
    "good":        BRAND["sage"],
    "warn":        BRAND["marigold"],
    "bad":         BRAND["coral"],
}