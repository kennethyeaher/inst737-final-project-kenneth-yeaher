"""
Build the published figure set from tables the pipeline has already written.

This module reads data/model_outputs, data/load and data/reference_tables, then
writes every published figure to data/figures. It does not re run a pipeline
stage, refit a model, or recompute a classification. Counts, tiers and
populations are read from the CSVs so a figure can never drift from the numbers
in the README.

Run after main.py:
    python -m vis.make_figures

Outputs written to data/figures:
    provider_density_by_state.png   providers per 100k, all states ranked
    taxonomy_distribution.png       specialty mix, grouped by category
    county_tier_distribution.png    counties and residents per access tier
    provider_growth_trend.png       annual enumeration counts

Figures whose inputs are missing are skipped rather than failing the run.

The residual based figures, the access gap choropleth, the predicted against
actual scatter, and the clustering plot, are not built here yet. They all
derive from the state regression, whose denominator has since been rebuilt on
ACS county population. Adding them is a separate change.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import Patch

from utils.logging_config import setup_logger
from vis._brand import BRAND, COUNTY_TIER_COLORS

logger = setup_logger("ovara.make_figures")


# input tables, all written by earlier pipeline stages

ACCESS_MODEL_FILE = Path("data/load/access_model_dataset.csv")
COUNTY_SUMMARY_FILE = Path("data/model_outputs/county_risk_summary.csv")
PROVIDER_CLEAN_FILE = Path("data/transformed/nppes_provider_clean.csv")

OUTPUT_DIR = Path("data/figures")
FIGURE_DPI = 200

# a plausible us state population, used to decide whether the density
# denominator can be trusted enough to draw a rate

MIN_STATE_POPULATION = 400_000
MAX_STATE_POPULATION = 45_000_000

# the NPI system opened in 2005 and enrolled most existing clinicians by 2007,
# so these years describe the registry rather than the workforce

ROLLOUT_YEARS = (2005, 2007)

# figure surface and ink, drawn from the brand so the published figures sit on
# the same cream as the dashboard's findings card

INK = BRAND["plum_ink"]
INK_SOFT = "#5B4A69"
MUTED = "#8B7D96"
SURFACE = BRAND["cream"]
GRID = BRAND["cream_deep"]

# the access tier ramp is defined once in vis/_brand.py and shared with the
# dashboard, so a tier cannot mean one colour in a figure and another on screen

TIER_COLORS = COUNTY_TIER_COLORS

TIER_ORDER = ["access_desert", "critical", "underserved", "adequate", "well_served"]

TIER_LABELS = {
    "access_desert": "Access Desert",
    "critical": "Critical",
    "underserved": "Underserved",
    "adequate": "Adequate",
    "well_served": "Well Served",
}

# three nominal specialty groups. the teal is a brand addition, because no pair
# drawn from the original palette cleared colour blind separation and this
# chart carries its categories in colour. the coral sits just under the 3:1
# contrast guideline, which the chart's direct value labels relieve.

CATEGORY_COLORS = {
    "OB/GYN": BRAND["iris_deep"],
    "Midwifery": BRAND["coral"],
    "Nurse Practitioner": BRAND["teal"],
}

# taxonomy code to display label and category, mirroring
# REPRODUCTIVE_HEALTH_TAXONOMY in etl/transform.py

TAXONOMY_LABELS = {
    "207V00000X": ("Obstetrics and Gynecology", "OB/GYN"),
    "207VC0200X": ("Critical Care Medicine", "OB/GYN"),
    "207VE0102X": ("Reproductive Endocrinology", "OB/GYN"),
    "207VF0040X": ("Female Pelvic Medicine and Reconstructive Surgery", "OB/GYN"),
    "207VG0400X": ("Gynecology", "OB/GYN"),
    "207VH0002X": ("OB/GYN, Hospice and Palliative Medicine", "OB/GYN"),
    "207VM0101X": ("Maternal Fetal Medicine", "OB/GYN"),
    "207VX0000X": ("Obstetrics", "OB/GYN"),
    "207VX0201X": ("Gynecologic Oncology", "OB/GYN"),
    "207VR0500X": ("Reproductive Endocrinology and Infertility", "OB/GYN"),
    "176B00000X": ("Midwife", "Midwifery"),
    "367A00000X": ("Certified Nurse Midwife", "Midwifery"),
    "363LW0102X": ("Nurse Practitioner, Women's Health", "Nurse Practitioner"),
}

# font families tried in order. matplotlib resolves by family name rather than
# by absolute path, which keeps this working on both linux and macos, and
# DejaVu Sans always ships with matplotlib so the last entry cannot fail.

FONT_CANDIDATES = ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"]


def resolve_font_family() -> str:
    """
    Return the first installed font family from FONT_CANDIDATES.

    Falls back to DejaVu Sans, which matplotlib bundles, so a missing system
    font never silently drops the figure to a default that ignores sizing.
    """
    installed = {font.name for font in font_manager.fontManager.ttflist}

    for family in FONT_CANDIDATES:
        if family in installed:
            return family

    return "DejaVu Sans"


def apply_style() -> None:
    """Set the shared matplotlib style so every figure matches the dashboard."""
    plt.rcParams.update({
        "font.family": resolve_font_family(),
        "font.size": 11,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK_SOFT,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.edgecolor": GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


# loading

def read_table(path: Path, **kwargs) -> pd.DataFrame | None:
    """
    Read one pipeline table, returning None when it is absent.

    A missing table means the stage that writes it has not run. That should
    skip one figure, not abort the whole figure set.
    """
    if not path.exists():
        logger.warning(f"missing input, skipping figures that need it: {path}")
        return None

    return pd.read_csv(path, **kwargs)


def build_state_density(access_model: pd.DataFrame) -> pd.DataFrame:
    """
    Rank states by the provider density the pipeline already published.

    This used to sum county population itself, which meant the denominator
    check below could only ever pass. Reading state_population from the
    published table makes that check load bearing: a bad denominator now
    reaches this function instead of being recomputed away from it.
    """
    missing = {"state_population", "providers_per_100k"} - set(access_model.columns)
    if missing:
        raise ValueError(f"access model dataset is missing columns: {sorted(missing)}")

    return access_model.sort_values("providers_per_100k")


def is_denominator_trustworthy(state_density: pd.DataFrame) -> bool:
    """
    Report whether every state population falls in a believable range.

    build_state_density reads state_population straight from the published
    table, so this check is what stops a bad denominator reaching a published
    figure. An earlier version of the pipeline put Georgia at 199 million by
    summing each metro area once per county in it, and nothing caught it.
    """
    population = state_density["state_population"]
    outside = state_density[
        (population < MIN_STATE_POPULATION) | (population > MAX_STATE_POPULATION)
    ]

    if outside.empty:
        return True

    logger.warning(
        "state population outside a plausible range for "
        f"{outside['practice_state'].tolist()}, skipping the rate figures"
    )
    return False


# shared drawing helpers

def titled(ax, title: str, subtitle: str | None = None) -> None:
    """Place the title and optional subtitle above the axes without collision."""
    ax.text(0, 1.10, title, transform=ax.transAxes,
            fontsize=15, fontweight="bold", color=INK, va="bottom")

    if subtitle:
        ax.text(0, 1.035, subtitle, transform=ax.transAxes,
                fontsize=10.5, color=MUTED, va="bottom")


def save(fig, filename: str) -> Path:
    """Write one figure to the output folder and return its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename

    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)

    logger.info(f"wrote -> {output_path}")
    return output_path


