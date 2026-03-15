from __future__ import annotations
 
import os
from typing import Final
 
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, ctx
import dash_bootstrap_components as dbc


# file path 

INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_DIR = Path("data/visualizations")

__all__ = ["build_access_dashboard"]
 
# constriants 
 
REQUIRED_COLUMNS: Final[set[str]] = {
    "practice_state",
    "providers_per_100k",
    "predicted_provider_density",
    "residual",
}
 
#  unified color system, defined once, referenced everywhere 

COLORS: Final[dict[str, str]] = {
    # diverging palette (red = underserved, blue = over-served)
    "neg_strong":  "#b2182b",
    "neg_mid":     "#ef8a62",
    "neutral":     "#f7f7f7",
    "pos_mid":     "#67a9cf",
    "pos_strong":  "#2166ac",
 
    # UI chrome
    "bg":          "#f8f9fa",
    "card_bg":     "#ffffff",
    "card_border": "#e0e0e0",
    "text":        "#212529",
    "text_muted":  "#6c757d",
    "accent":      "#2ca25f",
    "kpi_bad":     "#c0392b",
    "kpi_good":    "#27ae60",
}
 
UNIFIED_COLORSCALE: Final[list[list]] = [
    [0.0,  COLORS["neg_strong"]],
    [0.25, COLORS["neg_mid"]],
    [0.5,  COLORS["neutral"]],
    [0.75, COLORS["pos_mid"]],
    [1.0,  COLORS["pos_strong"]],
]
 
# reusable layout tokens 
FONT_STACK: Final[str] = "Inter, Segoe UI, sans-serif"
 
CHART_HEIGHT: Final[int] = 380
MAP_HEIGHT: Final[int] = 420
 
CARD_STYLE: Final[dict] = {
    "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "10px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.06)",
}
 
CHART_MARGIN: Final[dict] = {"l": 10, "r": 20, "t": 50, "b": 40}
 
BASE_LAYOUT: Final[dict] = {
    "template": "plotly_white",
    "margin": CHART_MARGIN,
    "height": CHART_HEIGHT,
    "font": {"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
}
 
# validation
 
def _validate_dataframe(df: pd.DataFrame) -> None:
    """Raise early with a clear message if the DataFrame is malformed."""
    if df.empty:
        raise ValueError("DataFrame is empty — cannot build dashboard.")
 
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {', '.join(sorted(missing))}. "
            f"Expected: {', '.join(sorted(REQUIRED_COLUMNS))}"
        )
 
 
def _shared_range(df: pd.DataFrame) -> float:
    """Symmetric color range so 0 sits at the palette center."""
    return max(abs(df["residual"].min()), abs(df["residual"].max()))


# required columns 

REQUIRED_COLUMNS = {
    "practice_state",
    "provider_count",
    "metro_population",
    "providers_per_100k",
    "predicted_provider_density",
    "residual",
    "taxonomy_diversity",
    "recent_provider_growth",
}

# helpers: 

def validate_columns(df: pd.DataFrame, required: set[str]) -> None:
    """Fail fast if the regression results file is missing required fields."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"regression_results.csv is missing required columns: {sorted(missing)}")
    
def apply_standard_layout(fig, title: str, x_title: Optional[str] = None, y_title: Optional[str] = None):
    """Apply a consistent Plotly layout style across charts."""
    fig.update_layout(
        title=title,
        template="plotly_white",
        xaxis_title=x_title,
        yaxis_title=y_title,
        title_x=0.5,
        margin=dict(l=40, r=40, t=70, b=40),
    )
    return fig

def save_html(fig, filename: str) -> None:
    """Save interactive Plotly chart as HTML."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.write_html(OUTPUT_DIR / filename, include_plotlyjs="cdn")
    print(f"[VIS] Saved → {filename}")

# load stage

