from __future__ import annotations

import json
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import html

#file paths
GEOJSON_FILE = Path("data/reference_tables/counties_geojson.json")
COUNTY_RISK_FILE = Path("data/model_outputs/county_risk_classified.csv")

FONT_STACK = "Inter, Segoe UI, sans-serif"

COLORS = {
    "text": "#212529",
    "text_muted": "#6c757d",
    "card_border": "#e0e0e0",
    "kpi_bad": "#c0392b",
    "accent": "#2ca25f",
}

CARD_STYLE = {
    "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "10px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.06)",
}

CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "staticPlot": False,
}

TIER_COLORS = {
    "access_desert": "#67000d",
    "critical": "#d32f2f",
    "underserved": "#ef8a62",
    "adequate": "#67a9cf",
    "well_served": "#2166ac",
}

TIER_ORDER = ["access_desert", "critical", "underserved", "adequate", "well_served"]

TIER_LABELS = {
    "access_desert": "Access Desert",
    "critical": "Critical",
    "underserved": "Underserved",
    "adequate": "Adequate",
    "well_served": "Well Served",
}

_geojson_cache: dict | None = None


def load_geojson() -> dict:
    """load county boundaries once so the dashboard does not keep rereading the same file."""
    global _geojson_cache

    if _geojson_cache is None:
        with open(GEOJSON_FILE) as f:
            _geojson_cache = json.load(f)

    return _geojson_cache


def load_county_risk_data() -> pd.DataFrame:
    """load county risk data and keep FIPS codes as strings so leading zeros do not get dropped."""
    return pd.read_csv(COUNTY_RISK_FILE, dtype={"county_fips": str, "state_fips": str})


