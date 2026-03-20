from __future__ import annotations
 
import os
from pathlib import Path
from typing import Final
 
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, ctx
import dash_bootstrap_components as dbc
 
# file paths
 
INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_DIR = Path("data/visualizations")
 
__all__ = ["build_access_dashboard"]

# unified color system
 
COLORS: Final[dict[str, str]] = {
    "neg_strong":  "#b2182b",
    "neg_mid":     "#ef8a62",
    "neutral":     "#f7f7f7",
    "pos_mid":     "#67a9cf",
    "pos_strong":  "#2166ac",
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
 
CARD_STYLE: Final[dict] = {
    "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "10px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.06)",
}
 
BASE_LAYOUT: Final[dict] = {
    "template": "plotly_white",
    "margin": {"l": 10, "r": 20, "t": 50, "b": 40},
    "height": CHART_HEIGHT,
    "font": {"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
}
 
CHART_CONFIG: Final[dict] = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "staticPlot": False,
}
 
MAP_CONFIG: Final[dict] = {
    **CHART_CONFIG,
    "staticPlot": False,
}
 
# required columns 

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

# helpers: 

def _validate(df: pd.DataFrame) -> None:
    """Fail fast if regression results are missing required fields."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"regression_results.csv missing: {sorted(missing)}")
 
 
def _shared_range(df: pd.DataFrame) -> float:
    """Symmetric color range so 0 sits at the palette center."""
    return max(abs(df["residual"].min()), abs(df["residual"].max()))
 
 
def _save_html(fig: go.Figure, filename: str) -> None:
    """Export a Plotly figure as standalone HTML."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.write_html(OUTPUT_DIR / filename, include_plotlyjs="cdn")
    print(f"[VIS] Saved → {filename}")

# load stage

def load_regression_results() -> pd.DataFrame:
    """Load regression outputs for reproductive health access visualization."""
    print("\n[VIS] ===== BUILDING INTERACTIVE VISUALIZATIONS =====")
 
    df = pd.read_csv(INPUT_FILE)
    _validate(df)
 
    df = df.dropna(
        subset=["practice_state", "providers_per_100k", "predicted_provider_density", "residual"]
    ).copy()
 
    print(f"[VIS] Rows available: {df.shape[0]}")
    return df

# visualization stage

def build_bar(
    df: pd.DataFrame,
    selected_states: list[str] | None = None,
) -> go.Figure:
    """Horizontal bar of top 10 underserved states, filterable by map click."""
    if selected_states:
        subset = df[df["practice_state"].isin(selected_states)].sort_values("residual")
        title_text = f"Access Gap — {', '.join(selected_states)}"
    else:
        subset = df.nsmallest(10, "residual").sort_values("residual")
        title_text = "Top 10 Most Underserved States"
 
    x_min = subset["residual"].min() if len(subset) > 0 else -4
 
    fig = go.Figure(go.Bar(
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
    ))
 
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": title_text, "font": {"size": 15}},
        xaxis={"title": "Residual (actual − predicted)", "range": [x_min * 1.30, 0.3]},
        yaxis={"title": ""},
    )
    return fig