def load_regression_results() -> pd.DataFrame:
    """
    Load saved regression outputs for interactive visualization.
    Keep only rows with valid geographic and modeled values.
    """
    print("\n[VIS] ===== BUILDING INTERACTIVE VISUALIZATIONS =====")
    print("[VIS] Loading regression results...")

    df = pd.read_csv(INPUT_FILE)
    validate_columns(df, REQUIRED_COLUMNS)

    df = df.dropna(
        subset=[
            "practice_state",
            "providers_per_100k",
            "predicted_provider_density",
            "residual",
        ]
    ).copy()

    print(f"[VIS] Rows available for visualization: {df.shape[0]}")
    return df

# visualization stage


def residual_ranking_chart(df: pd.DataFrame) -> None:
    """
    Bar chart ranking states by residual.
    More negative residual implies lower than expected provider density.
    """
    chart_df = df.sort_values("residual").copy()

    fig = px.bar(
        chart_df,
        x="practice_state",
        y="residual",
        color="residual",
        color_continuous_scale="RdBu",
        hover_data={
            "providers_per_100k": ":.2f",
            "predicted_provider_density": ":.2f",
            "metro_population": ":,.0f",
            "practice_state": False,
        },
    )

    fig = apply_standard_layout(
        fig,
        title="Provider Access Residual Ranking by State",
        x_title="State",
        y_title="Residual (Actual - Predicted Density)",
    )

    save_html(fig, "residual_ranking_chart.html")

def predicted_vs_actual_chart(df: pd.DataFrame) -> None:
    """
    Scatterplot comparing actual vs predicted provider density.
    Helps show how closely the baseline regression tracks observed density.
    """
    fig = px.scatter(
        df,
        x="predicted_provider_density",
        y="providers_per_100k",
        color="residual",
        color_continuous_scale="RdBu",
        hover_name="practice_state",
        hover_data={
            "metro_population": ":,.0f",
            "taxonomy_diversity": ":.2f",
            "recent_provider_growth": ":.0f",
        },
    )

    min_val = min(df["predicted_provider_density"].min(), df["providers_per_100k"].min())
    max_val = max(df["predicted_provider_density"].max(), df["providers_per_100k"].max())

    fig.add_trace(
        go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode="lines",
            name="Ideal Fit",
            line=dict(dash="dash"),
            showlegend=True,
        )
    )

    fig = apply_standard_layout(
        fig,
        title="Predicted vs Actual Provider Density",
        x_title="Predicted Providers per 100k",
        y_title="Actual Providers per 100k",
    )

    save_html(fig, "predicted_vs_actual_density.html")

def state_choropleth(df: pd.DataFrame) -> None:
    """
    U.S. state choropleth using provider density.
    This gives a more intuitive geographic access view than a standard bar chart.
    """
    fig = px.choropleth(
        df,
        locations="practice_state",
        locationmode="USA-states",
        color="providers_per_100k",
        scope="usa",
        hover_name="practice_state",
        hover_data={
            "provider_count": ":,.0f",
            "metro_population": ":,.0f",
            "residual": ":.2f",
        },
        color_continuous_scale="Blues",
    )

    fig = apply_standard_layout(
        fig,
        title="Provider Density by State",
    )

    save_html(fig, "state_provider_density_map.html")

def top_underserved_chart(df: pd.DataFrame) -> None:
    """
    Create a ranked bar chart of the most underserved states.

    More negative residual values indicate that actual provider density
    is lower than the model predicted, which signals potential access gaps.
    """
    chart_df = (
        df.nsmallest(10, "residual")
        .copy()
        .sort_values("residual", ascending=True)
    )

    chart_df["access_gap_label"] = chart_df["residual"].round(2)

    fig = px.bar(
        chart_df,
        x="practice_state",
        y="residual",
        color="residual",
        color_continuous_scale="Reds_r",
        text="access_gap_label",
        hover_data={
            "providers_per_100k": ":.2f",
            "predicted_provider_density": ":.2f",
            "provider_count": ":,.0f",
            "metro_population": ":,.0f",
            "practice_state": False,
            "access_gap_label": False,
        },
    )

    fig = apply_standard_layout(
        fig,
        title="Top 10 Most Underserved States by Provider Access Residual",
        x_title="State",
        y_title="Residual (Actual - Predicted Density)",
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        coloraxis_showscale=False,
        uniformtext_minsize=8,
        uniformtext_mode="hide",
    )

    save_html(fig, "top_underserved_states.html")

