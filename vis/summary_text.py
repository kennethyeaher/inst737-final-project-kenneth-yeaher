"""
Executive summary text for the dashboard.

The state and county views each have a written summary panel that
explains what the user is looking at in plain language. Keeping the
prose in its own module means I can edit the writing without scrolling
past chart code, and the dashboard module stays focused on layout
instead of paragraphs.
"""

from __future__ import annotations

import pandas as pd
from dash import html

from vis._styles import COLORS


def _bold(text: str):
    """Inline helper that wraps text in a bold span using the dashboard text color."""
    return html.B(text, style={"color": COLORS["text"]})


def generate_state_summary(df: pd.DataFrame) -> list:
    """
    Build the multi paragraph executive summary for the state view.

    Pulls the headline numbers (total states, total providers, average
    density, worst residual, etc.) directly from the dataframe so the
    prose updates whenever the regression output changes.

    Parameters
    df : pd.DataFrame with risk tiers assigned, residuals, and a
         metro_population column.

    Returns
    list of html.Span and html.Br elements ready to drop into a Dash layout.
    """
    n_states = df["practice_state"].nunique()
    if n_states == 0:
        return [html.Span("No state-level data available for summary.")]

    name_col = "state_name" if "state_name" in df.columns else "practice_state"

    # headline numbers
    total_providers = int(df["provider_count"].sum())
    avg_density = df["providers_per_100k"].mean()
    med_density = df["providers_per_100k"].median()

    # underserved vs over served
    underserved = df[df["residual"] < 0]
    n_under = len(underserved)
    pct_under = round(n_under / n_states * 100)
    n_over = len(df[df["residual"] > 0])

    # worst three
    worst_3 = df.nsmallest(3, "residual")
    worst_names = ", ".join(worst_3[name_col].tolist())
    worst_avg_gap = worst_3["residual"].mean()

    # the single worst case turned into an implied provider deficit
    worst_1 = df.nsmallest(1, "residual").iloc[0]
    worst_1_name = worst_1.get(name_col, worst_1["practice_state"])
    worst_1_gap = worst_1["residual"]
    worst_1_pop = worst_1["metro_population"]
    implied_deficit = int(abs(worst_1_gap) * worst_1_pop / 100_000)

    # best three
    best_3 = df.nlargest(3, "residual")
    best_names = ", ".join(best_3[name_col].tolist())

    # geographic concentration of the workforce
    top5_providers = df.nlargest(5, "provider_count")["provider_count"].sum()
    top5_pct = top5_providers / total_providers * 100 if total_providers > 0 else 0

    # tier counts
    tier_counts = df["risk_tier"].value_counts()
    n_critical = int(tier_counts.get("Critical", 0))
    n_at_risk = int(tier_counts.get("At Risk", 0))

    b = _bold

    return [
        html.Span([
            "What you're looking at on this dashboard is a gap analysis of reproductive health "
            "provider access across the United States. The core question Ovara is designed to "
            "answer isn't just how many OB/GYNs, midwives, and women's health nurse practitioners "
            "are registered in each state, that's a number you could pull directly from a federal "
            "registry. The harder question is: ",
            b("given everything we know about a state's size, demographics, and workforce history, "
              "how many providers should we reasonably expect to see there?"),
            " The gap between that expectation and reality is what the model calls a residual. "
            "A negative residual means a state has fewer providers than its population and "
            "workforce profile would predict. That gap is what gets flagged as an access concern.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            "Across ", b(f"{n_states} states"), " analyzed, Ovara identified ",
            b(f"{total_providers:,}"), " active reproductive health providers, a workforce spanning "
            "OB/GYNs, reproductive endocrinologists, certified nurse midwives, maternal-fetal medicine "
            "specialists, and women's health nurse practitioners. The national average density is ",
            b(f"{avg_density:.2f}"), " providers per 100,000 residents, but the median sits at ",
            b(f"{med_density:.2f}"),
            ", a meaningful gap that reflects how a handful of high density states pull the average "
            "upward. In fact, the top 5 states by provider count account for ",
            b(f"{top5_pct:.0f}%"),
            " of the entire national workforce, a level of geographic concentration that shows how "
            "unevenly this workforce is distributed across the country.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            b(f"{n_under} states ({pct_under}%)"),
            " fall below their model predicted supply levels. Of those, ",
            b(f"{n_critical} are classified as Critical"),
            " and ",
            b(f"{n_at_risk} as At Risk"),
            ", the states where the shortfall is most severe relative to what their population "
            "profile would suggest. The three most underserved states are ",
            b(worst_names), ", averaging a gap of ",
            b(f"{worst_avg_gap:.2f}"),
            " providers per 100,000 below expected. To put that in concrete terms: ",
            b(worst_1_name),
            " alone has a residual of ", b(f"{worst_1_gap:.2f}"),
            f" applied across its metro population of {worst_1_pop:,.0f}, that translates to roughly ",
            b(f"{implied_deficit:,} fewer providers"),
            " than the model would predict for a state with similar characteristics. These are not "
            "just statistical artifacts. They represent real gaps in access to fertility care, "
            "prenatal services, and gynecological treatment that fall hardest on communities with "
            "the fewest alternatives.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            "On the other end of the spectrum, ",
            b(f"{n_over} states"), " exceed their predicted supply levels. ",
            b(best_names), " show the strongest over supply, states that appear to attract providers "
            "well beyond what their local population base alone would explain. This pattern is "
            "consistent with a hub effect. Certain states, often those with major academic medical "
            "centers or historically strong healthcare economies, draw providers from surrounding "
            "regions. That dynamic benefits the states themselves but can contribute to the vacuum "
            "in neighboring areas that end up in the Critical and At Risk tiers.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            "The intent of this analysis is not to rank states as successes or failures. It is to "
            "give policymakers, health systems, and advocates a clearer and more honest picture of "
            "where the supply demand imbalance actually sits. Provider supply data has always "
            "existed in federal registries like the NPPES, but it rarely gets turned into actionable "
            "access intelligence at this level of geographic specificity. Ovara is my attempt to "
            "bridge that gap by taking raw federal workforce data and converting it into insights "
            "that can inform clinic placement, workforce development funding, and policy advocacy "
            "for the communities that need it most.",
        ]),
    ]
