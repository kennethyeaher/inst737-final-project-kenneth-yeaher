from __future__ import annotations

import os
from pathlib import Path
from typing import Final, Optional

import pandas as pd
import plotly.express as px
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
 
CHART_HEIGHT: Final[int] = 420
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

    fig = go.Figure(go.Choropleth(
        locations=df["practice_state"],
        z=df["residual"],
        locationmode="USA-states",
        colorscale=UNIFIED_COLORSCALE,
        zmin=-res_max,
        zmax=res_max,
        zmid=0,
        marker={"line": {"color": "white", "width": 1.5}},
        colorbar={"title": "Access Gap", "thickness": 14, "len": 0.6},
        hovertemplate="<b>%{location}</b><br>Residual: %{z:.2f}<extra></extra>",
    ))

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
                "colorscale": [
                    [0.0, COLORS["neg_strong"]],
                    [0.5, COLORS["neg_mid"]],
                    [1.0, "#fddbc7"],
                ],
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
        "ax": 50,
        "ay": 40,
    })

    # two most underserved states with staggered offsets
    offsets = [{"ax": -60, "ay": -30}, {"ax": -60, "ay": 35}]

    for i, (_, row) in enumerate(df.nsmallest(2, "residual").iterrows()):
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
            **offsets[i],
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
        zmin=-res_max,
        zmax=res_max,
        zmid=0,
        colorbar={"title": "Access Gap", "thickness": 14, "len": 0.6},
        hovertemplate="<b>%{location}</b><br>Residual: %{z:.2f}<extra></extra>",
    ))

    fig.update_layout(
        **{**BASE_LAYOUT, "height": 520, "margin": {"l": 0, "r": 0, "t": 50, "b": 0}},
        title={"text": "State-Level Access Gap Map", "font": {"size": 15}},
        geo=dict(
            scope="usa",
            projection_type="albers usa",
            showland=True,
            landcolor="rgb(245,245,245)",
            showlakes=True,
            lakecolor="rgb(232,240,250)",
        ),
    )
    return fig      

# summary and ui components

def generate_summary(df: pd.DataFrame) -> list:
    """Produce a styled executive summary with bolded key figures."""
    n_states = df["practice_state"].nunique()
    if n_states == 0:
        return [html.Span("No state-level data available for summary.")]

    avg_density = df["providers_per_100k"].mean()
    med_density = df["providers_per_100k"].median()

    underserved = df[df["residual"] < 0]
    n_under = len(underserved)
    pct_under = round(n_under / n_states * 100)

    worst_3 = df.nsmallest(3, "residual")
    worst_names = ", ".join(worst_3["practice_state"].tolist())
    worst_avg_gap = worst_3["residual"].mean()

    best = df.nlargest(1, "residual").iloc[0]

    b = lambda text: html.B(text, style={"color": COLORS["text"]})

    return [
        html.Span([
            "Across ", b(f"{n_states} states"), " analyzed, the average provider density is ",
            b(f"{avg_density:.1f}"), " per 100k residents (median: ",
            b(f"{med_density:.1f}"), ").",
        ]),
        html.Br(), html.Br(),
        html.Span([
            b(f"{n_under} states ({pct_under}%)"),
            " fall below model-predicted supply levels, indicating potential access gaps. ",
            "The three most underserved — ",
            b(worst_names),
            " — average a residual of ",
            b(f"{worst_avg_gap:.2f}"),
            ", meaning actual provider supply is substantially below expectations.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            b(best["practice_state"]),
            " shows the strongest over-supply at ",
            b(f"+{best['residual']:.2f}"),
            ".",
        ]),
    ]


def _kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    color: str = COLORS["text"],
    accent: str = COLORS["card_border"],
) -> dbc.Card:
    """Reusable KPI card with colored top accent border."""
    children = [
        html.P(
            title,
            className="mb-1",
            style={
                "fontSize": "0.85rem",
                "color": COLORS["text_muted"],
                "fontWeight": "600",
                "textTransform": "uppercase",
                "letterSpacing": "0.05em",
            },
        ),
        html.H2(
            value,
            className="mb-0",
            style={"fontSize": "2.2rem", "fontWeight": "700", "color": color},
        ),
    ]

    if subtitle:
        children.append(html.P(
            subtitle,
            className="mb-0 mt-1",
            style={"fontSize": "0.8rem", "color": COLORS["text_muted"]},
        ))

    return dbc.Card(
        dbc.CardBody(children),
        style={
            **CARD_STYLE,
            "textAlign": "center",
            "borderTop": f"4px solid {accent}",
        },
    )


def _chart_card(graph_id: str, figure: go.Figure) -> dbc.Card:
    """Wrap a Plotly figure in a styled card with hidden mode bar."""
    return dbc.Card(
        dcc.Graph(id=graph_id, figure=figure, config={"displayModeBar": False}),
        style=CARD_STYLE,
    )

# interactive dash dashboard

