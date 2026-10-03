"""
State level chart builders for the Ovara dashboard.

Three figures live here:
- build_bar:        horizontal bar of the ten thinnest states by density
- build_scatter:    model diagnostic, predicted against actual density
- build_choropleth: US map on a continuous provider density scale

Everything here reads observed provider density. The residual based risk
tiers this module used to draw were retired: they cut quartiles, so exactly a
quarter of states were labelled high risk whatever the data said, and they did
it on residuals from a model whose honest cross validated R2 is about 0.12.
The scatter survives as a labelled diagnostic, not as a finding.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pandas as pd
import plotly.graph_objects as go

from vis._brand import SUPPLY_TIER_RAMP
from vis._styles import (
    BASE_LAYOUT,
    CHART_TITLE_FONT,
    COLORS,
    UNIFIED_COLORSCALE,
    apply_axis_defaults,
)


# columns the dashboard needs before it can draw anything
REQUIRED_COLUMNS: Final[set[str]] = {
    "practice_state",
    "provider_count",
    "state_population",
    "providers_per_100k",
    "density_rank",
    "density_percentile",
    "predicted_provider_density",
    "regression_residual_diagnostic",
    "taxonomy_diversity",
}

# the published state ranking, which needs no model
INPUT_FILE: Final[Path] = Path("data/model_outputs/state_density_ranking.csv")

# evaluation output, read only to print the model's skill on the diagnostic figure
EVALUATION_FILE: Final[Path] = Path("data/model_outputs/evaluation_results.json")

# how many states the bar chart shows
THINNEST_STATE_COUNT: Final[int] = 10

# sequential density scale built from the brand supply ramp, thinnest to densest
DENSITY_COLORSCALE: Final[list[list]] = [
    [index / (len(SUPPLY_TIER_RAMP) - 1), color]
    for index, color in enumerate(SUPPLY_TIER_RAMP)
]


def validate_columns(df: pd.DataFrame) -> None:
    """
    Stop early if the ranking is missing fields the dashboard needs.

    Parameters
    df : pd.DataFrame to check.

    Raises
    ValueError listing the missing columns when any are absent.
    """
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"state_density_ranking.csv missing: {sorted(missing)}")


def load_state_density_ranking(path: Path = INPUT_FILE) -> pd.DataFrame:
    """
    Load the published state density ranking, thinnest state first.

    This replaces the old loader, which read the regression output and then
    recomputed or joined risk tiers. There are no tiers now.

    Parameters
    path : Path to the state density ranking csv.

    Returns
    pd.DataFrame ready to feed into any chart builder in this module.
    """
    df = pd.read_csv(path)
    validate_columns(df)

    # drop rows the dashboard cannot render
    before = df.shape[0]
    df = df.dropna(subset=["practice_state", "providers_per_100k"]).copy()
    df.attrs["dropped_rows"] = before - df.shape[0]

    return df.sort_values("density_rank").reset_index(drop=True)


def read_cross_validated_r2(path: Path = EVALUATION_FILE) -> float | None:
    """Read the model's cross validated R2 so the diagnostic figure can print it."""
    if not path.exists():
        return None

    with open(path) as handle:
        return json.load(handle).get("cv5_r2_mean")


def national_density(df: pd.DataFrame) -> float:
    """Providers per 100k across every state, used as the reference line."""
    return df["provider_count"].sum() / df["state_population"].sum() * 100000


def _shared_residual_range(df: pd.DataFrame) -> float:
    """Pick a symmetric residual range so zero stays at the center of the diagnostic scale."""
    residual = df["regression_residual_diagnostic"]
    return max(abs(residual.min()), abs(residual.max()))


def build_bar(
    df: pd.DataFrame,
    selected_states: list[str] | None = None,
) -> go.Figure:
    """
    Build the horizontal bar chart of the thinnest states by provider density.

    Lowest density sits at the top, matching the county chart. Bars are shaded
    along the supply ramp by density rather than by a tier, because there are
    no state tiers. A dashed line marks the national rate.

    Parameters
    df : pd.DataFrame from load_state_density_ranking.
    selected_states : list of state abbreviations to filter to, from a map click.

    Returns
    plotly Figure.
    """
    national = national_density(df)

    # plotly draws the first row at the bottom, so sort descending to put the
    # thinnest state at the top where the title points
    if selected_states:
        subset = df[df["practice_state"].isin(selected_states)].sort_values(
            "providers_per_100k", ascending=False
        )
        title_text = f"Provider Density for {', '.join(selected_states)}"
    else:
        subset = df.nsmallest(THINNEST_STATE_COUNT, "providers_per_100k").sort_values(
            "providers_per_100k", ascending=False
        )
        title_text = f"{THINNEST_STATE_COUNT} Thinnest States by Provider Density"

    bar_colors = _density_ramp_colors(subset["providers_per_100k"], df)

    fig = go.Figure(go.Bar(
        x=subset["providers_per_100k"],
        y=subset["practice_state"],
        orientation="h",
        text=subset["providers_per_100k"].round(1),
        textposition="outside",
        textfont={"size": 12, "color": COLORS["text"]},
        marker={"color": bar_colors},
        customdata=subset["density_rank"],
        hovertemplate=(
            "<b>%{y}</b><br>%{x:.2f} per 100k<br>"
            "National rank: %{customdata} of 51<extra></extra>"
        ),
    ))

    x_max = max(subset["providers_per_100k"].max(), national) if len(subset) else national

    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": title_text, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        xaxis={"title": "Providers per 100k residents", "range": [0, x_max * 1.18]},
        yaxis={"title": ""},
        shapes=[{
            "type": "line", "x0": national, "x1": national,
            "y0": -0.5, "y1": len(subset) - 0.5,
            "line": {"color": COLORS["text_muted"], "width": 1.5, "dash": "dash"},
        }],
        annotations=[{
            "x": national, "y": len(subset) - 0.5,
            "text": f"National {national:.1f}",
            "showarrow": False, "yshift": 12,
            "font": {"size": 10, "color": COLORS["text_muted"]},
        }],
    )
    apply_axis_defaults(fig)
    return fig


