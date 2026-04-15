import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
from pathlib import Path
from utils.logging_config import setup_logger

logger = setup_logger("ovara.eda")

# file paths

INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_DIR = Path("data/visualizations")

# reproductive health taxonomy code labels

TAXONOMY_LABELS = {
    "207V00000X": "Obstetrics & Gynecology",
    "207VC0200X": "Critical Care Medicine",
    "207VE0102X": "Reproductive Endocrinology",
    "207VF0040X": "Female Pelvic Medicine and Reconstructive Surgery",
    "207VG0400X": "Gynecology",
    "207VH0002X": "OB/GYN, Hospice and Palliative Medicine",
    "207VM0101X": "Maternal-Fetal Medicine",
    "207VX0000X": "Obstetrics",
    "207VX0201X": "Gynecologic Oncology",
    "207VR0500X": "Reproductive Endocrinology & Infertility",

    # midwifery
    "176B00000X": "Midwife",
    "367A00000X": "Certified Nurse Midwife",

    # nurse practitioner — women's health
    "363LW0102X": "Nurse Practitioner, Women's Health",
}

# category color mapping

CATEGORY_COLORS = {"obgyn": "#2563EB", "midwifery": "#7C3AED", "np": "#0891B2"}
ACCENT = "#2563EB"
MUTED = "#CBD5E1"


def _code_category(code: str) -> str:
    """derive provider category from taxonomy code prefix."""
    if code.startswith("207V"):
        return "obgyn"
    if code in ("176B00000X", "367A00000X"):
        return "midwifery"
    return "np"


def _style_axes(ax, title: str, subtitle: str) -> None:
    """apply consistent title, subtitle, and axis styling."""
    ax.set_title(title, fontsize=16, fontweight="bold", loc="left", pad=25)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=10.5, color="#64748B")
    ax.set_xlabel("")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color("#E2E8F0")
    ax.tick_params(axis="both", colors="#94A3B8")


def _save(filename: str) -> None:
    """save current figure and close."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"saved -> {filename}")


def load_clean_data() -> pd.DataFrame:
    """load cleaned reproductive health provider dataset."""
    logger.info("loading cleaned provider dataset...")
    df = pd.read_csv(INPUT_FILE, parse_dates=["provider_enumeration_date", "last_update_date"])
    logger.info(f"dataset shape: {df.shape}")
    return df


# visualizations

def provider_counts_by_state(df: pd.DataFrame):
    """horizontal bar chart of top 20 states by active provider count."""
    logger.info("building provider counts by state chart...")
    total = df.shape[0]

    counts = df["practice_state"].value_counts().head(20)
    states, values = counts.index.tolist()[::-1], counts.values.tolist()[::-1]
    pcts = [v / total * 100 for v in values]
    n = len(values)

    colors = [MUTED if i < (n - 5) else ACCENT for i in range(n)]

    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.barh(range(n), values, color=colors, height=0.7, edgecolor="none")
    ax.set_yticks(range(n))
    ax.set_yticklabels(states, fontsize=11, fontfamily="monospace")

    offset = max(values) * 0.02
    for bar, val, pct in zip(bars, values, pcts):
        ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                f"{val:,}  ({pct:.1f}%)", va="center", fontsize=10, color="#334155")

    _style_axes(ax, "Top 20 States by Reproductive Health Provider Count",
                f"{total:,} active reproductive health providers  •  Top 5 highlighted")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlim(0, max(values) * 1.35)
    _save("provider_counts_by_state.png")


def taxonomy_distribution(df: pd.DataFrame):
    """horizontal bar chart of reproductive specialties grouped by category."""
    logger.info("building taxonomy distribution chart...")
    total = df.shape[0]

    counts = df["taxonomy_code_1"].value_counts()
    codes = counts.index.tolist()
    labels = [TAXONOMY_LABELS.get(c, c) for c in codes][::-1]
    values = counts.values.tolist()[::-1]
    pcts = [v / total * 100 for v in values]
    cats = [_code_category(c) for c in codes][::-1]
    colors = [CATEGORY_COLORS[c] for c in cats]
    n = len(values)

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(range(n), values, color=colors, height=0.7, edgecolor="none", alpha=0.85)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=11)

    max_val = max(values)
    for bar, val, pct in zip(bars, values, pcts):
        ax.text(bar.get_width() + max(max_val * 0.015, 0.5), bar.get_y() + bar.get_height() / 2,
                f"{val:,}  ({pct:.1f}%)", va="center", fontsize=10, color="#334155")

    _style_axes(ax, "Reproductive Health Provider Specialties",
                f"{total:,} active providers across {n} specialties")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlim(0, max_val * 1.30)

    legend = [Patch(facecolor=CATEGORY_COLORS[k], alpha=0.85, label=l)
              for k, l in [("obgyn", "OB/GYN"), ("midwifery", "Midwifery"), ("np", "Nurse Practitioner")]]
    ax.legend(handles=legend, loc="lower right", fontsize=10, frameon=False)
    _save("taxonomy_distribution.png")


def provider_growth_trend(df: pd.DataFrame):
    """bar chart of annual provider enumerations with data quality handling."""
    logger.info("building provider growth trend chart...")

    trend = df.assign(year=df["provider_enumeration_date"].dt.year).groupby("year").size()
    complete = trend[trend.index <= 2024]
    partial = trend[trend.index == 2025]

    years, values = complete.index.tolist(), complete.values.tolist()
    peak = max(values)
    median_val = sorted(values)[len(values) // 2]

    fig, ax = plt.subplots(figsize=(13, 6.5))

    bar_colors = [ACCENT if v >= median_val else MUTED for v in values]
    bars = ax.bar(years, values, color=bar_colors, width=0.75, edgecolor="none")

    if not partial.empty:
        ax.bar(2025, partial.values[0], color="none", edgecolor=ACCENT,
               linewidth=1.5, width=0.75, hatch="///", label="2025 (partial year)")
        ax.text(2025, partial.values[0] + peak * 0.02, f"{partial.values[0]:,}",
                ha="center", va="bottom", fontsize=9, color=ACCENT)

    # label top quartile bars
    threshold = sorted(values)[-max(len(values) // 4, 1)]
    for bar, val in zip(bars, values):
        if val >= threshold:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + peak * 0.02,
                    f"{val:,}", ha="center", va="bottom", fontsize=9, color="#334155")

    _style_axes(ax, "Reproductive Health Provider Enumeration Trend (2005–2024)",
                "New reproductive health NPI registrations per year  •  2025 partial  •  2026 excluded (batch artifact)")
    ax.set_ylabel("New Providers", fontsize=11, color="#64748B")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xticks(range(2005, 2026))
    ax.set_xticklabels(range(2005, 2026), rotation=45, ha="right", fontsize=9)
    ax.legend(loc="upper left", fontsize=10, frameon=False)
    _save("provider_growth_trend.png")


def run_eda():
    """execute reproductive health EDA workflow."""
    try:
        df = load_clean_data()
        provider_counts_by_state(df)
        taxonomy_distribution(df)
        provider_growth_trend(df)
        logger.info("EDA workflow complete")

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during EDA: {e}")
        raise


if __name__ == "__main__":
    run_eda()