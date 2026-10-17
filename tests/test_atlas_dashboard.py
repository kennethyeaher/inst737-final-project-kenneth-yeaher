"""Integration checks for atlas transitions, rendered values and recovery."""

from types import SimpleNamespace

import pytest
from dash import no_update
from dash.exceptions import PreventUpdate

import vis.atlas_callbacks as callbacks
import vis.atlas_model as model
from vis.dashboard import create_dashboard


def callback(app, name):
    """Find the unwrapped application callback by its declared function name."""
    return next(
        item["callback"].__wrapped__
        for item in app.callback_map.values()
        if "callback" in item and getattr(item["callback"], "__wrapped__", None)
        and item["callback"].__wrapped__.__name__ == name
    )


def text_content(node):
    """Flatten Dash components for semantic assertions without snapshotting markup."""
    if node is None:
        return ""
    if isinstance(node, (str, int, float)):
        return str(node)
    if isinstance(node, (list, tuple)):
        return " ".join(text_content(child) for child in node)
    return text_content(getattr(node, "children", None))


@pytest.fixture(scope="module")
def app():
    """Build the real application against the supplied data files."""
    return create_dashboard()


def values(**changes):
    """Provide a browser's state before an explicit interaction."""
    current = dict(
        current_scope={"state": "", "tier": ""},
        current_selected="29037", current_comparison=[],
        current_view="county", current_revision=0,
        draft_state_value="", draft_tier_value="",
        choose=[0], remove=[0], map_event=None,
    )
    current.update(changes)
    return current


def render(app, **changes):
    """Render a county view from explicit browser state."""
    params = dict(scope={"state": "", "tier": ""}, selected="29037",
                  comparison=[], view="county", query="", page=0, mode="ranked", revision=0)
    params.update(changes)
    return callback(app, "render_view")(**params)


def action(app, monkeypatch, event, **changes):
    """Exercise the real callback with a controlled triggering component."""
    monkeypatch.setattr(callbacks, "ctx", SimpleNamespace(triggered_id=event))
    return callback(app, "handle_action")(**values(**changes))


def test_application_endpoints_and_asset_delivery(app):
    """The entry point serves a complete layout and the local design assets."""
    client = app.server.test_client()
    for route in ["/", "/_dash-layout", "/_dash-dependencies", "/assets/atlas.css", "/assets/atlas.js"]:
        assert client.get(route).status_code == 200


def test_default_view_exposes_correct_counts_and_selection(app):
    """Initial content pairs the county finding with the selected county's denominator."""
    result = render(app)
    assert "1,029" in text_content(result["summary"])
    assert "10,917,875" in text_content(result["summary"])
    assert "108,205" in text_content(result["detail"])
    assert result["compare_disabled"] is True


def test_cancel_preserves_applied_scope_and_saved_comparison(app, monkeypatch):
    """Draft changes cannot leak into the active scope through Cancel."""
    result = action(app, monkeypatch, "cancel-filters",
                    current_scope={"state": "MO", "tier": ""},
                    current_comparison=["29037"], draft_state_value="AL")
    assert result["scope"] is no_update
    assert result["comparison"] is no_update
    assert result["draft_state"] == "MO"
    assert result["modal"] is False


def test_apply_changes_scope_and_clears_outside_selection(app, monkeypatch):
    """Applying Missouri clears a Louisiana selection while retaining saved comparison."""
    result = action(app, monkeypatch, "apply-filters", current_selected="22063",
                    current_comparison=["29037", "22063"], draft_state_value="MO")
    assert result["scope"] == {"state": "MO", "tier": ""}
    assert result["selected"] is None
    assert result["comparison"] is no_update
    view = render(app, scope=result["scope"], selected=None)
    assert "614,052" in text_content(view["summary"])
    assert "115" in text_content(view["summary"])
    assert "Warren County" in text_content(view["list"])
    assert "Livingston Parish" not in text_content(view["list"])


def test_state_and_tier_scope_reaches_summary_list_and_distribution(app):
    """Zero supply is a real filtered result, with no invented populated counties."""
    result = render(app, scope={"state": "MO", "tier": "access_desert"}, mode="all", selected=None)
    assert "48" in text_content(result["summary"])
    assert "48" in text_content(result["distribution"])
    assert "0.00" in text_content(result["list"])


def test_empty_search_preserves_summary_and_comparison(app):
    """A query with no matches has a recovery message and leaves saved records visible."""
    result = render(app, query="zzzzz", comparison=["29037"])
    assert "No counties match" in text_content(result["list"])
    assert "1,029" in text_content(result["summary"])
    assert result["tray_hidden"] is False


def test_clear_search_does_not_clear_comparison(app, monkeypatch):
    """Clearing text is separate from resetting the whole exploration."""
    result = action(app, monkeypatch, "clear-search", current_comparison=["29037"])
    assert result["query"] == ""
    assert result["comparison"] is no_update


def test_two_counties_enable_comparison_and_prevent_a_third(app, monkeypatch):
    """Comparison controls reflect distinct valid records, not click counts."""
    result = render(app, comparison=["29037", "22063"], selected="48427")
    assert result["compare_disabled"] is False
    assert result["add_disabled"] is True
    blocked = action(app, monkeypatch, "add-comparison", current_selected="48427",
                     current_comparison=["29037", "22063"])
    assert blocked["comparison"] == ["29037", "22063"]


def test_comparison_includes_both_denominators(app):
    """The comparison view never substitutes national or selected county totals."""
    result = render(app, comparison=["29037", "22063"], view="compare")
    content = text_content(result["comparison"])
    assert all(value in content for value in ["108,205", "143,425", "0.92", "1.39", "0.47"])


def test_reset_restores_known_start_and_clears_saved_counties(app, monkeypatch):
    """Reset restores the national scope and clears accumulated comparison state."""
    result = action(app, monkeypatch, "reset-atlas",
                    current_scope={"state": "MO", "tier": "critical"},
                    current_comparison=["29037", "22063"])
    assert result["scope"] == {"state": "", "tier": ""}
    assert result["comparison"] == []
    assert result["selected"] == "29037"
    assert result["query"] == ""


def test_map_selection_outside_scope_is_rejected(app, monkeypatch):
    """A stale or forged map event cannot select a county outside applied filters."""
    with pytest.raises(PreventUpdate):
        action(app, monkeypatch, "atlas-map-event",
               current_scope={"state": "MO", "tier": ""}, map_event={"fips": "22063"})


def test_removing_county_returns_to_explorer(app, monkeypatch):
    """Removing a saved record leaves the other record available."""
    result = action(app, monkeypatch, {"type": "remove-county", "fips": "22063"},
                    remove=[1], current_comparison=["29037", "22063"])
    assert result["comparison"] == ["29037"]
    assert result["view"] == "county"


def test_missing_snapshot_never_renders_zero_and_retry_recovers(monkeypatch):
    """A load failure is explicit, and Retry reads the source again."""
    real_loader = model.load_atlas_data
    attempts = []

    def loader():
        """Fail once to exercise recovery without modifying a dataset file."""
        attempts.append(True)
        if len(attempts) == 1:
            raise FileNotFoundError("Snapshot unavailable")
        return real_loader()

    monkeypatch.setattr(model, "load_atlas_data", loader)
    missing_app = create_dashboard()
    before = render(missing_app)
    assert "Unavailable" in text_content(before["summary"])
    assert before["unavailable"] is False
    assert before["county_hidden"] is True
    action(missing_app, monkeypatch, "retry-atlas")
    after = render(missing_app, revision=1)
    assert after["unavailable"] is True
    assert "1,029" in text_content(after["summary"])
