"""Reusable Dash views for the Iris atlas county explorer."""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html

from vis._brand import COUNTY_TIER_COLORS
from vis.atlas_model import county_summary, tier_label
from vis.county_visualizations import TIER_ORDER

TIER_RANGES = ["0", ">0–5", ">5–10", ">10–20", ">20"]
PAGE_SIZE = 5
# dbc.Select adds a hidden blank option valued "", so the dialog's "all" choices need a value of their own.
ALL_DRAFT = "all"


def button(label, component_id, primary=False, **props):
    """Build a labeled action using the shared 44 pixel button style."""
    return html.Button(
        label, id=component_id, type="button",
        className="atlas-button" + (" primary" if primary else ""), **props,
    )


def metric(label, value, note=""):
    """Render one summary measure with its denominator or scope caption."""
    return html.Div([
        html.Div(label, className="metric-label"),
        html.Div(value, className="metric-value"),
        html.Div(note, className="metric-note"),
    ], className="atlas-metric")


def summary_view(frame: pd.DataFrame | None):
    """Show scope totals, or explicit unavailable labels instead of false zeroes."""
    if frame is None:
        return [metric(label, "Unavailable", "No confirmed data loaded") for label in [
            "Counties with zero providers", "Residents in those counties", "Counties analyzed"
        ]]
    values = county_summary(frame)
    residents = values["residents"]
    population = f"{residents / 1_000_000:.1f} million" if residents >= 1_000_000 else f"{residents:,}"
    return [
        metric("Counties with zero providers", f'{values["deserts"]:,}',
               f'{values["share"]:.1f}% of {values["counties"]:,} counties'),
        metric("Residents in those counties", population, f"{residents:,} residents · ACS 2022"),
        metric("Counties analyzed", f'{values["counties"]:,}', "County equivalents included"),
        html.Div([
            html.Strong(f'{values["deserts"]:,} counties'),
            html.P("have zero registered providers"),
            html.P(f'{population} residents · {values["share"]:.1f}% of counties'),
            html.P(f'Of {values["counties"]:,} county equivalents analyzed'),
        ], className="mobile-summary"),
    ]


def detail_view(row: pd.Series | None):
    """Present a selected county and keep registry uncertainty beside its figures."""
    if row is None:
        return [
            html.Div("COUNTY DETAILS", className="eyebrow"),
            html.H2("Select a county", className="county-title"),
            html.P("Use county search, the list, or the map to inspect an area's registered supply."),
        ]
    name, _, state = row["county_name"].rpartition(", ")
    return [
        html.Div("SELECTED COUNTY", className="eyebrow"),
        html.H2(name or row["county_name"], className="county-title"),
        html.P(f'{state} · FIPS {row["county_fips"]}', className="muted"),
        html.Div(
            f'{tier_label(row["risk_tier"])} · {row["providers_per_100k"]:.2f} providers / 100k',
            className="tier-badge",
        ),
        html.Div([
            metric("Providers", f'{int(row["provider_count"]):,}'),
            metric("Residents", f'{int(row["total_population"]):,}'),
        ], className="detail-metrics"),
        html.Hr(),
        html.P(
            f'{int(row["provider_count"]):,} registered '
            f'{"provider" if row["provider_count"] == 1 else "providers"} in an area of '
            f'{int(row["total_population"]):,} residents.'
        ),
        html.P(
            "Registry records can change this rate substantially. Verify local services "
            "before drawing conclusions.", className="small muted",
        ),
    ]


def legend():
    """Pair every ordered color with a tier name and its exact threshold."""
    return html.Div([
        html.P("Registered providers per 100,000 residents", className="small muted"),
        html.Ul([
            html.Li([
                html.Span(className="tier-swatch", style={"backgroundColor": COUNTY_TIER_COLORS[tier]}),
                html.Span(f"{tier_label(tier)} {interval}"),
            ]) for tier, interval in zip(TIER_ORDER, TIER_RANGES)
        ], className="atlas-legend"),
    ])


def distribution(frame: pd.DataFrame):
    """Use the same filtered records for tier counts and proportional bar widths."""
    counts = frame["risk_tier"].value_counts()
    total = len(frame)
    return [
        html.H2("How counties are distributed", className="section-title"),
        html.Div([
            html.Span(
                style={"width": f"{counts.get(tier, 0) / total * 100 if total else 0}%",
                       "backgroundColor": COUNTY_TIER_COLORS[tier]},
                title=f'{tier_label(tier)}: {counts.get(tier, 0):,}',
            ) for tier in TIER_ORDER
        ], className="distribution-bar", **{"aria-hidden": "true"}),
        html.Dl([
            html.Div([
                html.Dt(tier_label(tier)),
                html.Dd(f'{counts.get(tier, 0):,}'),
            ]) for tier in TIER_ORDER
        ], className="distribution-labels"),
    ]


