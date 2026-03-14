import pandas as pd
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional


# file path 

INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_DIR = Path("data/visualizations")

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

#visualization stage


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
        title="Top 10 Most Over-Served States by Provider Access Residual",
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

    print("[VIS] ===== INTERACTIVE VISUALIZATIONS COMPLETE =====")

if __name__ == "__main__":
    run_interactive_visualizations()