def build_scatter(df: pd.DataFrame) -> go.Figure:
    """Predicted vs actual density with ideal fit line and outlier annotations."""
    res_max = _shared_range(df)
 
    axis_min = min(df["predicted_provider_density"].min(), df["providers_per_100k"].min())
    axis_max = max(df["predicted_provider_density"].max(), df["providers_per_100k"].max())
    pad = (axis_max - axis_min) * 0.08
    axis_range = [axis_min - pad, axis_max + pad]
 
    fig = go.Figure()
 
    # ideal fit line
    fig.add_trace(go.Scatter(
        x=axis_range, y=axis_range,
        mode="lines",
        line={"dash": "dash", "width": 2, "color": COLORS["accent"]},
        hoverinfo="skip", showlegend=False,
    ))
 
    # data points
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
 
    # outlier annotations
    annotations = []
    anno_base = {"showarrow": True, "arrowhead": 2, "borderwidth": 1, "bgcolor": "rgba(255,255,255,0.85)"}
 
    top = df.nlargest(1, "residual").iloc[0]
    annotations.append({
        **anno_base,
        "x": top["predicted_provider_density"], "y": top["providers_per_100k"],
        "text": f"<b>{top['practice_state']}</b><br>+{top['residual']:.1f} above expected",
        "arrowcolor": COLORS["pos_strong"], "bordercolor": COLORS["pos_strong"],
        "font": {"size": 11, "color": COLORS["pos_strong"]},
        "ax": 50, "ay": 40,
    })
 
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
 
    # fit line label
    mid = (axis_min + axis_max) / 2
    annotations.append({
        "x": mid + pad * 2, "y": mid + pad * 2,
        "text": "Ideal: actual = predicted",
        "showarrow": False,
        "font": {"size": 11, "color": COLORS["accent"]},
        "bgcolor": "rgba(255,255,255,0.8)",
    })
 
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Predicted vs Actual Reproductive Health Provider Density", "font": {"size": 15}},
        xaxis={"title": "Predicted Providers per 100k", "range": axis_range},
        yaxis={"title": "Actual Providers per 100k", "range": axis_range},
        annotations=annotations,
    )
    return fig


def build_choropleth(df: pd.DataFrame, selected_state: str | None = None) -> go.Figure:
    """US choropleth colored by access gap with optional state highlight."""
    res_max = _shared_range(df)
    states = df["practice_state"]
 
    if selected_state:
        line_widths = [4 if s == selected_state else 1 for s in states]
        line_colors = ["#000000" if s == selected_state else "white" for s in states]
        opacities = [1.0 if s == selected_state else 0.4 for s in states]
    else:
        n = len(states)
        line_widths, line_colors, opacities = [1.5] * n, ["white"] * n, [1.0] * n
 
    fig = go.Figure(go.Choropleth(
        locations=states, z=df["residual"],
        locationmode="USA-states",
        colorscale=UNIFIED_COLORSCALE,
        zmin=-res_max, zmax=res_max, zmid=0,
        marker={"line": {"color": line_colors, "width": line_widths}, "opacity": opacities},
        colorbar={"title": "Access Gap", "thickness": 14, "len": 0.75,
                  "x": 1.01, "y": 0.5, "tickfont": {"size": 11}, "title_font": {"size": 12}},
        hovertemplate="<b>%{location}</b><br>Access Gap: %{z:.2f}<extra></extra>",
    ))
 
    title_text = "Reproductive Health Access Gap Map"
    if selected_state:
        row = df[df["practice_state"] == selected_state]
        if len(row) > 0:
            title_text = f"Reproductive Health Access Gap — {selected_state} (gap: {row.iloc[0]['residual']:.2f})"
 
    fig.update_layout(
        **{**BASE_LAYOUT, "height": 520, "margin": {"l": 0, "r": 0, "t": 50, "b": 0}},
        title={"text": title_text, "font": {"size": 15}},
        geo=dict(scope="usa", projection_type="albers usa",
                 showland=True, landcolor="#f0f0f0",
                 showlakes=True, lakecolor="#e8f0fa",
                 showframe=False, bgcolor="rgba(0,0,0,0)"),
    )
    return fig
 
# ui componets 
 
