"""
State level chart builders for the Ovara dashboard.

Three figures live here:
- build_bar:        horizontal bar of the most underserved states
- build_scatter:    predicted vs actual density with outlier annotations
- build_choropleth: US map colored by access gap or risk tier

Plus a few small helpers for validating the input frame and assigning
risk tiers from regression residuals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import plotly.graph_objects as go

from vis._styles import (
    BASE_LAYOUT,
    CHART_TITLE_FONT,
    COLORS,
    RISK_COLORSCALE,
    RISK_TIER_LABELS,
    UNIFIED_COLORSCALE,
    apply_axis_defaults,
)


# columns the dashboard needs before it can draw anything
REQUIRED_COLUMNS: Final[set[str]] = {
    "practice_state",
    "provider_count",
    "metro_population",
    "providers_per_100k",
    "predicted_provider_density",
    "residual",
    "taxonomy_diversity",
    "recent_provider_growth",
}

# default file path for the regression results frame
INPUT_FILE: Final[Path] = Path("data/model_outputs/regression_results.csv")


def validate_columns(df: pd.DataFrame) -> None:
    """
    Stop early if the regression output is missing fields the dashboard needs.

    Parameters
    df : pd.DataFrame to check.

    Raises
    ValueError listing the missing columns when any are absent.
    """
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"regression_results.csv missing: {sorted(missing)}")


def classify_risk_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each state to a risk tier using residual quartiles.

    Adds two columns to a copy of df:
    - risk_tier: ordered categorical label from RISK_TIER_LABELS
    - risk_tier_num: integer code 0..3 for use as a colorscale value

    Parameters
    df : pd.DataFrame with a residual column.

    Returns
    pd.DataFrame copy with the two new columns.
    """
    df = df.copy()
    df["risk_tier"] = pd.qcut(df["residual"], q=4, labels=RISK_TIER_LABELS)
    df["risk_tier_num"] = df["risk_tier"].cat.codes
    return df


def load_regression_results(path: Path = INPUT_FILE) -> pd.DataFrame:
    """
    Load regression results, drop rows with missing required values, and
    classify risk tiers.

    Parameters
    path : Path to the regression results csv.

    Returns
    pd.DataFrame ready to feed into any chart builder in this module.
    """
    df = pd.read_csv(path)
    validate_columns(df)

    # drop rows that are missing values the dashboard cannot render
    before = df.shape[0]
    df = df.dropna(
        subset=["practice_state", "providers_per_100k", "predicted_provider_density", "residual"]
    ).copy()
    dropped = before - df.shape[0]

    if dropped > 0:
        # logging is the caller's job, but we keep the count visible in the return
        # so the orchestrator can choose to log it
        df.attrs["dropped_rows"] = dropped

    return classify_risk_tiers(df)


def _shared_residual_range(df: pd.DataFrame) -> float:
    """Pick a symmetric residual range so zero stays at the center of the color scale."""
    return max(abs(df["residual"].min()), abs(df["residual"].max()))


