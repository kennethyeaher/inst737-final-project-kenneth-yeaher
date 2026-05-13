"""
Branded UI atoms for the Ovara dashboard.

These are small reusable pieces that carry the Ovara visual identity, like the
wordmark and navbar logo mark. Layout modules can use them without needing to
know hex values or font names.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

from vis._brand import BRAND, FONT_HEADING, FONT_MONO
from vis._styles import COLORS


def _logo_mark(size: int = 26) -> html.Img:
    """
    Build the Ovara logo mark as an inline SVG.

    The mark is an iris purple rounded square with a cream ring and dot.
    It uses a data URI so the dashboard does not need a separate image file.
    """
    iris = BRAND["iris"]
    cream = BRAND["cream"]

    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 26 26'>"
        f"<rect width='26' height='26' rx='6' fill='{iris}'/>"
        f"<circle cx='13' cy='13' r='7.5' fill='none' "
        f"stroke='{cream}' stroke-opacity='0.93' stroke-width='1.8'/>"
        f"<circle cx='13' cy='13' r='2.8' fill='{cream}' fill-opacity='0.93'/>"
        f"</svg>"
    )

    return html.Img(
        src=f"data:image/svg+xml;utf8,{svg}",
        style={
            "width": f"{size}px",
            "height": f"{size}px",
            "display": "block",
        },
    )


def wordmark(size_px: int = 17) -> html.Span:
    """
    Build the Ovara wordmark.

    The wordmark styles the middle letter in coral and the period in iris
    so the dashboard keeps a small branded touch without being too loud.
    """
    return html.Span(
        [
            "ov",
            html.Span("a", style={"fontStyle": "italic", "color": BRAND["coral"]}),
            "ra",
            html.Span(".", style={"color": BRAND["iris"]}),
        ],
        style={
            "fontFamily": FONT_HEADING,
            "fontWeight": "700",
            "fontSize": f"{size_px}px",
            "color": COLORS["text"],
            "letterSpacing": "-0.02em",
        },
    )


def topnav(context_tag: str | None = None) -> html.Nav:
    """
    Build the sticky top navigation bar.

    The left side shows the logo mark and wordmark. The right side can show
    a small context tag when a dashboard view needs extra context.
    """
    right_children: list = []

    if context_tag is not None:
        right_children.append(html.Span(context_tag, style={
            "fontFamily": FONT_MONO,
            "fontSize": "9px",
            "letterSpacing": "0.12em",
            "textTransform": "uppercase",
            "color": COLORS["text_muted"],
        }))

    return html.Nav(
        [
            html.Div(
                [_logo_mark(26), wordmark(17)],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                },
            ),
            html.Div(
                right_children,
                style={
                    "marginLeft": "auto",
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "14px",
                },
            ),
        ],
        style={
            "backgroundColor": "#201440",
            "borderBottom": f"1px solid {COLORS['card_border']}",
            "height": "52px",
            "display": "flex",
            "alignItems": "center",
            "padding": "0 32px",
            "position": "sticky",
            "top": "0",
            "zIndex": "200",
        },
    )