# figures

def plot_provider_density_by_state(state_density: pd.DataFrame) -> Path:
    """
    Rank every state by providers per 100,000 residents.

    This replaces the old raw count chart. Provider count correlates with state
    population at r = 0.99, so a count ranking is a population ranking and says
    nothing about access.
    """
    # plotly and matplotlib both draw the first row at the bottom, so sort
    # descending to put the thinnest state at the top where the subtitle points
    data = state_density.sort_values("providers_per_100k", ascending=False)
    national = data["provider_count"].sum() / data["state_population"].sum() * 100_000

    fig, ax = plt.subplots(figsize=(9, 12))
    positions = list(range(len(data)))

    # highlight from the density values rather than the row index, because the
    # frame is sorted descending and an index based rule silently highlighted
    # the ten best served states instead
    thinnest_cutoff = data["providers_per_100k"].nsmallest(10).max()
    colors = [
        TIER_COLORS["critical"] if value <= thinnest_cutoff else TIER_COLORS["adequate"]
        for value in data["providers_per_100k"]
    ]

    ax.barh(positions, data["providers_per_100k"], color=colors, height=0.72, zorder=3)
    ax.axvline(national, color=TIER_COLORS["access_desert"], linewidth=2,
               linestyle="--", zorder=4)

    # anchor the label beside the shortest bars, which sit at the top of a
    # descending sort, so it cannot collide with the longest one
    ax.text(national + 0.7, len(data) - 1.4, f"national {national:.0f} per 100k",
            color=TIER_COLORS["access_desert"], fontsize=10, fontweight="bold")

    for position, value in zip(positions, data["providers_per_100k"]):
        ax.text(value + 0.5, position, f"{value:.1f}", va="center",
                fontsize=9, color=INK_SOFT)

    ax.set_yticks(positions, data["state_name"], fontsize=9.5)
    ax.set_xlabel("Reproductive health providers per 100,000 residents")
    ax.set_xlim(0, data["providers_per_100k"].max() * 1.12)
    ax.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    titled(ax, "Provider supply per capita, thinnest states first",
           "The ten thinnest are highlighted. A raw provider count would rank these states by population instead.")

    fig.tight_layout()
    return save(fig, "provider_density_by_state.png")


