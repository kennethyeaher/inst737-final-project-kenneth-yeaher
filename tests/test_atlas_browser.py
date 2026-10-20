"""Browser regression checks for the county exploration and comparison workflow."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

playwright_api = pytest.importorskip("playwright.sync_api")
from vis.dashboard import create_dashboard

ASSETS = Path(__file__).resolve().parents[1] / "docs/assets"


@pytest.fixture(scope="module")
def live_url():
    """Serve a real app on an available local port and shut it down after testing."""
    server = make_server("127.0.0.1", 0, create_dashboard().server, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    """Use a fresh browser context without touching the user's browser profile."""
    with playwright_api.sync_playwright() as runtime:
        options = {"headless": True}
        if os.environ.get("BROWSER_CHANNEL"):
            options["channel"] = os.environ["BROWSER_CHANNEL"]
        instance = runtime.chromium.launch(**options)
        yield instance
        instance.close()


@pytest.fixture
def page(browser, live_url):
    """Open an isolated desktop exploration and fail on unexpected script errors."""
    context = browser.new_context(viewport={"width": 1440, "height": 1220})
    current = context.new_page()
    errors = []
    current.on("pageerror", lambda error: errors.append(str(error)))
    current.goto(live_url)
    current.locator("#atlas-summary").get_by_text("1,029", exact=True).wait_for()
    current.locator("#atlas-map svg path").first.wait_for()
    yield current
    assert errors == []
    context.close()


def capture(page, name):
    """Refresh documentation captures only when explicitly requested by the caller."""
    if os.environ.get("OVARA_CAPTURE_DOCS") == "1":
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(ASSETS / name), full_page=True, type="jpeg", quality=90)


def test_explorer_and_comparison(page):
    """Save two real counties and compare the same counts and denominators."""
    expect = playwright_api.expect
    expect(page.locator("#atlas-map svg path")).to_have_count(3144)
    expect(page.locator("#open-comparison")).to_be_disabled()
    capture(page, "iris-explorer.jpg")
    page.locator("#add-comparison").click()
    page.get_by_role("button", name="Livingston Parish, Louisiana 1.39", exact=True).click()
    expect(page.locator("#atlas-detail")).to_contain_text("143,425")
    page.locator("#add-comparison").click()
    expect(page.locator("#open-comparison")).to_be_enabled()
    page.locator("#open-comparison").click()
    expect(page.locator("#comparison-content")).to_contain_text("108,205")
    expect(page.locator("#comparison-content")).to_contain_text("143,425")
    expect(page.locator("#comparison-content")).to_contain_text("0.47")
    capture(page, "iris-comparison.jpg")
    page.locator("#back-to-explorer").click()
    expect(page.locator("#comparison-tray")).to_contain_text("2 OF 2")
    page.locator("#reset-atlas").click()
    expect(page.locator("#comparison-tray")).to_be_hidden()
    expect(page.locator("#open-comparison")).to_be_disabled()


def test_filter_dialog_shows_the_current_scope_on_open(page):
    """The State and Access tier choices are never blank; they name the scope in effect."""
    expect = playwright_api.expect
    shown = "el => el.options[el.selectedIndex].text"
    page.locator("#open-state-filter").click()
    expect(page.locator("#draft-state")).to_have_value("all")
    expect(page.locator("#draft-tier")).to_have_value("all")
    assert page.locator("#draft-state").evaluate(shown) == "All states"
    assert page.locator("#draft-tier").evaluate(shown) == "All tiers"
    page.locator("#draft-state").select_option("MO")
    page.locator("#apply-filters").click()
    expect(page.locator("#atlas-summary")).to_contain_text("115")
    page.locator("#open-tier-filter").click()
    expect(page.locator("#draft-state")).to_have_value("MO")
    assert page.locator("#draft-tier").evaluate(shown) == "All tiers"
    page.locator("#draft-state").select_option("all")
    page.locator("#apply-filters").click()
    expect(page.locator("#atlas-summary")).to_contain_text("3,144")