def top_overserved_chart(df: pd.DataFrame) -> None:
    """
    Create a ranked bar chart of the most over-served states.

    More positive residual values indicate that actual provider density
    is higher than the model predicted, which suggests stronger than expected supply.
    """
    chart_df = (
        df.nlargest(10, "residual")
        .copy()
        .sort_values("residual", ascending=False)
    )

    chart_df["access_surplus_label"] = chart_df["residual"].round(2)

    fig = px.bar(
        chart_df,
        x="practice_state",
        y="residual",
        color="residual",
        color_continuous_scale="Blues",
        text="access_surplus_label",
        hover_data={
            "providers_per_100k": ":.2f",
            "predicted_provider_density": ":.2f",
            "provider_count": ":,.0f",
            "metro_population": ":,.0f",
            "practice_state": False,
            "access_surplus_label": False,
        },
    )

    fig = apply_standard_layout(
        fig,
        title="Top 10 Most Over Served States by Provider Access Residual",
        x_title="State",
        y_title="Residual (Actual - Predicted Density)",
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        coloraxis_showscale=False,
        uniformtext_minsize=8,
        uniformtext_mode="hide",
    )

    save_html(fig, "top_overserved_states.html")


def annotated_predicted_vs_actual_chart(df: pd.DataFrame) -> None:
    """
    Create a predicted vs actual provider density scatterplot and label
    the most important underserved and overserved outliers.

    Points below the ideal fit line indicate lower actual provider density
    than predicted. Points above the line indicate stronger than expected supply.
    """
    outlier_count = 5
    chart_df = df.copy()

    # identify strongest negative and positive residual outliers
    underserved = chart_df.nsmallest(outlier_count, "residual").copy()
    underserved["label_text"] = underserved["practice_state"] + " (underserved)"

    overserved = chart_df.nlargest(outlier_count, "residual").copy()
    overserved["label_text"] = overserved["practice_state"] + " (overserved)"

    labeled_outliers = (
        pd.concat([underserved, overserved], ignore_index=True)
        .drop_duplicates(subset="practice_state")
        .copy()
    )

    # main scatterplot
    fig = px.scatter(
        chart_df,
        x="predicted_provider_density",
        y="providers_per_100k",
        color="residual",
        color_continuous_scale="RdBu",
        hover_name="practice_state",
        hover_data={
            "metro_population": ":,.0f",
            "taxonomy_diversity": ":.2f",
            "recent_provider_growth": ":.0f",
            "provider_count": ":,.0f",
            "residual": ":.2f",
        },
    )

    # add ideal fit reference line where actual = predicted
    
    axis_min = min(
        chart_df["predicted_provider_density"].min(),
        chart_df["providers_per_100k"].min(),
    )
    axis_max = max(
        chart_df["predicted_provider_density"].max(),
        chart_df["providers_per_100k"].max(),
    )

    fig.add_shape(
        type="line",
        x0=axis_min,
        y0=axis_min,
        x1=axis_max,
        y1=axis_max,
        line=dict(dash="dash", width=2),
    )

    # label only the most meaningful outliers
    
    fig.add_scatter(
        x=labeled_outliers["predicted_provider_density"],
        y=labeled_outliers["providers_per_100k"],
        mode="text",
        text=labeled_outliers["label_text"],
        textposition="top center",
        showlegend=False,
    )

    fig = apply_standard_layout(
        fig,
        title=(
            "Predicted vs Actual Provider Density"
            "<br><sup>Points below the dashed line have lower provider density than expected</sup>"
        ),
        x_title="Predicted Providers per 100k",
        y_title="Actual Providers per 100k",
    )

    fig.update_layout(
        coloraxis_colorbar_title="Residual",
        margin=dict(l=40, r=40, t=90, b=40),
    )

    save_html(fig, "annotated_predicted_vs_actual_density.html")

# dashboard figure builders