def plot_taxonomy_distribution(providers: pd.DataFrame) -> Path:
    """
    Show the specialty mix, grouped by category rather than interleaved.

    The old version sorted every specialty by count and carried the category in
    colour alone, with two hues that measured delta E 0.4 under deuteranopia.
    Grouping puts the categories in position as well as colour, so the chart
    still reads without colour vision.
    """
    counts = providers["taxonomy_code_1"].value_counts()
    total = int(counts.sum())

    rows = [
        {"label": label, "category": category, "count": int(counts.get(code, 0))}
        for code, (label, category) in TAXONOMY_LABELS.items()
    ]
    data = pd.DataFrame(rows)

    # order by category, then by size inside each category, so the groups sit
    # together and the reader can find them without the legend
    category_order = list(CATEGORY_COLORS)
    data["category_rank"] = data["category"].map(category_order.index)
    data = data.sort_values(["category_rank", "count"], ascending=[False, True])

    fig, ax = plt.subplots(figsize=(11, 8))

    # a gap between category blocks makes the grouping visible on its own
    positions, cursor, previous = [], 0.0, None
    for category in data["category"]:
        if previous is not None and category != previous:
            cursor += 1.0
        positions.append(cursor)
        cursor += 1.0
        previous = category

    colors = [CATEGORY_COLORS[category] for category in data["category"]]
    ax.barh(positions, data["count"], color=colors, height=0.74, zorder=3)

    for position, value in zip(positions, data["count"]):
        share = value / total * 100 if total else 0.0
        ax.text(value + total * 0.006, position, f"{value:,}  ({share:.1f}%)",
                va="center", fontsize=10, color=INK_SOFT)

    ax.set_yticks(positions, data["label"], fontsize=10)
    ax.set_xlabel("Registered providers")
    ax.set_xlim(0, data["count"].max() * 1.28)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _: f"{int(value):,}"))
    ax.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)

    present = int((data["count"] > 0).sum())
    ax.legend(
        handles=[Patch(facecolor=color, label=name) for name, color in CATEGORY_COLORS.items()],
        loc="lower right", frameon=False, fontsize=10,
    )
    titled(ax, "Who counts as a reproductive health provider",
           f"{total:,} providers across {present} of the 13 tracked taxonomy codes. Bars are grouped by category.")

    fig.tight_layout()
    return save(fig, "taxonomy_distribution.png")


