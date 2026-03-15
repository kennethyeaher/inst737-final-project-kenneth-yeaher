import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path


INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_DIR = Path("data/visualizations")

# taxonomy code to readable specialty name

TAXONOMY_LABELS = {
    "106S00000X": "Speech-Language Pathologist",
    "363LF0000X": "Nurse Practitioner — Family",
    "101YM0800X": "Counselor — Mental Health",
    "1041C0700X": "Social Worker — Clinical",
    "390200000X": "Student in Health Care Training",
    "363A00000X": "Physician Assistant",
    "163W00000X": "Registered Nurse",
    "225100000X": "Physical Therapist",
    "207R00000X": "Internal Medicine",
    "235Z00000X": "Speech-Language Pathologist (Alt)",
    "101YP2500X": "Counselor — Professional",
    "363LP0808X": "Nurse Practitioner — Psych/MH",
    "207Q00000X": "Family Medicine",
    "363L00000X": "Nurse Practitioner — General",
    "103K00000X": "Behavioral Analyst",
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
    """Bar chart of top states by active provider count."""
    print("[EDA] Building provider counts by state chart...")
 
    counts = (
        df["practice_state"]
        .value_counts()
        .head(20)
    )
 
    plt.figure(figsize=(12, 6))
    counts.plot(kind="bar")
 
    plt.title("Top States by Active Provider Count")
    plt.ylabel("Providers")
 
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
    """Line chart showing provider enumeration trend over time."""
    print("[EDA] Building provider growth trend chart...")
 
    trend = (
        df.assign(year=df["provider_enumeration_date"].dt.year)
        .groupby("year")
        .size()
        .sort_index()
    )
 
    plt.figure(figsize=(12, 6))
    trend.plot()
 
    plt.title("Provider Enumeration Trend")
    plt.ylabel("New Providers")
 
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