def _shared_range(df: pd.DataFrame) -> float:
    """Symmetric color range so 0 sits at the palette center."""
    return max(abs(df["residual"].min()), abs(df["residual"].max()))


def build_dashboard_bar(
    df: pd.DataFrame,
    selected_states: list[str] | None = None,
) -> go.Figure:
    """
    Horizontal bar showing top 10 most underserved states by default.
    When selected_states is provided via map click, filters to those.
    """
    res_max = _shared_range(df)

    if selected_states:
        subset = (
            df[df["practice_state"].isin(selected_states)]
            .copy()
            .sort_values("residual", ascending=True)
        )
        title_text = f"Access Gap — {', '.join(selected_states)}"
    else:
        subset = (
            df.nsmallest(10, "residual")
            .copy()
            .sort_values("residual", ascending=True)
        )
        title_text = "Top 10 Most Underserved States"

    x_min = subset["residual"].min() if len(subset) > 0 else -4

    fig = go.Figure(
        go.Bar(
            x=subset["residual"],
            y=subset["practice_state"],
            orientation="h",
            text=subset["residual"].round(2),
            textposition="outside",
            textfont={"size": 12, "color": COLORS["text"]},
            marker={
                "color": subset["residual"],
                "colorscale": UNIFIED_COLORSCALE,
                "cmin": -res_max,
                "cmax": res_max,
                "showscale": False,
            },
            hovertemplate="<b>%{y}</b><br>Residual: %{x:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": title_text, "font": {"size": 15}},
        xaxis={"title": "Residual (actual − predicted)", "range": [x_min * 1.30, 0.3]},
        yaxis={"title": ""},
    )
    return fig


def _build_outlier_annotations(
    df: pd.DataFrame,
    axis_min: float,
    axis_max: float,
    pad: float,
) -> list[dict]:
    """Annotation dicts for the top positive and bottom two negative outliers."""
    annotations: list[dict] = []

    # strongest over served state
    top_pos = df.nlargest(1, "residual").iloc[0]
    annotations.append({
        "x": top_pos["predicted_provider_density"],
        "y": top_pos["providers_per_100k"],
        "text": (
            f"<b>{top_pos['practice_state']}</b><br>"
            f"+{top_pos['residual']:.1f} above expected"
        ),
        "showarrow": True,
        "arrowhead": 2,
        "arrowcolor": COLORS["pos_strong"],
        "font": {"size": 11, "color": COLORS["pos_strong"]},
        "bgcolor": "rgba(255,255,255,0.85)",
        "bordercolor": COLORS["pos_strong"],
        "borderwidth": 1,
        "ax": 40,
        "ay": -40,
    })

    # two most underserved states
    for _, row in df.nsmallest(2, "residual").iterrows():
        annotations.append({
            "x": row["predicted_provider_density"],
            "y": row["providers_per_100k"],
            "text": (
                f"<b>{row['practice_state']}</b><br>"
                f"{row['residual']:.1f} below expected"
            ),
            "showarrow": True,
            "arrowhead": 2,
            "arrowcolor": COLORS["neg_strong"],
            "font": {"size": 11, "color": COLORS["neg_strong"]},
            "bgcolor": "rgba(255,255,255,0.85)",
            "bordercolor": COLORS["neg_strong"],
            "borderwidth": 1,
            "ax": -50,
            "ay": -35,
        })

    # fit line label
    mid = (axis_min + axis_max) / 2
    annotations.append({
        "x": mid + pad * 2,
        "y": mid + pad * 2,
        "text": "Ideal: actual = predicted",
        "showarrow": False,
        "font": {"size": 11, "color": COLORS["accent"], "family": FONT_STACK},
        "bgcolor": "rgba(255,255,255,0.8)",
    })

    return annotations