def test_draft_cancel_and_applied_state_and_tier(page):
    """Cancel preserves the scope; Apply updates totals, paths and list together."""
    expect = playwright_api.expect
    page.locator("#open-state-filter").click()
    page.locator("#draft-state").select_option("MO")
    expect(page.locator("#atlas-summary")).to_contain_text("3,144")
    page.locator("#cancel-filters").click()
    expect(page.locator("#open-state-filter")).to_be_focused()
    expect(page.locator("#atlas-summary")).to_contain_text("3,144")
    page.locator("#open-state-filter").click()
    page.locator("#draft-state").select_option("MO")
    page.locator("#apply-filters").click()
    expect(page.locator("#atlas-summary")).to_contain_text("614,052")
    expect(page.locator("#atlas-summary")).to_contain_text("115")
    expect(page.locator("#atlas-map svg path")).to_have_count(115)
    expect(page.locator("#county-list")).to_contain_text("Warren County")
    page.locator("#open-tier-filter").click()
    page.locator("#draft-tier").select_option("access_desert")
    page.locator("#apply-filters").click()
    expect(page.locator("#atlas-map svg path")).to_have_count(48)
    expect(page.locator("#atlas-summary")).to_contain_text("100.0% of 48 counties")
    page.get_by_label("All counties", exact=True).check()
    expect(page.locator("#county-list")).to_contain_text("0.00")


def test_search_empty_state_and_fips_selection(page):
    """Literal search has a recovery path and supports selecting a county by FIPS."""
    expect = playwright_api.expect
    page.locator("#add-comparison").click()
    page.locator("#county-search").fill("zzzzz")
    expect(page.locator("#county-list")).to_contain_text("No counties match")
    expect(page.locator("#atlas-summary")).to_contain_text("1,029")
    page.locator("#clear-search").click()
    expect(page.locator("#comparison-tray")).to_contain_text("Cass County")
    page.locator("#county-search").fill("22063")
    result = page.get_by_role("button", name="Livingston Parish, Louisiana 1.39", exact=True)
    result.click()
    expect(page.locator("#atlas-detail")).to_contain_text("Livingston Parish")
    expect(page.locator("#atlas-detail")).to_contain_text("143,425")


def test_map_selection_has_a_native_keyboard_alternative(page):
    """Mouse selection and keyboard county selection update the same detail panel."""
    expect = playwright_api.expect
    original_box = page.locator("#atlas-map svg").get_attribute("viewBox")
    page.locator("#atlas-zoom-in").click()
    assert page.locator("#atlas-map svg").get_attribute("viewBox") != original_box
    page.locator("#atlas-zoom-reset").click()
    expect(page.locator("#atlas-map svg")).to_have_attribute("viewBox", original_box)
    page.locator('#atlas-map path[data-fips="22063"]').click(force=True)
    expect(page.locator("#atlas-detail")).to_contain_text("Livingston Parish")
    cass = page.get_by_role("button", name="Cass County, Missouri 0.92", exact=True)
    cass.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#atlas-detail")).to_contain_text("Cass County")
    expect(cass).to_have_attribute("aria-pressed", "true")


def test_mobile_layout_filters_and_comparison(page):
    """Small screens retain filters, comparison and an optional national map."""
    expect = playwright_api.expect
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#atlas-map-column")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    capture(page, "iris-mobile.jpg")
    page.locator("#open-state-filter").click()
    page.locator("#draft-state").select_option("MO")
    capture(page, "iris-filter.jpg")
    page.locator("#apply-filters").click()
    expect(page.locator("#atlas-summary")).to_contain_text("614,052")
    page.locator("#reset-atlas").click()
    page.locator("#add-comparison").click()
    page.get_by_role("button", name="Livingston Parish, Louisiana 1.39", exact=True).click()
    page.locator("#add-comparison").click()
    page.locator("#open-comparison").click()
    expect(page.locator(".comparison-mobile")).to_be_visible()
    expect(page.locator(".comparison-mobile")).to_contain_text("143,425")
    expect(page.locator(".comparison-table")).to_be_hidden()
    page.set_viewport_size({"width": 320, "height": 780})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
