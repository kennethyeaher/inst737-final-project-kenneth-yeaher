import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path


INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_DIR = Path("data/visualizations")

# reproductive health taxonomy code labels
 
TAXONOMY_LABELS = {
    "207V00000X": "Obstetrics & Gynecology",
    "207VC0200X": "OB/GYN — Critical Care Medicine",
    "207VE0102X": "OB/GYN — Reproductive Endocrinology",
    "207VF0040X": "OB/GYN — Female Pelvic Medicine",
    "207VG0400X": "OB/GYN — Gynecology",
    "207VH0002X": "OB/GYN — Hospice and Palliative Medicine",
    "207VM0101X": "OB/GYN — Maternal-Fetal Medicine",
    "207VX0000X": "OB/GYN — Obstetrics",
    "207VX0201X": "OB/GYN — Gynecologic Oncology",
    "207VR0500X": "OB/GYN — REI",
    "176B00000X": "Midwife",
    "367A00000X": "Certified Nurse Midwife",
    "363LW0102X": "Nurse Practitioner — Women's Health",
}
 

# Utility 

def save_plot(filename: str):
    """Standard helper to save plots cleanly."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename)
    plt.close()
    print(f"[EDA] Saved → {filename}")

# Load 

def load_clean_data() -> pd.DataFrame:
    """
    Load cleaned provider dataset.
    This dataset is already filtered + standardized from transform stage.
    """
    print("[EDA] Loading cleaned provider dataset...")
 
    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["provider_enumeration_date", "last_update_date"]
    )
 
    print(f"[EDA] Dataset shape: {df.shape}")
    
    return df

# Visualization 

def provider_counts_by_state(df: pd.DataFrame):
    """Horizontal bar chart of top 20 states by active provider count."""
    print("[EDA] Building provider counts by state chart...")
 
    total = df.shape[0]
 
    counts = df["practice_state"].value_counts().head(20)
    states = counts.index.tolist()
    values = counts.values.tolist()
    percentages = [v / total * 100 for v in values]
 
    # reverse for top-down horizontal layout
    states = states[::-1]
    values = values[::-1]
    percentages = percentages[::-1]
 
    # top 5 get accent color, rest muted
    accent = "#2563EB"
    muted = "#CBD5E1"
    n = len(values)
    colors = [muted if i < (n - 5) else accent for i in range(n)]
 
    fig, ax = plt.subplots(figsize=(12, 8))
 
    bars = ax.barh(range(n), values, color=colors, height=0.7, edgecolor="none")
 
    ax.set_yticks(range(n))
    ax.set_yticklabels(states, fontsize=11, fontfamily="monospace")
 
    # count + percentage labels
    for bar, val, pct in zip(bars, values, percentages):
        ax.text(
            bar.get_width() + 25,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,}  ({pct:.1f}%)",
            va="center",
            fontsize=10,
            color="#334155",
        )
 
    top5_pct = sum(percentages[-5:])
 
    ax.set_title(
        "Top 20 States by Active Provider Count",
        fontsize=16, fontweight="bold", loc="left", pad=25,
    )
 
    ax.text(
        0, 1.02,
        f"{total:,} active providers  •  Top 5 states account for {top5_pct:.0f}% of all providers",
        transform=ax.transAxes,
        fontsize=10.5, color="#64748B",
    )
 
    # clean up axes
    ax.set_xlabel("")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.spines["left"].set_color("#E2E8F0")
    ax.tick_params(axis="x", colors="#94A3B8")
    ax.set_xlim(0, values[-1] * 1.22)
 
    plt.tight_layout()
    save_plot("provider_counts_by_state.png")
 
 
def taxonomy_distribution(df: pd.DataFrame):
    """Horizontal bar chart of top provider specialties by taxonomy code."""
    print("[EDA] Building taxonomy distribution chart...")
 
    total = df.shape[0]
 
    counts = df["taxonomy_code_1"].value_counts().head(15)
    labels = [TAXONOMY_LABELS.get(code, code) for code in counts.index]
    values = counts.values
    percentages = values / total * 100
 
    # reverse so largest bar is at top
    labels = labels[::-1]
    values = values[::-1]
    percentages = percentages[::-1]
 
    # top 5 get accent color, rest muted
    accent = "#2563EB"
    muted = "#CBD5E1"
    n = len(values)
    colors = [muted if i < (n - 5) else accent for i in range(n)]
 
    fig, ax = plt.subplots(figsize=(12, 8))
 
    bars = ax.barh(range(n), values, color=colors, height=0.7, edgecolor="none")
 
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=11)
 
    # count + percentage labels
    for bar, val, pct in zip(bars, values, percentages):
        ax.text(
            bar.get_width() + 30,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,}  ({pct:.1f}%)",
            va="center",
            fontsize=10,
            color="#334155",
        )
 
    fig.text(
        0.02, 0.96,
        f"Based on {total:,} active providers  •  Top 5 highlighted",
        fontsize=11,
        color="#64748B",
    )
 
    fig.text(
        0.02, 0.99,
        "Top 15 Provider Specialties by Taxonomy Code",
        fontsize=16,
        fontweight="bold",
        va="top",
    )
 
    # clean up axes
    ax.set_xlabel("")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.spines["left"].set_color("#E2E8F0")
    ax.tick_params(axis="x", colors="#94A3B8")
    ax.set_xlim(0, values[-1] * 1.25)
 
    plt.subplots_adjust(top=0.92)
    save_plot("taxonomy_distribution.png")
 
 
def provider_growth_trend(df: pd.DataFrame):
    """Bar chart of annual provider enumerations with data quality handling."""
    print("[EDA] Building provider growth trend chart...")
 
    trend = (
        df.assign(year=df["provider_enumeration_date"].dt.year)
        .groupby("year")
        .size()
    )
 
    # separate complete years from partial / artifact data
    complete_years = trend[trend.index <= 2024]
    partial_2025 = trend[trend.index == 2025]
 
    years = complete_years.index.tolist()
    values = complete_years.values.tolist()
 
    fig, ax = plt.subplots(figsize=(13, 6.5))
 
    accent = "#2563EB"
    muted = "#CBD5E1"
 
    bar_colors = [accent if v >= 1000 else muted for v in values]
    bars = ax.bar(years, values, color=bar_colors, width=0.75, edgecolor="none")
 
    # 2025 partial year as hatched bar
    if not partial_2025.empty:
        ax.bar(
            2025, partial_2025.values[0],
            color="none", edgecolor=accent, linewidth=1.5,
            width=0.75, hatch="///", label="2025 (partial year)",
        )
 
    # value labels on bars with 700+ providers
    for bar, val in zip(bars, values):
        if val >= 700:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 20,
                f"{val:,}",
                ha="center", va="bottom",
                fontsize=9, color="#334155",
            )
 
    if not partial_2025.empty:
        ax.text(
            2025, partial_2025.values[0] + 20,
            f"{partial_2025.values[0]:,}",
            ha="center", va="bottom",
            fontsize=9, color=accent,
        )
 
    # annotate key inflection points
    ax.annotate(
        "NPI system\nlaunched",
        xy=(2006, 1668), xytext=(2008.5, 1750),
        fontsize=9, color="#64748B",
        arrowprops=dict(arrowstyle="->", color="#94A3B8", lw=1.2),
        ha="center",
    )
 
    ax.annotate(
        "steady acceleration\nsince 2015",
        xy=(2019, 818), xytext=(2016, 1350),
        fontsize=9, color="#64748B",
        arrowprops=dict(arrowstyle="->", color="#94A3B8", lw=1.2),
        ha="center",
    )
 
    ax.set_title(
        "Annual Provider Enumeration Trend (2005–2024)",
        fontsize=16, fontweight="bold", loc="left", pad=25,
    )
 
    ax.text(
        0, 1.02,
        "New NPI registrations per year  •  2025 shown as partial  •  2026 excluded (batch artifact)",
        transform=ax.transAxes,
        fontsize=10.5, color="#64748B",
    )
 
    ax.set_ylabel("New Providers", fontsize=11, color="#64748B")
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.spines["left"].set_color("#E2E8F0")
    ax.tick_params(axis="both", colors="#94A3B8")
 
    ax.set_xticks(range(2005, 2026))
    ax.set_xticklabels(range(2005, 2026), rotation=45, ha="right", fontsize=9)
 
    ax.legend(loc="upper left", fontsize=10, frameon=False)
 
    plt.tight_layout()
    save_plot("provider_growth_trend.png")

# Pipeline runner

def run_eda():
    """
    Execute EDA workflow.
    Generates summary visuals that help guide modeling decisions.
    """
    df = load_clean_data()
 
    provider_counts_by_state(df)
    taxonomy_distribution(df)
    provider_growth_trend(df)
 
    print("[EDA] EDA workflow complete.")


if __name__ == "__main__":
    run_eda()
