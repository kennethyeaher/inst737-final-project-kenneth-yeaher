"""
Data quality tests for the county level access dataset.

These tests exist because a Census vintage mismatch between the ZIP to county
crosswalk and the county population table silently dropped every Connecticut
provider and published nine planning regions as access deserts. They assert
the properties that would have caught it: no state may lose its providers at
a geography join, and every county FIPS code the pipeline emits has to exist
in the population reference table.

Run with
    pytest tests/ -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from utils.fips import FIPS_TO_STATE

STATE_DATASET_FILE = Path("data/load/access_model_dataset.csv")
COUNTY_DATASET_FILE = Path("data/load/county_access_dataset.csv")
PROVIDER_FILE = Path("data/transformed/nppes_provider_clean.csv")
POPULATION_FILE = Path("data/reference_tables/county_population.csv")

# the 51 modeled states, meaning the 50 states plus DC
MODELED_STATES = set(FIPS_TO_STATE.values())

# share of in scope providers that has to survive the ZIP and population joins
MIN_PROVIDER_RETENTION = 0.96

# every county and county equivalent in the 51 modeled states
EXPECTED_COUNTY_ROWS = 3_144


@pytest.fixture(scope="module")
def state_dataset() -> pd.DataFrame:
    """State level access model dataset, one row per modeled state."""
    return pd.read_csv(STATE_DATASET_FILE)


@pytest.fixture(scope="module")
def county_dataset() -> pd.DataFrame:
    """County level access dataset, one row per county with FIPS codes kept as strings."""
    return pd.read_csv(
        COUNTY_DATASET_FILE,
        dtype={"county_fips": str, "state_fips": str},
    )


@pytest.fixture(scope="module")
def providers() -> pd.DataFrame:
    """Cleaned NPPES provider records, only the state column is needed here."""
    return pd.read_csv(PROVIDER_FILE, usecols=["practice_state"])


@pytest.fixture(scope="module")
def population() -> pd.DataFrame:
    """County population reference table that defines the valid county universe."""
    return pd.read_csv(POPULATION_FILE, dtype={"county_fips": str, "state_fips": str})


def test_every_state_with_providers_reaches_the_county_layer(state_dataset, county_dataset):
    """A state with providers in the state model must have providers in the county model."""
    states_with_providers = set(
        state_dataset.loc[state_dataset["provider_count"] > 0, "practice_state"]
    )

    county_totals = county_dataset.groupby("practice_state")["provider_count"].sum()
    states_in_county_layer = set(county_totals[county_totals > 0].index)

    missing = sorted(states_with_providers - states_in_county_layer)
    assert not missing, f"states with providers that vanish at the county layer: {missing}"


def test_no_state_is_entirely_zero_provider_counties(county_dataset):
    """No state may have every one of its counties reading zero providers."""
    county_totals = county_dataset.groupby("practice_state")["provider_count"].sum()

    all_zero = sorted(county_totals[county_totals == 0].index)
    assert not all_zero, f"states where every county reads zero providers: {all_zero}"


def test_provider_retention_through_the_county_joins(providers, county_dataset):
    """At least 96 percent of in scope providers survive the ZIP and population joins."""
    in_scope = providers["practice_state"].isin(MODELED_STATES).sum()
    retained = int(county_dataset["provider_count"].sum())

    retention = retained / in_scope
    assert retention >= MIN_PROVIDER_RETENTION, (
        f"only {retention:.2%} of {in_scope:,} in scope providers reached the county "
        f"dataset ({retained:,} retained)"
    )


def test_county_fips_codes_are_five_digits_and_known(county_dataset, population):
    """Every emitted county FIPS code is five characters and exists in the population table."""
    fips = county_dataset["county_fips"]

    bad_length = sorted(fips[fips.str.len() != 5].unique())
    assert not bad_length, f"county FIPS codes that are not five characters: {bad_length}"

    unknown = sorted(set(fips) - set(population["county_fips"]))
    assert not unknown, f"county FIPS codes missing from county_population.csv: {unknown}"


def test_county_dataset_row_count(county_dataset):
    """The county dataset covers all 3,144 counties in the modeled states."""
    assert len(county_dataset) == EXPECTED_COUNTY_ROWS