def _generate_summary(df: pd.DataFrame) -> list:
    """Styled executive summary with analytical depth."""
    n_states = df["practice_state"].nunique()
    if n_states == 0:
        return [html.Span("No state-level data available for summary.")]
 
    name_col = "state_name" if "state_name" in df.columns else "practice_state"
    total_providers = int(df["provider_count"].sum())
    avg_density = df["providers_per_100k"].mean()
    med_density = df["providers_per_100k"].median()
 
    underserved = df[df["residual"] < 0]
    n_under = len(underserved)
    pct_under = round(n_under / n_states * 100)
    n_over = len(df[df["residual"] > 0])
 
    worst_3 = df.nsmallest(3, "residual")
    worst_names = ", ".join(worst_3[name_col].tolist())
    worst_avg_gap = worst_3["residual"].mean()
 
    best_3 = df.nlargest(3, "residual")
    best_names = ", ".join(best_3[name_col].tolist())
 
    top5_providers = df.nlargest(5, "provider_count")["provider_count"].sum()
    top5_pct = top5_providers / total_providers * 100 if total_providers > 0 else 0
 
    b = lambda text: html.B(text, style={"color": COLORS["text"]})
 
    return [
        html.Span([
            "Across ", b(f"{n_states} states"), " analyzed, Ovara identified ",
            b(f"{total_providers:,}"), " active reproductive health providers with an average density of ",
            b(f"{avg_density:.2f}"), " per 100,000 residents (median: ",
            b(f"{med_density:.2f}"), "). ",
            "The top 5 states by provider count account for ",
            b(f"{top5_pct:.0f}%"), " of all providers, reflecting significant geographic concentration.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            b(f"{n_under} states ({pct_under}%)"),
            " fall below model-predicted supply levels, indicating potential reproductive health access gaps. ",
            "The three most underserved — ", b(worst_names),
            " — average a residual of ", b(f"{worst_avg_gap:.2f}"),
            ", meaning actual provider supply is substantially lower than what their population "
            "and workforce characteristics predict.",
        ]),
        html.Br(), html.Br(),
        html.Span([
            "On the other end, ", b(f"{n_over} states"), " exceed predicted supply. ",
            b(best_names),
            " show the strongest over-supply, suggesting these states may serve as regional hubs "
            "that attract providers beyond their immediate population base.",
        ]),
    ]
 
 
 def _kpi_card(
    title: str, value: str, subtitle: str = "",
    color: str = COLORS["text"], accent: str = COLORS["card_border"],
) -> dbc.Card:
    """Reusable KPI card with colored top accent border."""
    children = [
        html.P(title, className="mb-1", style={
            "fontSize": "0.85rem", "color": COLORS["text_muted"],
            "fontWeight": "600", "textTransform": "uppercase", "letterSpacing": "0.05em",
        }),
        html.H2(value, className="mb-0", style={
            "fontSize": "2.2rem", "fontWeight": "700", "color": color,
        }),
    ]
    if subtitle:
        children.append(html.P(subtitle, className="mb-0 mt-1", style={
            "fontSize": "0.8rem", "color": COLORS["text_muted"],
        }))
 
    return dbc.Card(
        dbc.CardBody(children),
        style={**CARD_STYLE, "textAlign": "center", "borderTop": f"4px solid {accent}"},
    )


def _chart_card(graph_id: str, figure: go.Figure, is_map: bool = False) -> dbc.Card:
    """Wrap a Plotly figure in a styled card."""
    return dbc.Card(
        dcc.Graph(id=graph_id, figure=figure, config=MAP_CONFIG if is_map else CHART_CONFIG),
        style=CARD_STYLE,
    )
  
 
# dashboard
 