def build_county_choropleth(
    df: pd.DataFrame,
    geojson: dict,
    selected_county: str | None = None,
    state_filter: str | None = None,
) -> go.Figure:
    """build county map colored by access risk tier."""
    plot_df = df.copy()

    if state_filter:
        plot_df = plot_df[plot_df["practice_state"] == state_filter]

    # map risk tiers to numbers because Plotly needs a numeric value for choropleth colors
    tier_to_num = {tier: i for i, tier in enumerate(TIER_ORDER)}
    plot_df["tier_num"] = plot_df["risk_tier"].map(tier_to_num)

    # create hard color breaks so each tier keeps its own color on the map
    colorscale = []
    for i, tier in enumerate(TIER_ORDER):
        lo = i / len(TIER_ORDER)
        hi = (i + 1) / len(TIER_ORDER)
        colorscale.append([lo, TIER_COLORS[tier]])
        colorscale.append([hi - 0.001, TIER_COLORS[tier]])

    n = len(plot_df)

    # highlight the selected county without fully hiding the rest of the map
    if selected_county:
        line_widths = [2.5 if f == selected_county else 0.3 for f in plot_df["county_fips"]]
        line_colors = ["#000" if f == selected_county else "#ccc" for f in plot_df["county_fips"]]
        opacities = [1.0 if f == selected_county else 0.5 for f in plot_df["county_fips"]]
    else:
        line_widths = [0.3] * n
        line_colors = ["#ccc"] * n
        opacities = [0.9] * n

    hover_text = [
        f"<b>{row['county_name']}</b><br>"
        f"Providers: {int(row['provider_count'])}<br>"
        f"Density: {row['providers_per_100k']:.1f} / 100k<br>"
        f"Tier: {TIER_LABELS.get(row['risk_tier'], row['risk_tier'])}<br>"
        f"Population: {int(row['total_population']):,}"
        for _, row in plot_df.iterrows()
    ]

    fig = go.Figure(go.Choropleth(
        geojson=geojson,
        locations=plot_df["county_fips"],
        z=plot_df["tier_num"],
        featureidkey="id",
        colorscale=colorscale,
        zmin=0,
        zmax=len(TIER_ORDER),
        marker={"line": {"color": line_colors, "width": line_widths}, "opacity": opacities},
        colorbar={
            "title": "Risk Tier",
            "thickness": 14,
            "len": 0.75,
            "tickvals": [i + 0.5 for i in range(len(TIER_ORDER))],
            "ticktext": [TIER_LABELS[t] for t in TIER_ORDER],
            "tickfont": {"size": 10},
            "title_font": {"size": 12},
        },
        text=hover_text,
        hovertemplate="%{text}<extra></extra>",
    ))

    title = "County Level Reproductive Health Access"
    if state_filter:
        title = f"County Access for {state_filter}"

    fig.update_layout(
        template="plotly_white",
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        height=560,
        font={"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
        title={"text": title, "font": {"size": 15}},
        geo=dict(
            scope="usa",
            projection_type="albers usa",
            showland=True,
            landcolor="#f0f0f0",
            showlakes=True,
            lakecolor="#e8f0fa",
            showframe=False,
            bgcolor="rgba(0,0,0,0)",
        ),
    )

    return fig


def build_county_bar(
    df: pd.DataFrame,
    state_filter: str | None = None,
    top_n: int = 15,
) -> go.Figure:
    """build bar chart for the counties with the lowest provider density."""
    plot_df = df[df["total_population"] > 0].copy()

    if state_filter:
        plot_df = plot_df[plot_df["practice_state"] == state_filter]

    # lowest density counties are the clearest way to show where access is weakest
    worst = plot_df.nsmallest(top_n, "providers_per_100k").sort_values("providers_per_100k")

    # remove state text from county labels so the y axis stays clean
    short_names = worst["county_name"].str.replace(r",.*", "", regex=True)

    bar_colors = [TIER_COLORS.get(t, "#999") for t in worst["risk_tier"]]

    fig = go.Figure(go.Bar(
        x=worst["providers_per_100k"],
        y=short_names,
        orientation="h",
        text=worst["providers_per_100k"].round(1),
        textposition="outside",
        textfont={"size": 11, "color": COLORS["text"]},
        marker={"color": bar_colors},
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Density: %{x:.1f} / 100k<extra></extra>"
        ),
    ))

    title = f"Top {top_n} Most Underserved Counties"
    if state_filter:
        title = f"Most Underserved Counties for {state_filter}"

    x_max = max(worst["providers_per_100k"].max() * 1.4, 1.0)

    fig.update_layout(
        template="plotly_white",
        margin={"l": 10, "r": 20, "t": 50, "b": 40},
        height=420,
        font={"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
        title={"text": title, "font": {"size": 15}},
        xaxis={"title": "Providers per 100k", "range": [0, x_max]},
        yaxis={"title": ""},
    )

    return fig


def county_kpi_cards(df: pd.DataFrame) -> list:
    """build the main KPI cards for the county view."""
    n_counties = len(df)
    n_desert = int((df["provider_count"] == 0).sum())
    pop_desert = int(df[df["provider_count"] == 0]["total_population"].sum())
    med_density = df[df["total_population"] > 0]["providers_per_100k"].median()

    # ignore tiny counties here so the most underserved card does not overreact to very small populations
    worst = df[df["total_population"] > 1000].nsmallest(1, "providers_per_100k")
    worst_name = worst["county_name"].str.replace(r",.*", "", regex=True).iloc[0] if len(worst) > 0 else "N/A"

    def _card(title, value, subtitle="", color=COLORS["text"], accent=COLORS["card_border"]):
        children = [
            html.P(title, className="mb-1", style={
                "fontSize": "0.85rem",
                "color": COLORS["text_muted"],
                "fontWeight": "600",
                "textTransform": "uppercase",
                "letterSpacing": "0.05em",
            }),
            html.H2(value, className="mb-0", style={
                "fontSize": "2.2rem",
                "fontWeight": "700",
                "color": color,
            }),
        ]

        if subtitle:
            children.append(html.P(subtitle, className="mb-0 mt-1", style={
                "fontSize": "0.8rem",
                "color": COLORS["text_muted"],
            }))

        return dbc.Card(
            dbc.CardBody(children),
            style={**CARD_STYLE, "textAlign": "center", "borderTop": f"4px solid {accent}"},
        )

    return [
        dbc.Col(_card(
            "Counties Analyzed",
            f"{n_counties:,}",
            accent="#2166ac",
        ), md=3),
        dbc.Col(_card(
            "Access Deserts",
            f"{n_desert:,}",
            subtitle=f"{pop_desert:,} residents affected",
            color=COLORS["kpi_bad"],
            accent="#67000d",
        ), md=3),
        dbc.Col(_card(
            "Median Density",
            f"{med_density:.1f}",
            subtitle="providers per 100k",
            accent=COLORS["accent"],
        ), md=3),
        dbc.Col(_card(
            "Most Underserved",
            worst_name,
            color=COLORS["kpi_bad"],
            accent="#d32f2f",
        ), md=3),
    ]


def county_detail_card(row: pd.Series) -> dbc.Card:
    """build the detail card for the county a user selects."""
    name = row["county_name"]
    tier = str(row["risk_tier"])
    tier_color = TIER_COLORS.get(tier, COLORS["text"])
    tier_label = TIER_LABELS.get(tier, tier)

    metrics = [
        ("Providers", f"{int(row['provider_count']):,}"),
        ("Density / 100k", f"{row['providers_per_100k']:.1f}"),
        ("Population", f"{int(row['total_population']):,}"),
        ("Specialties", f"{int(row.get('unique_taxonomies', 0))}"),
        ("Recent Growth", f"{int(row.get('recent_provider_growth', 0))}"),
    ]

    metric_cols = [
        dbc.Col(html.Div([
            html.P(label, className="mb-0", style={
                "fontSize": "0.75rem",
                "color": COLORS["text_muted"],
                "textTransform": "uppercase",
                "fontWeight": "600",
            }),
            html.P(value, className="mb-0", style={
                "fontSize": "1.3rem",
                "fontWeight": "700",
                "color": COLORS["text"],
            }),
        ], style={"textAlign": "center"}), md=2)
        for label, value in metrics
    ]

    return dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col(html.Div([
                html.H5(name, className="mb-1", style={"fontWeight": "700"}),
                html.Span(tier_label, style={
                    "fontSize": "0.85rem",
                    "fontWeight": "600",
                    "color": "white",
                    "backgroundColor": tier_color,
                    "padding": "3px 12px",
                    "borderRadius": "12px",
                }),
            ]), md=2),
            *metric_cols,
        ], className="align-items-center"),
    ]), style={**CARD_STYLE, "borderLeft": f"5px solid {tier_color}"})