def county_list(frame, selected, query, page, mode):
    """Render paginated native buttons as an alternative to pointing at a map."""
    from vis.atlas_model import search_counties

    if mode == "all" and not (query or "").strip():
        matches = frame.sort_values(["county_name", "county_fips"])
    else:
        matches = search_counties(frame, query)
    page = min(max(0, page or 0), max(0, (len(matches) - 1) // PAGE_SIZE))
    visible = matches.iloc[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    heading = "Search results" if (query or "").strip() else (
        "Counties in this view" if mode == "all" else "Lowest density with at least one provider"
    )
    rows = [
        html.Div([
            html.Div("COUNTY"), html.Div("PER 100K"),
        ], className="county-list-heading"),
    ]
    for row in visible.itertuples():
        rows.append(html.Button([
            html.Span(row.county_name),
            html.Strong(f"{row.providers_per_100k:.2f}"),
        ], id={"type": "county-choice", "fips": row.county_fips},
            n_clicks=0, className="county-row" + (" selected" if selected == row.county_fips else ""),
            type="button", **{"aria-pressed": selected == row.county_fips}))
    if matches.empty:
        rows.append(html.Div([
            html.H3("No counties match this view"),
            html.P("Try another county name or FIPS code, clear search, or adjust the filters."),
        ], className="empty-state"))
    first = page * PAGE_SIZE + 1 if len(matches) else 0
    caption = f"{first}–{min((page + 1) * PAGE_SIZE, len(matches))} of {len(matches):,} counties"
    note = "Zero-provider counties are counted separately above." if not query and mode == "ranked" else ""
    return heading, note, rows, caption, page == 0, (page + 1) * PAGE_SIZE >= len(matches)


def comparison_view(rows):
    """Render the same county measures side by side and in stacked mobile cards."""
    if len(rows) != 2:
        return html.P("Save two distinct counties to compare their registered supply.")
    metrics = [
        ("Providers per 100,000 residents", lambda row: f'{row["providers_per_100k"]:.2f}'),
        ("Registered providers", lambda row: f'{int(row["provider_count"]):,}'),
        ("Resident population", lambda row: f'{int(row["total_population"]):,}'),
        ("Represented taxonomy codes", lambda row: str(int(row.get("unique_taxonomies", 0)))),
        ("Access tier", lambda row: tier_label(row["risk_tier"])),
    ]
    desktop = html.Table([
        html.Thead(html.Tr([
            html.Th("Observed measure", scope="col"),
            *[html.Th(row["county_name"], scope="col") for row in rows],
        ])),
        html.Tbody([
            html.Tr([html.Th(label, scope="row"), *[html.Td(formatter(row)) for row in rows]])
            for label, formatter in metrics
        ]),
    ], className="comparison-table")
    mobile = html.Div([
        html.Section([
            html.H2(row["county_name"], className="county-title"),
            html.Dl([html.Div([html.Dt(label), html.Dd(formatter(row))])
                     for label, formatter in metrics]),
        ], className="comparison-card") for row in rows
    ], className="comparison-mobile")
    difference = abs(rows[1]["providers_per_100k"] - rows[0]["providers_per_100k"])
    same = rows[0]["risk_tier"] == rows[1]["risk_tier"]
    return [
        html.Div([desktop, mobile], className="comparison-matrix"),
        html.Section([
            html.H2("Different rates. The same access tier." if same else "Read each rate in context."),
            html.P(
                f"The density difference is {difference:.2f} registered providers per 100,000 "
                "residents. Compare the counts and populations together; this difference "
                "does not establish clinical capacity or recommend a service location."
            ),
        ], className="comparison-takeaway"),
        html.Div([
            html.Section([html.H2("What this comparison shows"),
                          html.P("Registered supply and population, calculated consistently from the project snapshot.")]),
            html.Section([html.H2("What still needs local verification"),
                          html.P("Specialty fit, appointment availability, insurance acceptance and travel across county lines.")]),
        ], className="comparison-limits"),
    ]


def evidence_footer():
    """Keep source vintage and interpretation boundaries visible on every view."""
    return html.Footer([
        html.P("NPPES registry snapshot + ACS 2022 population · 13 tracked taxonomy codes"),
        html.P("Registered supply does not measure appointment availability, insurance acceptance, travel time, or delivered care."),
    ], className="evidence-footer")


def methodology_view():
    """Explain observed tiers and the retired state model in plain language."""
    return html.Section([
        html.H2("A count of registered supply"),
        html.P("Ovara joins reproductive health provider records from NPPES with Census ACS "
               "county population. Each county's rate is the registered provider count "
               "divided by its population, multiplied by 100,000."),
        html.H3("County thresholds are project choices"),
        legend(),
        html.P("These cut points are descriptive, not clinical standards. Connecticut uses "
               "nine planning regions as county equivalents. A ZIP spanning multiple "
               "counties is assigned to one area, so boundaries remain approximate."),
        html.H3("The state model is a negative result"),
        html.P("The corrected state regression explains little of the variation in provider "
               "density, with cross validated R² about +0.12. Its former residual based "
               "risk tiers are retired. State overview shows observed density and ranks; "
               "the regression remains a labeled diagnostic."),
        html.H3("Use this to ask better local questions"),
        html.P("An NPI record does not establish active practice, appointment capacity, "
               "insurance acceptance or travel access. Compare specialties and verify "
               "local services before acting on a density difference."),
        html.A("Read the full methodology", href="https://github.com/kennethyeaher/inst737-final-project-kenneth-yeaher/blob/test/METHODOLOGY.md"),
    ], className="methodology-panel")


def build_atlas_layout(state_view, state_options, default_county):
    """Compose a responsive shell with persistent controls and browser scoped state."""
    stores = [
        dcc.Store(id="atlas-scope", data={"state": "", "tier": ""}),
        dcc.Store(id="atlas-selected", data=default_county),
        dcc.Store(id="atlas-comparison", data=[]),
        dcc.Store(id="atlas-view", data="county"),
        dcc.Store(id="atlas-page", data=0),
        dcc.Store(id="atlas-revision", data=0),
        dcc.Store(id="atlas-map-event"),
    ]
    sidebar = html.Aside([
        html.Div([
            html.Div([html.Div("ovara", className="wordmark"),
                      html.Div("REPRODUCTIVE HEALTH ACCESS", className="brand-caption")]),
            html.Button("Menu", id="mobile-menu", className="atlas-button",
                        **{"aria-expanded": "false", "aria-controls": "atlas-navigation"}),
        ], className="brand-row"),
        html.Nav([
            button("County explorer", "nav-county"),
            button("State overview", "nav-state"),
            button("Methodology", "nav-method"),
        ], id="atlas-navigation", className="nav-items", **{"aria-label": "Primary navigation"}),
        html.Div([
            html.Div("ABOUT THIS DATA", className="eyebrow"),
            html.P(["Observed supply.", html.Br(), "No prediction required."], className="sidebar-statement"),
            html.P(["NPPES + Census ACS", html.Br(), "Project data snapshot"], className="small muted"),
        ], className="sidebar-foot"),
    ], className="atlas-sidebar")
    filters = html.Div([
        html.Div([html.Label("Search counties", htmlFor="county-search"),
                  dcc.Input(id="county-search", type="search", value="", debounce=0.25,
                            placeholder="Search county or state", className="atlas-input"),
                  button("Clear search", "clear-search")], className="search-field"),
        html.Div([html.Label("State", htmlFor="open-state-filter"),
                  button("All states", "open-state-filter")]),
        html.Div([html.Label("Access tier", htmlFor="open-tier-filter"),
                  button("All tiers", "open-tier-filter")]),
        button("Reset view", "reset-atlas"),
    ], className="atlas-filters")
    county_view = html.Section([
        dcc.Store(id="atlas-map-payload"),
        html.Div(id="atlas-summary", className="atlas-summary"),
        filters,
        html.Div([button("List", "mobile-list"), button("Map", "mobile-map")],
                 className="mobile-view-switch", **{"aria-label": "County view"}),
        html.Div([
            html.Div([
                html.H2(id="atlas-map-heading", className="section-title"),
                html.Div([
                    html.Div(id="atlas-map", className="atlas-map"),
                    html.Div([
                        button("+", "atlas-zoom-in", **{"aria-label": "Zoom in on county map"}),
                        button("−", "atlas-zoom-out", **{"aria-label": "Zoom out on county map"}),
                        button("Reset map", "atlas-zoom-reset"),
                    ], className="map-tools", **{"aria-label": "Map zoom controls"}),
                ], className="atlas-map-frame"),
                html.Div(id="atlas-map-render-status", className="sr-only", **{"aria-live": "polite"}),
                html.P(id="atlas-map-caption", className="map-caption"),
                legend(),
            ], id="atlas-map-column", className="map-column"),
            html.Aside([
                html.Div(id="atlas-detail"),
                button("Add to comparison", "add-comparison", primary=True),
            ], className="county-detail"),
        ], className="county-workspace"),
        html.Div([
            html.Section([
                html.H2(id="county-list-title", className="section-title"),
                html.P(id="county-list-note", className="small muted"),
                dcc.RadioItems(id="county-list-mode", value="ranked", inline=True, options=[
                    {"label": " Lowest density", "value": "ranked"},
                    {"label": " All counties", "value": "all"}],
                    className="list-mode", inputStyle={"marginRight": "6px"}),
                html.Div(id="county-list", className="county-list"),
                html.Div([button("Previous", "county-previous"),
                          html.Span(id="county-page-caption"),
                          button("Next", "county-next")], className="list-pagination"),
            ]),
            html.Section(id="atlas-distribution"),
        ], className="county-support"),
        html.Section([
            html.Div(id="comparison-tray-content"),
            html.Div([button("Compare counties", "tray-compare", primary=True),
                      button("Clear comparison", "clear-comparison")], className="tray-actions"),
        ], id="comparison-tray", className="comparison-tray", hidden=True),
    ], id="atlas-county-view")
    dialog = dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Filter counties"), close_button=False),
        dbc.ModalBody([
            html.P("Choose a scope, then apply the changes together.", className="muted"),
            html.Label("State", htmlFor="draft-state"),
            dbc.Select(id="draft-state", options=[{"label": "All states", "value": ALL_DRAFT}, *state_options],
                       value=ALL_DRAFT),
            html.Label("Access tier", htmlFor="draft-tier"),
            dbc.Select(id="draft-tier", options=[
                {"label": "All tiers", "value": ALL_DRAFT},
                *[{"label": tier_label(tier), "value": tier} for tier in TIER_ORDER],
            ], value=ALL_DRAFT),
            html.P("Cancel keeps your current view.", className="small muted"),
        ]),
        dbc.ModalFooter([button("Cancel", "cancel-filters"),
                         button("Apply filters", "apply-filters", primary=True)]),
    ], id="filter-dialog", is_open=False, centered=True, className="atlas-filter-dialog",
        autofocus=True)
    main = html.Main([
        html.Header([
            html.Div([html.Div(id="atlas-breadcrumb", className="eyebrow"),
                      html.H1(id="atlas-title"), html.P(id="atlas-subhead", className="muted")]),
            html.Div([button("Compare (0/2)", "open-comparison", primary=True, disabled=True),
                      button("Back to explorer", "back-to-explorer")], className="header-actions"),
        ], className="atlas-header"),
        html.Div(id="atlas-feedback", className="feedback", role="status", **{"aria-live": "polite"}),
        html.Section([
            html.H2("County data is unavailable"),
            html.P("Retry before interpreting counts or rates. Missing records are not zero provider counties."),
            button("Retry loading", "retry-atlas", primary=True),
        ], id="atlas-unavailable", className="unavailable-panel", hidden=True, role="alert"),
        dcc.Loading(county_view, type="circle", color="#6846AA", delay_show=250,
                    overlay_style={"visibility": "hidden"}, className="atlas-loading"),
        html.Section([
            html.Div([html.P("2 of 2 counties selected · NPPES + ACS 2022"),
                      button("Clear comparison", "clear-comparison-view")], className="comparison-scope"),
            html.Div(id="comparison-content"),
        ], id="atlas-compare-view", hidden=True),
        html.Section(state_view, id="atlas-state-view", hidden=True),
        html.Section(methodology_view(), id="atlas-method-view", hidden=True),
        evidence_footer(), dialog,
        html.Div(id="atlas-highlight-status", className="sr-only"),
        html.Div(id="atlas-mobile-status", className="sr-only"),
    ], id="main-content", className="atlas-main", tabIndex=-1)
    return html.Div([
        html.A("Skip to content", href="#main-content", className="skip-link"),
        *stores, sidebar, main,
    ], className="atlas-app")
