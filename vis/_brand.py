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
    "teal":       "#1A89C5",
}


# typography stacks

FONT_HEADING: Final[str] = "'Fraunces', Georgia, serif"
FONT_BODY: Final[str] = "'Inter', 'Segoe UI', sans-serif"
FONT_MONO: Final[str] = "'JetBrains Mono', 'Menlo', monospace"


# access tiers are ordered, so they get one hue at rising lightness rather than
# four unrelated hues. lightness is the channel that survives greyscale, poor
# screens and colour blindness, so severity stays readable when hue does not.
#
# the band is constrained from both ends. the county map draws these on a light
# carto basemap, so the lightest step has to stay dark enough to see. every
# other surface, the bars, the badges, the state choropleth, is dark plum, so
# the darkest step has to stay light enough to read there. L 0.53 to 0.80 is
# the window that satisfies both, measured at 1.78 minimum contrast on the
# basemap and 3.03 on the dark surface.

SUPPLY_TIER_RAMP: Final[list[str]] = [
    "#6E57BB",  # worst supply
    "#8775D1",
    "#A294E4",
    "#BDB5EE",  # best supply
]

# zero providers is a different state rather than a smaller amount, so it sits
# off the ramp in coral. that also leaves the ramp free to carry a no data
# colour later without colliding with a real value.

ACCESS_DESERT_COLOR: Final[str] = BRAND["coral"]

# no county currently lacks data, but an ordered ramp with no slot for unknown
# is how a join failure gets published as a real low value

NO_DATA_COLOR: Final[str] = "#CFCBC4"


# state level risk tiers, ordered most underserved to best served so quartile
# codes 0..3 line up with the residual ranking

STATE_TIER_COLORS: Final[dict[str, str]] = dict(
    zip(["Critical", "At Risk", "Adequate", "Well Served"], SUPPLY_TIER_RAMP)
)


# county level risk tiers, the same ramp plus the off ramp desert colour, so a
# tier means the same thing visually in both views

COUNTY_TIER_COLORS: Final[dict[str, str]] = {
    "access_desert": ACCESS_DESERT_COLOR,
    **dict(zip(["critical", "underserved", "adequate", "well_served"], SUPPLY_TIER_RAMP)),
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