def build_access_dashboard(df: pd.DataFrame, *, debug: bool = False) -> None:
    """
    Interactive Dash dashboard for reproductive health provider access analysis.
    Launches a local server at http://127.0.0.1:8050
    """
    _validate(df)
    print("[VIS] Launching interactive Dash dashboard...")
    chart_df = df.copy()
 
    # pre compute kpis
    n_states = int(chart_df["practice_state"].nunique())
    total_providers = int(chart_df["provider_count"].sum())
    avg_dens = chart_df["providers_per_100k"].mean()
    med_dens = chart_df["providers_per_100k"].median()
    worst_row = chart_df.nsmallest(1, "residual").iloc[0]
    worst_name = worst_row.get("state_name", worst_row["practice_state"])
 
    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Ovara — Reproductive Health Access Dashboard",
    )
 
    app.layout = dbc.Container([
 
        # header
        dbc.Row(dbc.Col(html.Div([
            html.H3("Reproductive Health Provider Access Dashboard",
                     className="mb-0", style={"fontWeight": "700"}),
            html.P("Residuals highlight where reproductive health provider supply "
                   "falls below or exceeds model expectations. Click a state on "
                   "the map to filter the bar chart.",
                   className="mb-0", style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
        ], style={"textAlign": "center", "padding": "18px 0 10px 0"}), width=12)),
 
        html.Hr(style={"margin": "0 0 16px 0", "borderColor": COLORS["card_border"]}),
 
        # kpi row
        dbc.Row([
            dbc.Col(_kpi_card("States Analyzed", str(n_states),
                              subtitle=f"{total_providers:,} total providers",
                              accent=COLORS["pos_strong"]), md=4),
            dbc.Col(_kpi_card("Avg Providers / 100k", f"{avg_dens:.2f}",
                              subtitle=f"Median: {med_dens:.2f}",
                              accent=COLORS["accent"]), md=4),
            dbc.Col(_kpi_card("Most Underserved", worst_name,
                              subtitle=f"Gap: {worst_row['residual']:.2f}",
                              color=COLORS["kpi_bad"], accent=COLORS["kpi_bad"]), md=4),
        ], className="g-3 mb-3"),
 
        # charts: bar + scatter
        dbc.Row([
            dbc.Col(dbc.Card([
                dcc.Graph(id="bar-chart", figure=build_bar(chart_df), config=CHART_CONFIG),
                html.Div(
                    dbc.Button("Reset filter", id="reset-bar", size="sm", color="secondary", outline=True),
                    style={"textAlign": "right", "padding": "6px 12px 10px 0"},
                ),
            ], style=CARD_STYLE), md=5),
            dbc.Col(_chart_card("scatter-chart", build_scatter(chart_df)), md=7),
        ], className="g-3 mb-3"),
 
        # map
        dbc.Row(dbc.Col(
            _chart_card("choropleth", build_choropleth(chart_df), is_map=True), width=12,
        ), className="mb-3"),
 
        # executive summary
        dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Executive Summary", style={
                "fontWeight": "700", "textTransform": "uppercase",
                "letterSpacing": "0.05em", "color": COLORS["text_muted"], "fontSize": "0.8rem",
            }),
            html.Div(_generate_summary(chart_df), id="summary-text", style={
                "fontSize": "0.95rem", "lineHeight": "1.7",
                "color": COLORS["text"], "marginBottom": "0",
            }),
        ]), style={**CARD_STYLE, "backgroundColor": "#f0f4f8"}), width=12), className="mb-4"),
 
    ], fluid=True, style={
        "backgroundColor": COLORS["bg"], "fontFamily": FONT_STACK,
        "maxWidth": "1440px", "paddingBottom": "40px",
    })

    # callback: click map to filter bar chart
    @app.callback(
        Output("bar-chart", "figure"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def update_bar(click_data, _n_clicks):
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return build_bar(chart_df)
        return build_bar(chart_df, selected_states=[click_data["points"][0]["location"]])
    
    # callback: click map to highlight selected state
    @app.callback(
        Output("choropleth", "figure"),
        Input("choropleth", "clickData"),
        Input("reset-bar", "n_clicks"),
    )
    def highlight_state(click_data, _n_clicks):
        if ctx.triggered_id == "reset-bar" or click_data is None:
            return build_choropleth(chart_df)
        return build_choropleth(chart_df, selected_state=click_data["points"][0]["location"])
    

    port = int(os.environ.get("DASH_PORT", 8050))
    print(f"[VIS] Dashboard running at http://127.0.0.1:{port}")
    app.run(debug=debug, port=port)
    

# workflow manager
 
def run_interactive_visualizations() -> None:
    """Run the full reproductive health visualization workflow."""
    df = load_regression_results()
 
    # export dashboard figures as static html
    _save_html(build_bar(df), "underserved_bar_chart.html")
    _save_html(build_scatter(df), "predicted_vs_actual_scatter.html")
    _save_html(build_choropleth(df), "access_gap_choropleth.html")
 
    print("[VIS] ===== STATIC EXPORTS COMPLETE =====")
 
    # launch interactive dashboard
    build_access_dashboard(df, debug=True)


if __name__ == "__main__":
    run_interactive_visualizations()
