"""
Findings card for the Ovara dashboard.

The findings card is the editorial centerpiece of the dashboard. It sits
on a cream surface in the middle of the dark dashboard and presents the
top model findings in a two column prose layout, with a mono eyebrow,
a Fraunces headline with an italic coral accent, and plum body copy.

Two builders are exposed, one per dashboard view. Both return the same
component shape so they can drop into the same layout slot:

state_findings_card(df): state level findings
county_findings_card(df, state_filter=None): county level findings
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

from vis._brand import BRAND, FONT_HEADING, FONT_MONO

# style atoms shared by both card variants
_CARD_STYLE: dict = {
    "backgroundColor": BRAND["cream"],
    "borderRadius": "12px",
    "padding": "36px 44px",
    "marginBottom": "24px",
    "border": "none",
}

_EYEBROW_STYLE: dict = {
    "fontFamily": FONT_MONO,
    "fontSize": "9px",
    "letterSpacing": "0.15em",
    "textTransform": "uppercase",
    "color": BRAND["coral"],
    "marginBottom": "16px",
    "fontWeight": "500",
}

_HEADLINE_STYLE: dict = {
    "fontFamily": FONT_HEADING,
    "fontWeight": "700",
    "fontSize": "22px",
    "color": BRAND["plum_ink"],
    "lineHeight": "1.3",
    "marginBottom": "22px",
    "letterSpacing": "-0.005em",
}

_BODY_STYLE: dict = {
    "fontFamily": "'Inter', sans-serif",
    "fontSize": "13px",
    "color": "rgba(47, 26, 62, 0.72)",
    "lineHeight": "1.85",
    "columns": "2",
    "columnGap": "52px",
    "marginBottom": "0",
}


def _emphasis(text: str) -> html.Em:
    """Build an italic coral phrase for the card headline."""
    return html.Em(text, style={"color": BRAND["coral"], "fontStyle": "italic"})


def _bold(text: str) -> html.Strong:
    """Build a bold plum phrase for key facts inside body copy."""
    return html.Strong(text, style={"color": BRAND["plum_ink"], "fontWeight": "600"})


def _paragraph(*children) -> html.P:
    """Build a body paragraph that works cleanly in the two column layout."""
    return html.P(list(children), style={
        "marginBottom": "14px",
        "breakInside": "avoid",
    })


def _card(eyebrow: str, headline: list, body: list) -> dbc.Card:
    """
    Shared layout for state and county findings cards.

    This keeps the cream card surface consistent so future views can reuse the
    same structure with different content.
    """
    return dbc.Card(
        [
            html.Div(eyebrow, style=_EYEBROW_STYLE),
            html.H2(headline, style=_HEADLINE_STYLE),
            html.Div(body, style=_BODY_STYLE),
        ],
        style=_CARD_STYLE,
    )


def state_findings_card(df: pd.DataFrame) -> dbc.Card:
    """
    Build the state level findings card.

    Headline numbers come directly from the regression results frame so the
    written findings stay aligned with the data.
    """
    name_col = "state_name" if "state_name" in df.columns else "practice_state"

    n_states = int(df["practice_state"].nunique())
    n_critical = int((df["risk_tier"] == "Critical").sum())
    n_at_risk = int((df["risk_tier"] == "At Risk").sum())
    n_concern = n_critical + n_at_risk

    worst = df.nsmallest(1, "residual").iloc[0]
    worst_name = worst.get(name_col, worst["practice_state"])
    worst_gap = worst["residual"]

    best = df.nlargest(1, "residual").iloc[0]
    best_name = best.get(name_col, best["practice_state"])
    best_gap = best["residual"]

    worst_3 = ", ".join(df.nsmallest(3, "residual")[name_col].tolist())

    eyebrow = "Model Findings · State Level · 2026"

    headline = [
        "The residual map surfaces where ",
        _emphasis("geography, demographics, and workforce barriers"),
        " create persistent reproductive health access gaps.",
    ]

    body = [
        _paragraph(
            "Across the ",
            _bold(f"{n_states} states"),
            " analyzed, Ovara's model estimated expected provider supply using "
            "population, taxonomy diversity, workforce age, recent provider growth, and "
            "fertility age demographics. States falling far below their predicted supply "
            "are flagged as underserved relative to model expectations, meaning that even "
            "accounting for known supply drivers, access remains structurally constrained.",
        ),
        _paragraph(
            "Of those states, ",
            _bold(f"{n_concern} fall into a tier of concern"),
            ", with ",
            _bold(f"{n_critical} classified as Critical"),
            " and ",
            _bold(f"{n_at_risk} as At Risk"),
            ". The three most underserved states are ",
            _bold(worst_3),
            ", clustered in patterns that suggest workforce retention barriers, "
            "geographic isolation, and small population bases with limited academic medical "
            "infrastructure.",
        ),
        _paragraph(
            _bold(f"{worst_name}'s residual of {worst_gap:.2f}"),
            " represents the largest access gap in the dataset. The state's population "
            "and workforce profile would predict meaningfully higher provider density than "
            "is actually registered, a structural mismatch that demographic variables alone "
            "cannot explain and that signals a need for targeted intervention.",
        ),
        _paragraph(
            "On the other end of the spectrum, ",
            _bold(f"{best_name} shows the strongest positive residual at +{best_gap:.1f}"),
            ", with actual provider density well above what demographics predict. "
            "This pattern is consistent with a hub effect, where certain states draw "
            "providers from surrounding regions and end up over supplied relative to their "
            "local population alone.",
        ),
    ]

    return _card(eyebrow, headline, body)


def county_findings_card(
    df: pd.DataFrame,
    state_filter: str | None = None,
) -> dbc.Card:
    """
    Build the county level findings card.

    The headline and body text adapt when a state filter is active. All numbers
    are recomputed across the filtered scope so the card stays accurate as the
    user drills into a state.
    """
    scope = df[df["practice_state"] == state_filter] if state_filter else df

    n_counties = len(scope)
    n_desert = int((scope["provider_count"] == 0).sum())
    pct_desert = round(n_desert / n_counties * 100) if n_counties > 0 else 0
    pop_desert = int(scope[scope["provider_count"] == 0]["total_population"].sum())

    n_critical = int((scope["risk_tier"] == "critical").sum())
    n_underserved = int((scope["risk_tier"] == "underserved").sum())
    n_concern = n_desert + n_critical + n_underserved

    populated = scope[scope["total_population"] > 0]
    med_density = populated["providers_per_100k"].median() if len(populated) > 0 else 0.0

    scope_label = state_filter if state_filter else "the United States"

    eyebrow = (
        f"Model Findings · County Level · {state_filter}"
        if state_filter else "Model Findings · County Level · 2026"
    )

    headline = [
        "County level data exposes ",
        _emphasis("access deserts"),
        " that state averages can completely hide.",
    ]

    body = [
        _paragraph(
            f"Of the {n_counties:,} counties analyzed across {scope_label}, ",
            _bold(f"{n_desert:,} have no registered reproductive health provider"),
            f", roughly {pct_desert}% of the analyzed counties. ",
            "These are not low density counties. They are access deserts where the local "
            "workforce is missing from the federal registry entirely.",
        ),
        _paragraph(
            "The ",
            _bold(f"{pop_desert:,} residents"),
            " living in those access desert counties likely travel to a neighboring "
            "county for fertility care, prenatal services, or gynecological treatment, a "
            "burden that falls hardest on communities with the fewest transportation options.",
        ),
        _paragraph(
            "Beyond the access deserts, another ",
            _bold(f"{n_critical:,} counties are classified as Critical"),
            f" with fewer than 5 providers per 100k, and {n_underserved:,} are classified "
            f"as Underserved with 5 to 10 providers per 100k. Combined, {n_concern:,} "
            f"counties fall into a tier of concern, against a median density of just "
            f"{med_density:.1f} providers per 100k.",
        ),
        _paragraph(
            "County level resolution matters because state averages can hide the real "
            "access problem. A state can look adequate overall while still containing "
            "dozens of counties where no reproductive health provider is registered at all.",
        ),
    ]

    return _card(eyebrow, headline, body)