def _density_ramp_colors(values: pd.Series, df: pd.DataFrame) -> list[str]:
    """Shade each bar along the supply ramp by where its density sits nationally."""
    low = df["providers_per_100k"].min()
    high = df["providers_per_100k"].max()
    span = high - low if high > low else 1.0

    colors = []
    for value in values:
        position = (value - low) / span
        index = min(int(position * len(SUPPLY_TIER_RAMP)), len(SUPPLY_TIER_RAMP) - 1)
        colors.append(SUPPLY_TIER_RAMP[index])

    return colors


def build_scatter(df: pd.DataFrame) -> go.Figure:
    """
    Model diagnostic: predicted against actual provider density.

    This figure is a diagnostic, not a finding. The dashed diagonal is the
    ideal fit line, and the spread around it is the point: the model explains
    little of the variation between states. Its cross validated R2 is printed
    on the figure so the scatter cannot be read as more than it is.

    Parameters
    df : pd.DataFrame from load_state_density_ranking.

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
            "color": df["regression_residual_diagnostic"],
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

    # print the model's skill on the figure so nobody reads the scatter as a result
    cv_r2 = read_cross_validated_r2()
    skill_text = (
        f"Model diagnostic only. Cross validated R2 {cv_r2:+.3f} across 5 folds"
        if cv_r2 is not None
        else "Model diagnostic only"
    )
    annotations.append({
        "x": 0.02, "y": 1.02, "xref": "paper", "yref": "paper",
        "text": skill_text,
        "showarrow": False, "xanchor": "left", "yanchor": "bottom",
        "font": {"size": 11, "color": COLORS["text_muted"]},
    })

    fig.update_layout(
        **BASE_LAYOUT,
        title={
            "text": "Model Diagnostic: Predicted against Actual Density",
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
    top = df.nlargest(1, "regression_residual_diagnostic").iloc[0]
    annotations.append({
        **anno_base,
        "x": top["predicted_provider_density"], "y": top["providers_per_100k"],
        "text": f"<b>{top['practice_state']}</b><br>+{top['regression_residual_diagnostic']:.1f} above expected",
        "arrowcolor": COLORS["pos_strong"], "bordercolor": COLORS["pos_strong"],
        "font": {"size": 11, "color": COLORS["pos_strong"]},
        "ax": 50, "ay": 40,
    })

    # two biggest under supply states (most negative residuals)
    for i, (_, row) in enumerate(df.nsmallest(2, "regression_residual_diagnostic").iterrows()):
        offsets = [{"ax": -60, "ay": -30}, {"ax": -60, "ay": 35}]
        annotations.append({
            **anno_base,
            "x": row["predicted_provider_density"], "y": row["providers_per_100k"],
            "text": f"<b>{row['practice_state']}</b><br>{row['regression_residual_diagnostic']:.1f} below expected",
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
) -> go.Figure:
    """
    US choropleth on a continuous provider density scale.

    This used to offer a second mode that coloured states by risk tier. That
    classification is retired, so the map shows observed density only, shaded
    along the supply ramp from thinnest to densest.

    Parameters
    df : pd.DataFrame from load_state_density_ranking.
    selected_state : str or None
        State abbreviation passed in from a map click. Highlights the
        selected state with a thicker border and dims the others.

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

    title_text = "Reproductive Health Provider Density by State"
    if selected_state:
        row = df[df["practice_state"] == selected_state]
        if len(row) > 0:
            title_text = (
                f"{selected_state}: {row.iloc[0]['providers_per_100k']:.1f} per 100k, "
                f"rank {int(row.iloc[0]['density_rank'])} of {n}"
            )

    fig = go.Figure(go.Choropleth(
        locations=states,
        z=df["providers_per_100k"],
        locationmode="USA-states",
        colorscale=DENSITY_COLORSCALE,
        marker=marker,
        colorbar={
            "title": "Per 100k", "thickness": 14, "len": 0.75,
            "x": 1.01, "y": 0.5,
            "tickfont": {"size": 11}, "title_font": {"size": 12},
        },
        customdata=df["density_rank"],
        hovertemplate=(
            "<b>%{location}</b><br>%{z:.2f} per 100k<br>"
            "National rank: %{customdata} of 51<extra></extra>"
        ),
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