def generate_county_summary(df: pd.DataFrame) -> list:
    """build the written summary for the county access view."""
    n_counties = len(df)
    n_desert = int((df["provider_count"] == 0).sum())
    pct_desert = round(n_desert / n_counties * 100)
    pop_desert = int(df[df["provider_count"] == 0]["total_population"].sum())

    n_critical = int((df["risk_tier"] == "critical").sum())
    n_underserved = int((df["risk_tier"] == "underserved").sum())
    n_concern = n_desert + n_critical + n_underserved

    total_providers = int(df["provider_count"].sum())
    med_density = df[df["total_population"] > 0]["providers_per_100k"].median()

    desert_states = df[df["provider_count"] == 0]["practice_state"].value_counts()
    top_desert_states = ", ".join(desert_states.head(5).index.tolist())

    b = lambda text: html.B(text, style={"color": COLORS["text"]})

    return [
        html.Span([
            "At the county level, the access picture becomes much sharper. Of the ",
            b(f"{n_counties:,} counties"),
            " in this analysis, ",
            b(f"{n_desert:,} ({pct_desert}%)"),
            " have ",
            b("zero registered reproductive health providers"),
            ". That means no OB/GYNs, no midwives, and no women's health NPs are listed "
            "in the federal registry for those counties. These are not just areas with low "
            "provider density. They are access deserts where the local provider workforce is "
            "missing from the data entirely. The ",
            b(f"{pop_desert:,} residents"),
            " living in these counties likely have to travel to a neighboring county for care.",
        ]),
        html.Br(),
        html.Br(),
        html.Span([
            "Beyond the access deserts, another ",
            b(f"{n_critical:,} counties"),
            " are classified as Critical, with fewer than 5 providers per 100,000 residents, and ",
            b(f"{n_underserved:,}"),
            " are classified as Underserved, with 5 to 10 providers per 100,000 residents. In total, ",
            b(f"{n_concern:,} counties"),
            ", or roughly ",
            b(f"{round(n_concern / n_counties * 100)}%"),
            " of all US counties, fall into a tier of concern. The national median county density is just ",
            b(f"{med_density:.1f}"),
            " providers per 100,000 residents, spread across a total workforce of ",
            b(f"{total_providers:,}"),
            " reproductive health providers.",
        ]),
        html.Br(),
        html.Br(),
        html.Span([
            "The states with the most access desert counties are ",
            b(top_desert_states),
            ". This county level view shows gaps that state averages can completely hide. A state can look "
            "adequate overall while still having dozens of counties where no reproductive health provider is registered.",
        ]),
    ]