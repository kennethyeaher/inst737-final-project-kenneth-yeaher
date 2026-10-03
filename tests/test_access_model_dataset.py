"""
Guards on the state level denominator.

The state dataset used to divide provider counts by a sum of CBSA metro
populations. That table carries one row per county with the whole metro's
population on each row, so Georgia's denominator reached 198,940,717 against a
true 10.7 million while Wyoming was under counted. The inflation ran 0.32x to
28.8x, which scrambled the ranking rather than scaling it. These tests hold the
denominator to what a state population can actually be, and check that it
tracks the numerator at all.

Run with
    pytest tests/ -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scipy.stats import spearmanr

from analysis.regression_model import FEATURE_COLUMNS

STATE_DATASET_FILE = Path("data/load/access_model_dataset.csv")

# no state is smaller than Wyoming or larger than California
MIN_STATE_POPULATION = 400_000
MAX_STATE_POPULATION = 45_000_000

# the 51 modeled states have to add up to roughly the national population
MIN_NATIONAL_POPULATION = 320_000_000
MAX_NATIONAL_POPULATION = 350_000_000

# plausible range for reproductive health providers per 100k residents
MIN_DENSITY = 5
MAX_DENSITY = 200

# a denominator that tracks its numerator ranks states the same way
MIN_COUNT_POPULATION_SPEARMAN = 0.9

EXPECTED_STATE_ROWS = 51

# columns built out of provider_count, which is the numerator of the target.
# a rate model cannot use a component of its own target as a predictor
TARGET_DERIVED_FEATURES = {
    "provider_count": "the numerator of the target",
    "providers_per_100k": "the target itself",
    "recent_provider_growth": "a strict subset of provider_count",
    "growth_per_100k": "a subset of provider_count over the target denominator",
}


@pytest.fixture(scope="module")
def state_dataset() -> pd.DataFrame:
    """State level access model dataset, one row per modeled state."""
    return pd.read_csv(STATE_DATASET_FILE)


def test_every_state_population_is_plausible(state_dataset):
    """No state population may fall outside the range a real US state occupies."""
    population = state_dataset.set_index("practice_state")["state_population"]

    out_of_range = population[
        (population < MIN_STATE_POPULATION) | (population > MAX_STATE_POPULATION)
    ]

    assert out_of_range.empty, (
        "state populations outside "
        f"{MIN_STATE_POPULATION:,} to {MAX_STATE_POPULATION:,}: "
        f"{out_of_range.astype('int64').to_dict()}"
    )


def test_state_populations_sum_to_the_national_population(state_dataset):
    """The 51 state populations have to add up to roughly the US population."""
    total = state_dataset["state_population"].sum()

    assert MIN_NATIONAL_POPULATION <= total <= MAX_NATIONAL_POPULATION, (
        f"state populations sum to {total:,.0f}, expected between "
        f"{MIN_NATIONAL_POPULATION:,} and {MAX_NATIONAL_POPULATION:,}"
    )


def test_provider_density_is_plausible(state_dataset):
    """Provider density per 100k has to sit in a range a real workforce could produce."""
    density = state_dataset.set_index("practice_state")["providers_per_100k"]

    out_of_range = density[(density < MIN_DENSITY) | (density > MAX_DENSITY)]

    assert out_of_range.empty, (
        f"provider density outside {MIN_DENSITY} to {MAX_DENSITY} per 100k: "
        f"{out_of_range.round(2).to_dict()}"
    )


def test_denominator_tracks_the_numerator(state_dataset):
    """States with more providers have more residents, so the two must rank together."""
    rho, p_value = spearmanr(
        state_dataset["provider_count"],
        state_dataset["state_population"],
    )

    assert rho > MIN_COUNT_POPULATION_SPEARMAN, (
        f"provider_count and state_population correlate at rho {rho:.3f} "
        f"(p {p_value:.4f}), expected above {MIN_COUNT_POPULATION_SPEARMAN}"
    )


def test_dataset_shape_and_completeness(state_dataset):
    """The dataset covers all 51 modeled states with no gaps in the modeling columns."""
    assert len(state_dataset) == EXPECTED_STATE_ROWS

    required = ["provider_count", "state_population", "providers_per_100k"]
    nulls = state_dataset[required].isna().sum()

    assert nulls.sum() == 0, f"nulls in modeling columns: {nulls[nulls > 0].to_dict()}"


def test_recent_growth_is_a_subset_of_provider_count(state_dataset):
    """Recently enumerated providers are counted inside provider_count, in every state."""
    over_count = state_dataset[
        state_dataset["recent_provider_growth"] > state_dataset["provider_count"]
    ]

    assert over_count.empty, (
        "states where recent_provider_growth exceeds provider_count: "
        f"{over_count['practice_state'].tolist()}"
    )


def test_no_model_feature_is_derived_from_the_target():
    """No feature may be arithmetically derived from provider_count."""
    leaking = {
        column: reason
        for column, reason in TARGET_DERIVED_FEATURES.items()
        if column in FEATURE_COLUMNS
    }

    assert not leaking, (
        "FEATURE_COLUMNS contains features derived from the target: "
        + ", ".join(f"{column} is {reason}" for column, reason in leaking.items())
    )