def plot_county_tier_distribution(summary: pd.DataFrame) -> Path:
    """
    Show counties and residents in each access tier, read from the tier summary.

    Two panels because counties and people tell opposite stories. A third of
    counties are access deserts and they hold three percent of the population.
    """
    data = summary.set_index("risk_tier").reindex(TIER_ORDER).reset_index()
    labels = [TIER_LABELS[tier] for tier in data["risk_tier"]]
    colors = [TIER_COLORS[tier] for tier in data["risk_tier"]]
    positions = list(range(len(data)))[::-1]

    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5.4))

    left.barh(positions, data["county_count"], color=colors, height=0.7, zorder=3)
    for position, value in zip(positions, data["county_count"]):
        left.text(value + 12, position, f"{value:,}", va="center",
                  fontsize=10.5, fontweight="bold", color=INK)
    left.set_yticks(positions, labels, fontsize=10.5)
    left.set_xlabel("Counties")
    left.set_xlim(0, data["county_count"].max() * 1.18)

    millions = data["total_population"] / 1e6
    right.barh(positions, millions, color=colors, height=0.7, zorder=3)
    for position, value in zip(positions, millions):
        right.text(value + 3, position, f"{value:.1f}M", va="center",
                   fontsize=10.5, fontweight="bold", color=INK)
    right.set_yticks(positions, [""] * len(positions))
    right.set_xlabel("Residents, millions")
    right.set_xlim(0, millions.max() * 1.18)

    for ax in (left, right):
        ax.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.7, zorder=0)
        ax.set_axisbelow(True)

    fig.suptitle("Counties and residents by access tier", x=0.008, ha="left",
                 fontsize=15, fontweight="bold", color=INK)
    county_share = data.loc[data["risk_tier"] == "access_desert", "county_count"].iloc[0] / data["county_count"].sum()
    people_share = data.loc[data["risk_tier"] == "access_desert", "total_population"].iloc[0] / data["total_population"].sum()

    fig.text(0.008, 0.90,
             "The same five tiers counted two ways. Access deserts are "
             f"{county_share:.0%} of counties and {people_share:.0%} of the population.",
             fontsize=10.5, color=MUTED)

    fig.tight_layout(rect=[0, 0, 1, 0.88])
    return save(fig, "county_tier_distribution.png")


def plot_provider_growth_trend(providers: pd.DataFrame) -> Path:
    """
    Show when the current workforce was issued its NPI.

    Half this series is the 2005 to 2007 rollout of the NPI system itself, so
    the rollout is called out rather than left to read as a hiring surge.
    Enumeration marks the issue of an identifier, not the start of practice.
    The final year is partial and is excluded rather than drawn as a bar that
    is invisible next to the rollout peak.
    """
    years = pd.to_datetime(providers["provider_enumeration_date"], errors="coerce").dt.year
    counts = years.dropna().astype(int).value_counts().sort_index()
    counts = counts[counts.index >= ROLLOUT_YEARS[0]]

    partial_year = int(counts.index.max())
    partial_count = int(counts.loc[partial_year])
    counts = counts[counts.index < partial_year]

    rollout = counts[counts.index <= ROLLOUT_YEARS[1]]
    steady = counts[counts.index > ROLLOUT_YEARS[1]]
    rollout_share = rollout.sum() / counts.sum()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(rollout.index, rollout.values, color=TIER_COLORS["access_desert"],
           width=0.76, zorder=3, label="NPI system rollout")
    ax.bar(steady.index, steady.values, color=TIER_COLORS["critical"],
           width=0.76, zorder=3, label="Steady state registration")

    ax.annotate(
        f"The rollout of the NPI system is {rollout_share:.0%} of this series",
        xy=(ROLLOUT_YEARS[1] + 0.4, rollout.max() * 0.86),
        xytext=(14, 0), textcoords="offset points",
        fontsize=10.5, fontweight="bold", color=TIER_COLORS["access_desert"],
        va="center",
    )

    ax.set_ylabel("Providers first registered")
    ax.set_xlabel("NPI enumeration year")
    ax.set_xticks(list(range(counts.index.min(), counts.index.max() + 1, 2)))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _: f"{int(value):,}"))
    ax.legend(frameon=False, fontsize=10, loc="upper right")
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    titled(ax, "When the current workforce was first registered",
           f"Enumeration marks the issue of an NPI, not the start of practice. {partial_year} is excluded as a partial year with {partial_count:,} records.")

    fig.tight_layout()
    return save(fig, "provider_growth_trend.png")


# entry point

def main() -> None:
    """Build every figure whose inputs are present and report what was written."""
    apply_style()

    access_model = read_table(ACCESS_MODEL_FILE)
    county_summary = read_table(COUNTY_SUMMARY_FILE)
    providers = read_table(
        PROVIDER_CLEAN_FILE,
        usecols=["taxonomy_code_1", "provider_enumeration_date"],
    )

    written: list[Path] = []

    if access_model is not None:
        state_density = build_state_density(access_model)

        if is_denominator_trustworthy(state_density):
            written.append(plot_provider_density_by_state(state_density))

    if providers is not None:
        written.append(plot_taxonomy_distribution(providers))
        written.append(plot_provider_growth_trend(providers))

    if county_summary is not None:
        written.append(plot_county_tier_distribution(county_summary))

    logger.info(f"figures written: {len(written)}")
    for output_path in written:
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