def build_access_dashboard(df: pd.DataFrame, *, debug: bool = False) -> None:
    """
    Interactive Dash dashboard replacing the old static Plotly version.
    Launches a local server at http://127.0.0.1:8050
    """
    validate_columns(df, {"practice_state", "providers_per_100k",
                          "predicted_provider_density", "residual"})

    print("[VIS] Launching interactive Dash dashboard...")
    chart_df = df.copy()

    # pre compute kpis

    n_states = int(chart_df["practice_state"].nunique())
    avg_dens = chart_df["providers_per_100k"].mean()
    med_dens = chart_df["providers_per_100k"].median()
    worst_row = chart_df.nsmallest(1, "residual").iloc[0]

    # initialize dash

    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Ovara — Access Dashboard",
    )

    app.layout = dbc.Container(
        [
            # header

            dbc.Row(dbc.Col(html.Div(
                [
                    html.H3(
                        "U.S. Specialist Access Dashboard",
                        className="mb-0",
                        style={"fontWeight": "700"},
                    ),
                    html.P(
                        "Residuals highlight where provider supply falls below "
                        "or exceeds model expectations. Click a state on the "
                        "map to filter the bar chart.",
                        className="mb-0",
                        style={"color": COLORS["text_muted"], "fontSize": "0.9rem"},
                    ),
                ],
                style={"textAlign": "center", "padding": "18px 0 10px 0"},
            ), width=12)),

            html.Hr(style={"margin": "0 0 16px 0", "borderColor": COLORS["card_border"]}),

            # kpi row

            dbc.Row(
                [
                    dbc.Col(_kpi_card(
                        "States Analyzed",
                        str(n_states),
                        accent=COLORS["pos_strong"],
                    ), md=4),
                    dbc.Col(_kpi_card(
                        "Avg Providers / 100k",
                        f"{avg_dens:.1f}",
                        subtitle=f"Median: {med_dens:.1f}",
                        accent=COLORS["accent"],
                    ), md=4),
                    dbc.Col(_kpi_card(
                        "Most Underserved",
                        worst_row["practice_state"],
                        subtitle=f"Gap: {worst_row['residual']:.2f}",
                        color=COLORS["kpi_bad"],
                        accent=COLORS["kpi_bad"],
                    ), md=4),
                ],
                className="g-3 mb-3",
            ),

            # charts bar and scatter

            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card([
                            dcc.Graph(
                                id="bar-chart",
                                figure=build_dashboard_bar(chart_df),
                                config={"displayModeBar": False},
                            ),
                            html.Div(
                                dbc.Button(
                                    "Reset filter",
                                    id="reset-bar",
                                    size="sm",
                                    color="secondary",
                                    outline=True,
                                ),
                                style={"textAlign": "right", "padding": "6px 12px 10px 0"},
                            ),
                        ], style=CARD_STYLE),
                        md=5,
                    ),
                    dbc.Col(
                        _chart_card("scatter-chart", build_dashboard_scatter(chart_df)),
                        md=7,
                    ),
                ],
                className="g-3 mb-3",
            ),

            # map

            dbc.Row(
                dbc.Col(
                    _chart_card("choropleth", build_dashboard_choropleth(chart_df)),
                    width=12,
                ),
                className="mb-3",
            ),

            # executive summary

            dbc.Row(
                dbc.Col(dbc.Card(
                    dbc.CardBody([
                        html.H6(
                            "Executive Summary",
                            style={
                                "fontWeight": "700",
                                "textTransform": "uppercase",
                                "letterSpacing": "0.05em",
                                "color": COLORS["text_muted"],
                                "fontSize": "0.8rem",
                            },
                        ),
                        html.Div(
                            generate_summary(chart_df),
                            id="summary-text",
                            style={
                                "fontSize": "0.95rem",
                                "lineHeight": "1.7",
                                "color": COLORS["text"],
                                "marginBottom": "0",
                            },
                        ),
                    ]),
                    style={**CARD_STYLE, "backgroundColor": "#f0f4f8"},
                ), width=12),
                className="mb-4",
            ),
        ],
        fluid=True,
        style={
            "backgroundColor": COLORS["bg"],
            "fontFamily": FONT_STACK,
            "maxWidth": "1440px",
            "paddingBottom": "40px",
        },
    )

    # callback click map to filter bar and reset button restores

    @app.callback(
        Output("bar-chart", "figure"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def update_bar(click_data, _n_clicks):
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return build_dashboard_bar(chart_df)

        clicked_state = click_data["points"][0]["location"]
        return build_dashboard_bar(chart_df, selected_states=[clicked_state])

    # launch

    port = int(os.environ.get("DASH_PORT", 8050))
    print(f"[VIS] Dashboard running at http://127.0.0.1:{port}")
    app.run(debug=debug, port=port)

# workflow manager

def run_interactive_visualizations() -> None:
    """Run the full interactive visualization workflow."""
    df = load_regression_results()

    # static html chart exports

    top_underserved_chart(df)
    top_overserved_chart(df)
    residual_ranking_chart(df)
    predicted_vs_actual_chart(df)
    state_choropleth(df)
    annotated_predicted_vs_actual_chart(df)

    print("[VIS] ===== STATIC VISUALIZATIONS COMPLETE =====")

    # interactive dashboard launches server

    build_access_dashboard(df, debug=True)

if __name__ == "__main__":
    run_interactive_visualizations()
    