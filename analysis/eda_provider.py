import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_DIR = Path("data/visualizations")


# ---------- Utility ----------

def save_plot(filename: str):
    """Standard helper to save plots cleanly."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename)
    plt.close()
    print(f"[EDA] Saved → {filename}")


# ---------- Load ----------

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


# ---------- Visualizations ----------

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
    """Bar chart of top provider taxonomy groups."""
    print("[EDA] Building taxonomy distribution chart...")

    counts = df["taxonomy_group_1"].value_counts().head(15)

    plt.figure(figsize=(12, 6))
    counts.plot(kind="bar")

    plt.title("Top Provider Taxonomy Groups")
    plt.ylabel("Count")

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


# ---------- Pipeline Runner ----------

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