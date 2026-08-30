"""
Guards on the county findings card's prose.

The card used to describe access deserts unconditionally, so a state with
none of them read "0 have no registered provider ... They are access deserts
where the local workforce is missing" and reported how far its zero residents
travel. These tests keep the prose matched to what the scope actually holds.
"""

import pytest

from vis.county_visualizations import load_county_risk_data
from vis.findings_card import county_findings_card


@pytest.fixture(scope="module")
def county_data():
    return load_county_risk_data()


def card_text(component):
    """Flatten a Dash component tree down to its plain text."""
    if isinstance(component, str):
        return component

    if isinstance(component, (list, tuple)):
        return "".join(card_text(child) for child in component)

    children = getattr(component, "children", None)
    return card_text(children) if children is not None else ""


def scope_text(df, state_filter=None):
    """Render the county findings card for a scope and return its text."""
    return card_text(county_findings_card(df, state_filter=state_filter))


def test_a_scope_with_no_deserts_does_not_claim_any(county_data):
    # every connecticut planning region has providers after the vintage fix
    text = scope_text(county_data, "CT")

    assert "have no registered reproductive health provider" not in text
    assert "living in those access desert counties" not in text
    assert "clears the" in text


def test_a_scope_with_deserts_still_reports_them(county_data):
    text = scope_text(county_data, "AL")

    assert "have no registered reproductive health provider" in text
    assert "access deserts" in text


def test_the_national_card_reports_the_real_desert_count(county_data):
    text = scope_text(county_data)
    n_desert = int((county_data["provider_count"] == 0).sum())
    pop_desert = int(county_data[county_data["provider_count"] == 0]["total_population"].sum())

    assert f"{n_desert:,}" in text
    assert f"{pop_desert:,}" in text


@pytest.mark.parametrize("state_filter", [None, "CT", "AL", "NE"])
def test_every_card_carries_the_coverage_caveat(county_data, state_filter):
    # density counts registered addresses, not appointments, and the card has to say so
    text = scope_text(county_data, state_filter)

    assert "not the same as having access" in text


def test_the_median_density_is_never_editorialized_as_low(county_data):
    # "a median density of just 24.1" called a well served figure low
    text = scope_text(county_data, "CT")

    assert "median density of just" not in text
    assert "Well Served tier" in text
