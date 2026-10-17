"""Dash callbacks that keep scope, county selection and comparison consistent."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, html, no_update
from dash.exceptions import PreventUpdate

from vis.atlas_model import (
    comparison_rows, comparison_selection, county_scope, state_names, tier_label,
)
from vis.atlas_view import (
    PAGE_SIZE, comparison_view, county_list, detail_view, distribution, summary_view,
)
from vis.county_visualizations import TIER_ORDER


def register_atlas_callbacks(app, snapshot, refresh):
    """Register browser scoped state transitions and snapshot based render callbacks."""
    outputs = {
        "scope": Output("atlas-scope", "data"),
        "selected": Output("atlas-selected", "data"),
        "comparison": Output("atlas-comparison", "data"),
        "view": Output("atlas-view", "data"),
        "query": Output("county-search", "value"),
        "modal": Output("filter-dialog", "is_open"),
        "draft_state": Output("draft-state", "value"),
        "draft_tier": Output("draft-tier", "value"),
        "feedback": Output("atlas-feedback", "children"),
        "revision": Output("atlas-revision", "data"),
    }
    actions = [
        "open-state-filter", "open-tier-filter", "cancel-filters", "apply-filters",
        "reset-atlas", "add-comparison", "clear-comparison", "clear-comparison-view",
        "open-comparison", "tray-compare", "back-to-explorer", "nav-county",
        "nav-state", "nav-method", "clear-search", "retry-atlas",
    ]
    inputs = {item.replace("-", "_"): Input(item, "n_clicks") for item in actions}
    inputs.update({
        "choose": Input({"type": "county-choice", "fips": ALL}, "n_clicks"),
        "remove": Input({"type": "remove-county", "fips": ALL}, "n_clicks"),
        "map_event": Input("atlas-map-event", "data"),
        "current_scope": State("atlas-scope", "data"),
        "current_selected": State("atlas-selected", "data"),
        "current_comparison": State("atlas-comparison", "data"),
        "current_view": State("atlas-view", "data"),
        "draft_state_value": State("draft-state", "value"),
        "draft_tier_value": State("draft-tier", "value"),
        "current_revision": State("atlas-revision", "data"),
    })

    @app.callback(output=outputs, inputs=inputs, prevent_initial_call=True)
    def handle_action(**values):
        """Apply explicit actions while leaving unrelated browser state untouched."""
        event = ctx.triggered_id
        result = {key: no_update for key in outputs}
        frame = snapshot["frame"]
        scope = values["current_scope"] or {"state": "", "tier": ""}
        selected = values["current_selected"]
        comparison = values["current_comparison"] or []
        if isinstance(event, dict):
            clicks = values["choose"] if event["type"] == "county-choice" else values["remove"]
            if not any(clicks or []):
                raise PreventUpdate
            if event["type"] == "remove-county":
                result["comparison"] = [fips for fips in comparison if fips != event["fips"]]
                result["view"] = "county"
                result["feedback"] = "County removed from comparison."
                return result
            selected = event["fips"]
        elif event == "atlas-map-event":
            selected = (values["map_event"] or {}).get("fips")
        elif event in ("open-state-filter", "open-tier-filter"):
            result.update(modal=True, draft_state=scope.get("state", ""),
                          draft_tier=scope.get("tier", ""))
            return result
        elif event == "cancel-filters":
            result.update(modal=False, draft_state=scope.get("state", ""),
                          draft_tier=scope.get("tier", ""))
            return result
        elif event == "apply-filters":
            state = values["draft_state_value"] or ""
            tier = values["draft_tier_value"] or ""
            if frame is None:
                result.update(modal=False, feedback="Load county data before applying filters.")
                return result
            if state and state not in set(frame["practice_state"]):
                result["feedback"] = "Choose a state listed in the filter."
                return result
            if tier and tier not in TIER_ORDER:
                result["feedback"] = "Choose an access tier listed in the filter."
                return result
            applied = {"state": state, "tier": tier}
            scoped = county_scope(frame, applied)
            keep = selected if selected in set(scoped["county_fips"]) else None
            result.update(scope=applied, selected=keep, modal=False, query="",
                          feedback=f"Filters applied. {len(scoped):,} county equivalents in view.")
            return result
        elif event == "reset-atlas":
            default = "29037" if frame is not None and "29037" in set(frame["county_fips"]) else None
            result.update(scope={"state": "", "tier": ""}, selected=default, comparison=[],
                          view="county", query="", modal=False, draft_state="", draft_tier="",
                          feedback="National view restored. Filters and comparison cleared.")
            return result
        elif event == "add-comparison":
            if frame is None:
                raise PreventUpdate
            comparison, message = comparison_selection(frame, comparison, selected)
            result.update(comparison=comparison, feedback=message)
            return result
        elif event in ("clear-comparison", "clear-comparison-view"):
            result.update(comparison=[], view="county", feedback="Comparison cleared.")
            return result
        elif event in ("open-comparison", "tray-compare"):
            if frame is not None and len(comparison_rows(frame, comparison)) == 2:
                result.update(view="compare", feedback="")
            return result
        elif event in ("back-to-explorer", "nav-county", "nav-state", "nav-method"):
            view = {"nav-state": "state", "nav-method": "method"}.get(event, "county")
            result.update(view=view, feedback="")
            return result
        elif event == "clear-search":
            result.update(query="", feedback="Search cleared. Saved comparison counties kept.")
            return result
        elif event == "retry-atlas":
            snapshot.update(refresh())
            result.update(revision=(values["current_revision"] or 0) + 1,
                          feedback="Dataset reloaded." if snapshot["frame"] is not None
                          else "County data is still unavailable. Check the local dataset and retry.")
            return result
        else:
            raise PreventUpdate

        # County selection must belong to the applied scope, even for map events.
        if frame is None:
            raise PreventUpdate
        scoped = county_scope(frame, scope)
        if selected not in set(scoped["county_fips"]):
            raise PreventUpdate
        row = scoped[scoped["county_fips"] == selected].iloc[0]
        result.update(selected=selected, feedback=f'Selected {row["county_name"]}.')
        return result

    @app.callback(
        Output("atlas-page", "data"),
        Input("county-next", "n_clicks"), Input("county-previous", "n_clicks"),
        Input("county-search", "value"), Input("atlas-scope", "data"),
        Input("county-list-mode", "value"), State("atlas-page", "data"),
    )
    def paginate(_next, _previous, _query, _scope, _mode, page):
        """Reset pagination after search or scope changes, otherwise move one page."""
        if ctx.triggered_id == "county-next":
            return (page or 0) + 1
        if ctx.triggered_id == "county-previous":
            return max(0, (page or 0) - 1)
        return 0

    @app.callback(
        Output("atlas-map-payload", "data"),
        Output("atlas-map-heading", "children"),
        Output("atlas-map-caption", "children"),
        Input("atlas-scope", "data"), Input("atlas-revision", "data"),
    )
    def render_map(scope, _revision):
        """Build geometry only when the dataset or applied scope changes."""
        frame = snapshot["frame"]
        if frame is None:
            return {"svg": ""}, "County access map", "No confirmed county data loaded."
        scoped = county_scope(frame, scope)
        state = (scope or {}).get("state")
        name = state_names(frame).get(state, "the United States")
        caption = "Simplified county boundaries" if state else "AK + HI insets · Simplified county boundaries"
        return {"svg": snapshot["atlas"].render(scoped, state)}, f"County access across {name}", caption

    @app.callback(
        output={
            "summary": Output("atlas-summary", "children"),
            "detail": Output("atlas-detail", "children"),
            "distribution": Output("atlas-distribution", "children"),
            "list_title": Output("county-list-title", "children"),
            "list_note": Output("county-list-note", "children"),
            "list": Output("county-list", "children"),
            "caption": Output("county-page-caption", "children"),
            "previous": Output("county-previous", "disabled"),
            "next": Output("county-next", "disabled"),
            "state_label": Output("open-state-filter", "children"),
            "tier_label": Output("open-tier-filter", "children"),
            "add_disabled": Output("add-comparison", "disabled"),
            "add_label": Output("add-comparison", "children"),
            "compare_disabled": Output("open-comparison", "disabled"),
            "compare_label": Output("open-comparison", "children"),
            "tray_hidden": Output("comparison-tray", "hidden"),
            "tray": Output("comparison-tray-content", "children"),
            "tray_disabled": Output("tray-compare", "disabled"),
            "comparison": Output("comparison-content", "children"),
            "county_hidden": Output("atlas-county-view", "hidden"),
            "state_hidden": Output("atlas-state-view", "hidden"),
            "method_hidden": Output("atlas-method-view", "hidden"),
            "compare_hidden": Output("atlas-compare-view", "hidden"),
            "unavailable": Output("atlas-unavailable", "hidden"),
            "title": Output("atlas-title", "children"),
            "breadcrumb": Output("atlas-breadcrumb", "children"),
            "subhead": Output("atlas-subhead", "children"),
            "back_style": Output("back-to-explorer", "style"),
            "compare_style": Output("open-comparison", "style"),
            "nav_county": Output("nav-county", "className"),
            "nav_state": Output("nav-state", "className"),
            "nav_method": Output("nav-method", "className"),
        },
        inputs={
            "scope": Input("atlas-scope", "data"),
            "selected": Input("atlas-selected", "data"),
            "comparison": Input("atlas-comparison", "data"),
            "view": Input("atlas-view", "data"),
            "query": Input("county-search", "value"),
            "page": Input("atlas-page", "data"),
            "mode": Input("county-list-mode", "value"),
            "revision": Input("atlas-revision", "data"),
        },
    )
    def render_view(scope, selected, comparison, view, query, page, mode, revision):
        """Render every numeric and textual view from one applied county scope."""
        frame = snapshot["frame"]
        scoped = county_scope(frame, scope) if frame is not None else None
        names = state_names(frame) if frame is not None else {}
        state = names.get((scope or {}).get("state"), "United States")
        tier = tier_label(scope["tier"]) if (scope or {}).get("tier") else "All tiers"
        rows = comparison_rows(frame, comparison) if frame is not None else []
        saved = [row["county_fips"] for row in rows]
        selected_row = None
        if scoped is not None and selected in set(scoped["county_fips"]):
            selected_row = scoped[scoped["county_fips"] == selected].iloc[0]
        listing = county_list(scoped, selected, query, page, mode) if scoped is not None else (
            "County list", "", [], "Unavailable", True, True
        )
        title = "Where reproductive care is missing" if state == "United States" else f"Provider supply across {state}"
        title = {"compare": "Compare county supply", "state": "Observed provider supply by state",
                 "method": "How to read the data"}.get(view, title)
        subhead = {
            "compare": "Two counties. The same measures. A clearer basis for follow-up.",
            "state": "States ranked by observed providers per 100,000 residents. The model is a labeled diagnostic.",
            "method": "Source records, descriptive thresholds and the limits of registered supply.",
        }.get(view, "Explore registered provider supply, county by county.")
        tray = [
            html.Div(f"COMPARISON / {len(rows)} OF 2 COUNTIES", className="eyebrow"),
            html.H2("Counties saved for comparison", className="section-title"),
            html.Div([
                html.Div([
                    html.Span(row["county_name"]),
                    html.Button("Remove", id={"type": "remove-county", "fips": row["county_fips"]},
                                n_clicks=0, className="atlas-button", type="button",
                                **{"aria-label": f'Remove {row["county_name"]} from comparison'}),
                ], className="saved-county") for row in rows
            ], className="saved-counties"),
            html.P("Choose one more county from search or the list." if len(rows) < 2
                   else "Ready to compare counts, populations and density.", className="small muted"),
        ]
        return {
            "summary": summary_view(scoped), "detail": detail_view(selected_row),
            "distribution": distribution(scoped) if scoped is not None else [],
            "list_title": listing[0], "list_note": listing[1], "list": listing[2],
            "caption": listing[3], "previous": listing[4], "next": listing[5],
            "state_label": state if state != "United States" else "All states",
            "tier_label": tier,
            "add_disabled": selected_row is None or selected in saved or len(saved) >= 2,
            "add_label": "Added to comparison" if selected in saved else "Add to comparison",
            "compare_disabled": len(rows) != 2, "compare_label": f"Compare ({len(rows)}/2)",
            "tray_hidden": not rows, "tray": tray, "tray_disabled": len(rows) != 2,
            "comparison": comparison_view(rows),
            "county_hidden": view != "county" or frame is None,
            "state_hidden": view != "state", "method_hidden": view != "method",
            "compare_hidden": view != "compare", "unavailable": frame is not None or view != "county",
            "title": title, "breadcrumb": f'COUNTY EXPLORER / {state.upper()} / {tier.upper()}'
            if view == "county" else f'OVARA / {view.upper()}',
            "subhead": subhead, "back_style": {} if view == "compare" else {"display": "none"},
            "compare_style": {} if view == "county" else {"display": "none"},
            "nav_county": "atlas-button" + (" active" if view in ("county", "compare") else ""),
            "nav_state": "atlas-button" + (" active" if view == "state" else ""),
            "nav_method": "atlas-button" + (" active" if view == "method" else ""),
        }

    app.clientside_callback(
        "function(payload) { return window.dash_clientside.atlas.renderMap(payload); }",
        Output("atlas-map-render-status", "children"), Input("atlas-map-payload", "data"),
    )
    app.clientside_callback(
        "function(ready, selected) { return window.dash_clientside.atlas.highlight(selected); }",
        Output("atlas-highlight-status", "children"),
        Input("atlas-map-render-status", "children"), Input("atlas-selected", "data"),
    )
    app.clientside_callback(
        "function(list, map) { return window.dash_clientside.atlas.mobileView(); }",
        Output("atlas-mobile-status", "children"),
        Input("mobile-list", "n_clicks"), Input("mobile-map", "n_clicks"),
    )
