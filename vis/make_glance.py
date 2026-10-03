"""
Build the README at a glance strip from tables the pipeline has already written.

Every number on the strip is read from data/model_outputs, so the strip can
never drift from the numbers in the README. Text uses a system font stack and
the strip carries its own plum background, so it reads in light and dark
GitHub themes without web fonts.

Run after main.py:
    python -m vis.make_glance

Output written to docs/assets:
    at_a_glance.svg
"""

from __future__ import annotations

import json
from pathlib import Path

from vis._brand import BRAND

# input tables, all written by earlier pipeline stages

COUNTY_METADATA_FILE = Path("data/model_outputs/county_risk_metadata.json")
STATE_METADATA_FILE = Path("data/model_outputs/state_density_metadata.json")
FEATURE_SELECTION_FILE = Path("data/model_outputs/feature_selection.json")

OUTPUT_FILE = Path("docs/assets/at_a_glance.svg")

# card surface sits one step lighter than the plum ink background

COLOR_CARD = "#3A2550"
COLOR_BORDER = "#4A3460"
COLOR_NOTE = "#C9BFD6"
FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

CARD_WIDTH = 282
CARD_HEIGHT = 150
CARD_GAP = 12
PADDING = 12


def load_json(path: Path) -> dict:
    """Read one JSON output written by an earlier pipeline stage."""
    with open(path) as handle:
        return json.load(handle)


def build_cards() -> list[tuple[str, str, str, str]]:
    """
    Compute the four headline results the strip shows.

    Returns
    list of (value, label, note, accent) tuples, one per card
    """
    county = load_json(COUNTY_METADATA_FILE)
    state = load_json(STATE_METADATA_FILE)
    selection = load_json(FEATURE_SELECTION_FILE)
    selected_r2 = selection["candidates"][selection["selected"]]["cv5_r2_mean"]

    return [
        (f"{county['counties_zero_providers']:,}",
         "Counties with no provider",
         f"of {county['total_counties']:,} US counties",
         BRAND["coral"]),
        (f"{county['population_in_access_deserts']:,}",
         "Residents in those counties",
         "ACS population, no model involved",
         BRAND["coral"]),
        (f"{state['national_providers_per_100k']:.2f}",
         "Providers per 100k nationally",
         f"{state['states_below_national_rate']} of {state['total_states']} states fall below it",
         BRAND["iris"]),
        (f"R² {selected_r2:+.2f}",
         "State regression fit",
         "Cross validated, a negative result",
         BRAND["marigold"]),
    ]


def escape(text: str) -> str:
    """Escape the characters SVG text cannot hold literally."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(cards: list[tuple[str, str, str, str]]) -> str:
    """
    Lay the cards out in one row on the plum ink background.

    Parameters
    cards : list of (value, label, note, accent) tuples from build_cards

    Returns
    the complete SVG document as a string
    """
    width = PADDING * 2 + CARD_WIDTH * len(cards) + CARD_GAP * (len(cards) - 1)
    height = PADDING * 2 + CARD_HEIGHT
    summary = "; ".join(f"{value}: {label}. {note}" for value, label, note, _ in cards)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
        '  <title id="title">Ovara results at a glance</title>',
        f'  <desc id="description">{escape(summary)}</desc>',
        f'  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" '
        f'fill="{BRAND["plum_ink"]}" stroke="{COLOR_BORDER}"/>',
    ]
    for index, (value, label, note, accent) in enumerate(cards):
        x = PADDING + index * (CARD_WIDTH + CARD_GAP)
        parts += [
            f'  <rect x="{x}" y="{PADDING}" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="10" fill="{COLOR_CARD}"/>',
            f'  <rect x="{x}" y="{PADDING}" width="4" height="{CARD_HEIGHT}" rx="2" fill="{accent}"/>',
            f'  <text x="{x + 24}" y="{PADDING + 58}" fill="#FFFFFF" font-family="{FONT_STACK}" '
            f'font-size="36" font-weight="700">{escape(value)}</text>',
            f'  <text x="{x + 24}" y="{PADDING + 96}" fill="{BRAND["cream"]}" font-family="{FONT_STACK}" '
            f'font-size="17" font-weight="600">{escape(label)}</text>',
            f'  <text x="{x + 24}" y="{PADDING + 126}" fill="{COLOR_NOTE}" font-family="{FONT_STACK}" '
            f'font-size="15">{escape(note)}</text>',
        ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    """Write the strip and print the values it carries."""
    cards = build_cards()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(render_svg(cards))
    for value, label, note, _ in cards:
        print(f"{value:>12}  {label}  ({note})")
    print(f"wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