def build_bar(
    df: pd.DataFrame,
    selected_states: list[str] | None = None,
) -> go.Figure:
    """
    Build the horizontal bar chart for the most underserved states.

    Bars are colored by each state's risk tier so the chart works as both
    a residual ranking and a tier breakdown. When a user clicks a state on
    the map, the chart filters to that selected state.
    """
    if selected_states:
        subset = df[df["practice_state"].isin(selected_states)].sort_values("residual")
        title_text = f"Access Gap for {', '.join(selected_states)}"
    else:
        subset = df.nsmallest(10, "residual").sort_values("residual")
        title_text = "Top 10 Most Underserved States"

    x_min = subset["residual"].min() if len(subset) > 0 else -4

    # color each bar by risk tier so the chart is easier to read at a glance
    from vis._styles import RISK_TIER_COLORS as TIER_COLORS

    bar_colors = [
        TIER_COLORS.get(tier, COLORS["neg_mid"])
        for tier in subset["risk_tier"].astype(str)
    ]

    fig = go.Figure(go.Bar(
        x=subset["residual"],
        y=subset["practice_state"],
        orientation="h",
        text=subset["residual"].round(2),
        textposition="outside",
        textfont={"size": 12, "color": COLORS["text"]},
        marker={"color": bar_colors},
        hovertemplate="<b>%{y}</b><br>Residual: %{x:.2f}<extra></extra>",
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": title_text, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        xaxis={"title": "Residual (actual − predicted)", "range": [x_min * 1.30, 0.3]},
        yaxis={"title": ""},
    )
    apply_axis_defaults(fig)
    return fig


def build_scatter(df: pd.DataFrame) -> go.Figure:
    """
    Predicted vs actual provider density with outlier annotations.

    The dashed diagonal is the ideal fit line. Points above the line
    have more providers than the model predicted, points below have fewer.
    Annotations call out the single biggest over and under supply states.

    Parameters
    df : pd.DataFrame with risk tiers assigned.

    Returns
    plotly Figure.
    """
    res_max = _shared_residual_range(df)

    axis_min = min(df["predicted_provider_density"].min(), df["providers_per_100k"].min())
    axis_max = max(df["predicted_provider_density"].max(), df["providers_per_100k"].max())
    pad = (axis_max - axis_min) * 0.08
    axis_range = [axis_min - pad, axis_max + pad]

    fig = go.Figure()

    # ideal fit line: actual equals predicted
    fig.add_trace(go.Scatter(
        x=axis_range, y=axis_range,
        mode="lines",
        line={"dash": "dash", "width": 2, "color": COLORS["accent"]},
        hoverinfo="skip", showlegend=False,
    ))

    # data points colored by residual
    fig.add_trace(go.Scatter(
        x=df["predicted_provider_density"],
        y=df["providers_per_100k"],
        mode="markers",
        text=df["practice_state"],
        marker={
            "size": 11,
            "color": df["residual"],
            "colorscale": UNIFIED_COLORSCALE,
            "cmin": -res_max, "cmax": res_max,
            "showscale": True,
            "colorbar": {"title": "Residual", "thickness": 12, "len": 0.75},
            "line": {"width": 0.6, "color": "white"},
        },
        hovertemplate="<b>%{text}</b><br>Predicted: %{x:.2f}<br>Actual: %{y:.2f}<extra></extra>",
        showlegend=False,
    ))

    # call out the single biggest over supply and the two biggest under supply states
    annotations = _build_outlier_annotations(df, axis_min, axis_max, pad)

    fig.update_layout(
        **BASE_LAYOUT,
        title={
            "text": "Predicted vs Actual Reproductive Health Provider Density",
            "font": CHART_TITLE_FONT,
            "x": 0.02,
            "xanchor": "left",
        },
        xaxis={"title": "Predicted Providers per 100k", "range": axis_range},
        yaxis={"title": "Actual Providers per 100k", "range": axis_range},
        annotations=annotations,
    )
    apply_axis_defaults(fig)
    return fig


def _build_outlier_annotations(
    df: pd.DataFrame,
    axis_min: float,
    axis_max: float,
    pad: float,
) -> list[dict]:
    """Build the three labeled callouts plus the ideal fit line label."""
    annotations: list[dict] = []
    anno_base = {
        "showarrow": True, "arrowhead": 2,
        "borderwidth": 1, "bgcolor": "rgba(255,255,255,0.85)",
    }

    # biggest over supply state (positive residual)
    top = df.nlargest(1, "residual").iloc[0]
    annotations.append({
        **anno_base,
        "x": top["predicted_provider_density"], "y": top["providers_per_100k"],
        "text": f"<b>{top['practice_state']}</b><br>+{top['residual']:.1f} above expected",
        "arrowcolor": COLORS["pos_strong"], "bordercolor": COLORS["pos_strong"],
        "font": {"size": 11, "color": COLORS["pos_strong"]},
        "ax": 50, "ay": 40,
    })

    # two biggest under supply states (most negative residuals)
    for i, (_, row) in enumerate(df.nsmallest(2, "residual").iterrows()):
        offsets = [{"ax": -60, "ay": -30}, {"ax": -60, "ay": 35}]
        annotations.append({
            **anno_base,
            "x": row["predicted_provider_density"], "y": row["providers_per_100k"],
            "text": f"<b>{row['practice_state']}</b><br>{row['residual']:.1f} below expected",
            "arrowcolor": COLORS["neg_strong"], "bordercolor": COLORS["neg_strong"],
            "font": {"size": 11, "color": COLORS["neg_strong"]},
            **offsets[i],
        })

    # label for the dashed ideal fit line
    mid = (axis_min + axis_max) / 2
    annotations.append({
        "x": mid + pad * 2, "y": mid + pad * 2,
        "text": "Ideal: actual = predicted",
        "showarrow": False,
        "font": {"size": 11, "color": COLORS["accent"]},
        "bgcolor": "rgba(255,255,255,0.8)",
    })

    return annotations


def build_choropleth(
    df: pd.DataFrame,
    selected_state: str | None = None,
    view_mode: str = "gap",
) -> go.Figure:
    """
    US choropleth in either access gap or risk tier mode.

    Parameters
    df : pd.DataFrame with risk tiers assigned.
    selected_state : str or None
        State abbreviation passed in from a map click. Highlights the
        selected state with a thicker border and dims the others.
    view_mode : str
        Either "gap" (continuous residual scale) or "tier" (four discrete bands).

    Returns
    plotly Figure.
    """
    states = df["practice_state"]
    n = len(states)

    # state highlight: thicker border on the clicked state, dimmed neighbors
    if selected_state:
        line_widths = [4 if s == selected_state else 1 for s in states]
        line_colors = ["#000000" if s == selected_state else "white" for s in states]
        opacities = [1.0 if s == selected_state else 0.4 for s in states]
    else:
        line_widths, line_colors, opacities = [1.5] * n, ["white"] * n, [1.0] * n

    marker = {"line": {"color": line_colors, "width": line_widths}, "opacity": opacities}

    # mode specific values: z, colorscale, colorbar, hover, title
    z, colorscale, zmin, zmax, colorbar, hover, title_text = _resolve_choropleth_mode(
        df, selected_state, view_mode,
    )

    fig = go.Figure(go.Choropleth(
        locations=states, z=z,
        locationmode="USA-states",
        colorscale=colorscale,
        zmin=zmin, zmax=zmax,
        marker=marker,
        colorbar=colorbar,
        customdata=df["risk_tier"].astype(str),
        hovertemplate=hover,
    ))

    fig.update_layout(
        **{**BASE_LAYOUT, "height": 520, "margin": {"l": 0, "r": 0, "t": 50, "b": 0}},
        title={"text": title_text, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        geo=dict(
            scope="usa", projection_type="albers usa",
            showland=True, landcolor=COLORS["bg"],
            showlakes=True, lakecolor=COLORS["card_bg"],
            showframe=False, bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


def _resolve_choropleth_mode(
    df: pd.DataFrame,
    selected_state: str | None,
    view_mode: str,
) -> tuple:
    """Pick z values, colorscale, colorbar, hover template, and title for the chosen view."""
    if view_mode == "tier":
        z = df["risk_tier_num"]
        colorscale = RISK_COLORSCALE
        zmin, zmax = 0, 3
        colorbar = {
            "title": "Risk Tier", "thickness": 14, "len": 0.75,
            "x": 1.01, "y": 0.5,
            "tickvals": [0.375, 1.125, 1.875, 2.625],
            "ticktext": RISK_TIER_LABELS,
            "tickfont": {"size": 11}, "title_font": {"size": 12},
        }
        hover = "<b>%{location}</b><br>Risk Tier: %{customdata}<extra></extra>"
        title_text = "Reproductive Health Access Risk Tiers"
        if selected_state:
            row = df[df["practice_state"] == selected_state]
            if len(row) > 0:
                title_text = f"Access Risk {selected_state} ({row.iloc[0]['risk_tier']})"
        return z, colorscale, zmin, zmax, colorbar, hover, title_text

    # default: continuous access gap view
    res_max = _shared_residual_range(df)
    z = df["residual"]
    colorscale = UNIFIED_COLORSCALE
    zmin, zmax = -res_max, res_max
    colorbar = {
        "title": "Access Gap", "thickness": 14, "len": 0.75,
        "x": 1.01, "y": 0.5,
        "tickfont": {"size": 11}, "title_font": {"size": 12},
    }
    hover = "<b>%{location}</b><br>Access Gap: %{z:.2f}<br>Risk Tier: %{customdata}<extra></extra>"
    title_text = "Reproductive Health Access Gap Map"
    if selected_state:
        row = df[df["practice_state"] == selected_state]
        if len(row) > 0:
            title_text = f"Access Gap {selected_state} (gap: {row.iloc[0]['residual']:.2f})"
    return z, colorscale, zmin, zmax, colorbar, hover, title_text
