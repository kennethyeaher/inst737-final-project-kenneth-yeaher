from __future__ import annotations

import json
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import html

from vis._brand import COUNTY_TIER_COLORS
from vis._styles import (
    CARD_STYLE,
    CHART_TITLE_FONT,
    COLORS,
    FONT_STACK,
    apply_axis_defaults,
)

# main file paths for county dashboard data
GEOJSON_FILE = Path("data/reference_tables/counties_geojson.json")
COUNTY_RISK_FILE = Path("data/model_outputs/county_risk_classified.csv")

# county tier setup ordered from worst access to strongest access
TIER_COLORS = COUNTY_TIER_COLORS
TIER_ORDER = ["access_desert", "critical", "underserved", "adequate", "well_served"]

TIER_LABELS = {
    "access_desert": "Access Desert",
    "critical": "Critical",
    "underserved": "Underserved",
    "adequate": "Adequate",
    "well_served": "Well Served",
}

# mapbox view settings used when the user filters down to one state
STATE_VIEW_PARAMS: dict[str, dict] = {
    "AL": {"center": {"lat": 32.8, "lon": -86.8}, "zoom": 5.5},
    "AK": {"center": {"lat": 64.2, "lon": -153.4}, "zoom": 3.5},
    "AZ": {"center": {"lat": 34.3, "lon": -111.1}, "zoom": 5.5},
    "AR": {"center": {"lat": 34.8, "lon": -92.2}, "zoom": 5.5},
    "CA": {"center": {"lat": 37.3, "lon": -119.7}, "zoom": 4.8},
    "CO": {"center": {"lat": 39.0, "lon": -105.5}, "zoom": 5.5},
    "CT": {"center": {"lat": 41.6, "lon": -72.7}, "zoom": 7.5},
    "DC": {"center": {"lat": 38.9, "lon": -77.0}, "zoom": 10.0},
    "DE": {"center": {"lat": 38.9, "lon": -75.5}, "zoom": 7.5},
    "FL": {"center": {"lat": 27.8, "lon": -83.7}, "zoom": 5.5},
    "GA": {"center": {"lat": 32.6, "lon": -83.4}, "zoom": 5.5},
    "HI": {"center": {"lat": 20.3, "lon": -156.4}, "zoom": 5.5},
    "ID": {"center": {"lat": 44.5, "lon": -114.6}, "zoom": 5.0},
    "IL": {"center": {"lat": 40.0, "lon": -89.2}, "zoom": 5.5},
    "IN": {"center": {"lat": 40.0, "lon": -86.1}, "zoom": 6.0},
    "IA": {"center": {"lat": 42.1, "lon": -93.5}, "zoom": 5.5},
    "KS": {"center": {"lat": 38.5, "lon": -98.4}, "zoom": 5.5},
    "KY": {"center": {"lat": 37.5, "lon": -85.3}, "zoom": 5.8},
    "LA": {"center": {"lat": 31.0, "lon": -91.8}, "zoom": 5.8},
    "ME": {"center": {"lat": 45.2, "lon": -69.0}, "zoom": 5.8},
    "MD": {"center": {"lat": 39.0, "lon": -76.8}, "zoom": 6.5},
    "MA": {"center": {"lat": 42.3, "lon": -71.8}, "zoom": 7.0},
    "MI": {"center": {"lat": 44.3, "lon": -85.4}, "zoom": 5.5},
    "MN": {"center": {"lat": 46.4, "lon": -93.1}, "zoom": 5.0},
    "MS": {"center": {"lat": 32.7, "lon": -89.7}, "zoom": 5.8},
    "MO": {"center": {"lat": 38.5, "lon": -92.4}, "zoom": 5.5},
    "MT": {"center": {"lat": 46.9, "lon": -110.4}, "zoom": 5.0},
    "NE": {"center": {"lat": 41.5, "lon": -99.9}, "zoom": 5.5},
    "NV": {"center": {"lat": 38.5, "lon": -117.1}, "zoom": 5.0},
    "NH": {"center": {"lat": 43.7, "lon": -71.6}, "zoom": 6.5},
    "NJ": {"center": {"lat": 40.1, "lon": -74.4}, "zoom": 7.0},
    "NM": {"center": {"lat": 34.4, "lon": -106.1}, "zoom": 5.5},
    "NY": {"center": {"lat": 42.9, "lon": -75.6}, "zoom": 5.8},
    "NC": {"center": {"lat": 35.5, "lon": -79.4}, "zoom": 5.8},
    "ND": {"center": {"lat": 47.5, "lon": -100.5}, "zoom": 5.5},
    "OH": {"center": {"lat": 40.4, "lon": -82.8}, "zoom": 6.0},
    "OK": {"center": {"lat": 35.5, "lon": -97.5}, "zoom": 5.8},
    "OR": {"center": {"lat": 44.0, "lon": -120.5}, "zoom": 5.5},
    "PA": {"center": {"lat": 40.9, "lon": -77.8}, "zoom": 6.0},
    "RI": {"center": {"lat": 41.7, "lon": -71.5}, "zoom": 8.5},
    "SC": {"center": {"lat": 33.8, "lon": -80.9}, "zoom": 6.0},
    "SD": {"center": {"lat": 44.4, "lon": -100.2}, "zoom": 5.5},
    "TN": {"center": {"lat": 35.9, "lon": -86.4}, "zoom": 5.8},
    "TX": {"center": {"lat": 31.5, "lon": -99.3}, "zoom": 4.8},
    "UT": {"center": {"lat": 39.4, "lon": -111.1}, "zoom": 5.5},
    "VT": {"center": {"lat": 44.1, "lon": -72.7}, "zoom": 6.5},
    "VA": {"center": {"lat": 37.5, "lon": -79.4}, "zoom": 5.8},
    "WA": {"center": {"lat": 47.4, "lon": -120.4}, "zoom": 5.5},
    "WV": {"center": {"lat": 38.6, "lon": -80.6}, "zoom": 6.0},
    "WI": {"center": {"lat": 44.6, "lon": -89.8}, "zoom": 5.5},
    "WY": {"center": {"lat": 43.0, "lon": -107.5}, "zoom": 5.5},
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
    """
    Build a county level map that users can zoom and pan.

    Selection is shown through county borders because mapbox choropleth opacity
    only works for the full trace, not each county separately.
    """
    plot_df = df.copy()

    if state_filter:
        plot_df = plot_df[plot_df["practice_state"] == state_filter]

    tier_to_num = {tier: i for i, tier in enumerate(TIER_ORDER)}
    plot_df["tier_num"] = plot_df["risk_tier"].map(tier_to_num)

    # build hard color bands so each tier keeps a solid color
    colorscale: list[list] = []
    for i, tier in enumerate(TIER_ORDER):
        lo = i / len(TIER_ORDER)
        hi = (i + 1) / len(TIER_ORDER)
        colorscale.append([lo, TIER_COLORS[tier]])

        edge = 1.0 if i == len(TIER_ORDER) - 1 else hi - 0.001
        colorscale.append([edge, TIER_COLORS[tier]])

    n = len(plot_df)

    # highlight selected county with a stronger border without hiding the rest of the map
    if selected_county:
        line_widths = [3.0 if f == selected_county else 0.3 for f in plot_df["county_fips"]]
        line_colors = ["#000" if f == selected_county else "#ccc" for f in plot_df["county_fips"]]
    else:
        line_widths = [0.3] * n
        line_colors = ["#ccc"] * n

    hover_text = [
        f"<b>{row['county_name']}</b><br>"
        f"Providers: {int(row['provider_count'])}<br>"
        f"Density: {row['providers_per_100k']:.1f} / 100k<br>"
        f"Tier: {TIER_LABELS.get(row['risk_tier'], row['risk_tier'])}<br>"
        f"Population: {int(row['total_population']):,}"
        for _, row in plot_df.iterrows()
    ]

    # snap the map to a state when the user filters, otherwise start with the full US view
    if state_filter and state_filter in STATE_VIEW_PARAMS:
        map_center = STATE_VIEW_PARAMS[state_filter]["center"]
        map_zoom = STATE_VIEW_PARAMS[state_filter]["zoom"]
    else:
        map_center = {"lat": 38.5, "lon": -96.0}
        map_zoom = 3.0

    title = "County Level Reproductive Health Access"
    if state_filter:
        title = f"County Access for {state_filter}"

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=plot_df["county_fips"],
        z=plot_df["tier_num"],
        featureidkey="id",
        colorscale=colorscale,
        zmin=0,
        zmax=len(TIER_ORDER),
        marker={
            "line": {"color": line_colors, "width": line_widths},
            "opacity": 0.85,
        },
        colorbar={
            "title": "Risk Tier",
            "thickness": 14,
            "len": 0.75,
            "tickvals": [i + 0.5 for i in range(len(TIER_ORDER))],
            "ticktext": [TIER_LABELS[tier] for tier in TIER_ORDER],
            "tickfont": {"size": 10},
            "title_font": {"size": 12},
        },
        text=hover_text,
        hovertemplate="%{text}<extra></extra>",
    ))

    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox_zoom=map_zoom,
        mapbox_center=map_center,
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        height=560,
        font={"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
        title={"text": title, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        paper_bgcolor="rgba(0,0,0,0)",
    )

    return fig


def build_county_bar(
    df: pd.DataFrame,
    state_filter: str | None = None,
    top_n: int = 15,
) -> go.Figure:
    """
    Build the bar chart for the most underserved counties that still have providers.

    Counties with zero providers are excluded from this chart because they all have
    density 0.0, which makes the bar chart hard to read. They are still shown in
    the Access Deserts KPI card, and the title says how many were excluded.
    """
    base = df[df["total_population"] > 0].copy()

    if state_filter:
        base = base[base["practice_state"] == state_filter]

    n_deserts = int((base["provider_count"] == 0).sum())
    plot_df = base[base["provider_count"] > 0].copy()

    layout_base = dict(
        template="plotly_white",
        margin={"l": 10, "r": 20, "t": 60, "b": 40},
        height=420,
        font={"family": FONT_STACK, "size": 12, "color": COLORS["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # show a clean empty state when every county in the filter has zero providers
    if len(plot_df) == 0:
        msg = (
            f"All populated counties in {state_filter} are Access Deserts"
            if state_filter else "No counties with providers found"
        )

        fig = go.Figure()
        fig.update_layout(**layout_base, title={
            "text": msg, "font": CHART_TITLE_FONT,
            "x": 0.02, "xanchor": "left",
        })
        apply_axis_defaults(fig)
        return fig

    show_n = min(top_n, len(plot_df))
    worst = plot_df.nsmallest(show_n, "providers_per_100k").sort_values("providers_per_100k")

    short_names = worst["county_name"].str.replace(r",.*", "", regex=True)
    bar_colors = [TIER_COLORS.get(tier, "#999") for tier in worst["risk_tier"]]

    desert_note = f" ({n_deserts} access desert counties excluded)" if n_deserts > 0 else ""

    if state_filter:
        title = f"Most Underserved for {state_filter}{desert_note}"
    else:
        title = f"Top {show_n} Most Underserved Counties{desert_note}"

    x_max = max(worst["providers_per_100k"].max() * 1.4, 1.0)

    fig = go.Figure(go.Bar(
        x=worst["providers_per_100k"],
        y=short_names,
        orientation="h",
        text=worst["providers_per_100k"].round(1),
        textposition="outside",
        textfont={"size": 11, "color": COLORS["text"]},
        marker={"color": bar_colors},
        hovertemplate="<b>%{y}</b><br>Density: %{x:.1f} / 100k<extra></extra>",
    ))

    fig.update_layout(
        **layout_base,
        title={"text": title, "font": CHART_TITLE_FONT, "x": 0.02, "xanchor": "left"},
        xaxis={"title": "Providers per 100k", "range": [0, x_max]},
        yaxis={"title": ""},
    )
    apply_axis_defaults(fig)

    return fig


def county_kpi_cards(df: pd.DataFrame) -> list:
    """build the main KPI cards for the county view."""
    n_counties = len(df)
    n_desert = int((df["provider_count"] == 0).sum())
    pop_desert = int(df[df["provider_count"] == 0]["total_population"].sum())
    med_density = df[df["total_population"] > 0]["providers_per_100k"].median()

    # match the bar chart filter so this KPI and the chart agree on what "most underserved" means.
    # access deserts (provider_count == 0) already get their own KPI card, so this tile points
    # at the worst county that actually has at least one provider on the registry.
    worst_pool = df[(df["total_population"] > 1000) & (df["provider_count"] > 0)]
    worst = worst_pool.nsmallest(1, "providers_per_100k")
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