def build_dashboard_scatter(df: pd.DataFrame) -> go.Figure:
    """
    Predicted vs actual scatter with unified coloring,
    ideal fit line label, and annotated outliers.
    """
    res_max = _shared_range(df)

    axis_min = min(
        df["predicted_provider_density"].min(),
        df["providers_per_100k"].min(),
    )
    axis_max = max(
        df["predicted_provider_density"].max(),
        df["providers_per_100k"].max(),
    )
    pad = (axis_max - axis_min) * 0.08
    axis_range = [axis_min - pad, axis_max + pad]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=axis_range,
        y=axis_range,
        mode="lines",
        line={"dash": "dash", "width": 2, "color": COLORS["accent"]},
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=df["predicted_provider_density"],
        y=df["providers_per_100k"],
        mode="markers",
        text=df["practice_state"],
        marker={
            "size": 11,
            "color": df["residual"],
            "colorscale": UNIFIED_COLORSCALE,
            "cmin": -res_max,
            "cmax": res_max,
            "showscale": True,
            "colorbar": {"title": "Residual", "thickness": 12, "len": 0.75},
            "line": {"width": 0.6, "color": "white"},
        },
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Predicted: %{x:.2f}<br>"
            "Actual: %{y:.2f}<extra></extra>"
        ),
        showlegend=False,
    ))

    annotations = _build_outlier_annotations(df, axis_min, axis_max, pad)

    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Predicted vs Actual Provider Density", "font": {"size": 15}},
        xaxis={"title": "Predicted Providers per 100k", "range": axis_range},
        yaxis={"title": "Actual Providers per 100k", "range": axis_range},
        annotations=annotations,
    )
    return fig


def build_dashboard_choropleth(df: pd.DataFrame) -> go.Figure:
    """Full width US choropleth with unified color scale."""
    res_max = _shared_range(df)

    fig = go.Figure(go.Choropleth(
        locations=df["practice_state"],
        z=df["residual"],
        locationmode="USA-states",
        colorscale=UNIFIED_COLORSCALE,
        cmin=-res_max,
        cmax=res_max,
        zmid=0,
        colorbar={"title": "Access Gap", "thickness": 14, "len": 0.6},
        hovertemplate="<b>%{location}</b><br>Residual: %{z:.2f}<extra></extra>",
    ))

    fig.update_geos(
        scope="usa",
        projection_type="albers usa",
        showland=True,
        landcolor="rgb(245,245,245)",
        showlakes=True,
        lakecolor="rgb(232,240,250)",
    )

    fig.update_layout(
        **{**BASE_LAYOUT, "height": MAP_HEIGHT},
        title={"text": "State-Level Access Gap Map", "font": {"size": 15}},
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
    )
    return fig


def build_access_dashboard(df: pd.DataFrame) -> None:
    """
    Build an executive style access dashboard that summarizes:
    1. Core KPIs
    2. Most underserved states
    3. Model fit (predicted vs actual density)
    4. Geographic access gaps across states

    Residuals are used as the main access gap signal:
    more negative residuals indicate lower actual provider density than expected.
    """
    print("[VIS] Building executive access dashboard...")

    chart_df = df.copy()

    # kpi values

    states_analyzed = int(chart_df["practice_state"].nunique())
    avg_density = round(chart_df["providers_per_100k"].mean(), 2)
    most_underserved_state = chart_df.nsmallest(1, "residual")["practice_state"].iloc[0]

    # ranking slice 

    underserved = (
        chart_df.nsmallest(10, "residual")
        .copy()
        .sort_values("residual", ascending=True)
    )
    underserved["residual_label"] = underserved["residual"].round(2)

    # scatter refrence line range 

    axis_min = min(
        chart_df["predicted_provider_density"].min(),
        chart_df["providers_per_100k"].min(),
    )
    axis_max = max(
        chart_df["predicted_provider_density"].max(),
        chart_df["providers_per_100k"].max(),
    )

    # build layout 

    fig = make_subplots(
        rows=3,
        cols=2,
        row_heights=[0.18, 0.42, 0.60],
        specs=[
            [{"type": "indicator"}, {"type": "indicator"}],
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "choropleth", "colspan": 2}, None],
        ],
        subplot_titles=(
            "States Analyzed",
            "Average Provider Density",
            "Top 10 Most Underserved States",
            "Predicted vs Actual Provider Density",
            "State-Level Access Gap Map",
        ),
        vertical_spacing=0.10,
        horizontal_spacing=0.08,
    )

    # kpi one 

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=states_analyzed,
            title={"text": "States Analyzed"},
        ),
        row=1,
        col=1,
    )

    # kpi two 
   
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=avg_density,
            delta={"reference": 0, "relative": False},
            title={"text": f"Avg Providers per 100k<br><sup>Most underserved: {most_underserved_state}</sup>"},
        ),
        row=1,
        col=2,
    )

    # panel one, underserved ranking

    fig.add_trace(
        go.Bar(
            x=underserved["residual"],
            y=underserved["practice_state"],
            orientation="h",
            text=underserved["residual_label"],
            textposition="outside",
            marker=dict(
                color=underserved["residual"],
                colorscale="Reds_r",
                showscale=False,
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Residual: %{x:.2f}<br>"
                "<extra></extra>"
            ),
            name="Residual",
        ),
        row=2,
        col=1,
    )

    # panel two, model fit scatter 

    fig.add_trace(
        go.Scatter(
            x=chart_df["predicted_provider_density"],
            y=chart_df["providers_per_100k"],
            mode="markers",
            text=chart_df["practice_state"],
            marker=dict(
                size=11,
                color=chart_df["residual"],
                colorscale="RdBu",
                showscale=True,
                colorbar=dict(
                    title="Residual",
                    len=0.38,
                    thickness=12,
                    x=1.02,
                    y=0.66,
                ),
                line=dict(width=0.5, color="white"),
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Predicted Density: %{x:.2f}<br>"
                "Actual Density: %{y:.2f}<br>"
                "Residual: %{marker.color:.2f}<br>"
                "<extra></extra>"
            ),
            name="States",
            showlegend=False,
        ),
        row=2,
        col=2,
    )

    # ideal fit line
    
    fig.add_trace(
        go.Scatter(
            x=[axis_min, axis_max],
            y=[axis_min, axis_max],
            mode="lines",
            line=dict(dash="dash", width=2, color="#2ca25f"),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=2,
        col=2,
    )

    # panel three, geograpic accesss gap map 

    fig.add_trace(
        go.Choropleth(
            locations=chart_df["practice_state"],
            z=chart_df["residual"],
            locationmode="USA-states",
            colorscale="RdBu",
            zmid=0,
            colorbar=dict(
                title="Access Gap",
                len=0.60,
                thickness=14,
                x=1.02,
                y=0.20,
            ),
            hovertemplate=(
                "<b>%{location}</b><br>"
                "Residual: %{z:.2f}<br>"
                "<extra></extra>"
            ),
            name="Access Gap",
        ),
        row=3,
        col=1,
    )

    # layout mgmt and polish 

    fig.update_layout(
        title=(
            "U.S. Specialist Access Dashboard"
            "<br><sup>Residuals highlight where provider supply is below or above model expectations</sup>"
        ),
        template="plotly_white",
        height=930,
        width=1400,
        title_x=0.5,
        margin=dict(l=35, r=40, t=95, b=30),
        font=dict(size=14),
    )

    fig.update_xaxes(title_text="Residual", row=2, col=1)
    fig.update_yaxes(title_text="", row=2, col=1)

    fig.update_xaxes(title_text="Predicted Providers per 100k", row=2, col=2)
    fig.update_yaxes(title_text="Actual Providers per 100k", row=2, col=2)

    fig.update_geos(
        scope="usa",
        projection_type="albers usa",
        showland=True,
        landcolor="rgb(245,245,245)",
        row=3,
        col=1,
    )

    save_html(fig, "access_decision_dashboard.html") 

# workflow manager

def run_interactive_visualizations() -> None:
    """Run the full interactive visualization workflow."""
    df = load_regression_results()

    top_underserved_chart(df)
    top_overserved_chart(df)
    residual_ranking_chart(df)
    predicted_vs_actual_chart(df)
    state_choropleth(df)
    annotated_predicted_vs_actual_chart(df)
    build_access_dashboard(df) 

    print("[VIS] ===== INTERACTIVE VISUALIZATIONS COMPLETE =====")

if __name__ == "__main__":
    run_interactive_visualizations()
