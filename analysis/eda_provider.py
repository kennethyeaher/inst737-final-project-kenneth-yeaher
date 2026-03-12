import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_DIR = Path("data/visualizations")


def load_clean_data():
    """Load cleaned provider dataset from transform stage."""
    print("[EDA] Loading cleaned provider dataset...")
    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["provider_enumeration_date", "last_update_date"]
    )
    print(f"[EDA] Dataset shape: {df.shape}")
    return df


def provider_counts_by_state(df):
    """Create bar chart of top states by provider count."""
    print("[EDA] Creating provider counts by state...")

    counts = (
        df.groupby("practice_state")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    plt.figure(figsize=(12, 6))
    counts.plot(kind="bar")
    plt.title("Top States by Active Provider Count")
    plt.ylabel("Number of Providers")
    plt.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_DIR / "provider_counts_by_state.png")
    plt.close()


def taxonomy_distribution(df):
    """Visualize top provider taxonomy groups."""
    print("[EDA] Creating taxonomy distribution...")

    counts = df["taxonomy_group_1"].value_counts().head(15)

    plt.figure(figsize=(12, 6))
    counts.plot(kind="bar")
    plt.title("Top Provider Taxonomy Groups")
    plt.ylabel("Count")
    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "taxonomy_distribution.png")
    plt.close()


def provider_growth_trend(df):
    """Line chart showing provider enumeration trend."""
    print("[EDA] Creating provider growth trend...")

    df["year"] = df["provider_enumeration_date"].dt.year

    trend = df.groupby("year").size().sort_index()

    plt.figure(figsize=(12, 6))
    trend.plot()
    plt.title("Provider Enumeration Trend Over Time")
    plt.ylabel("New Providers")
    plt.tight_layout()

    plt.savefig(OUTPUT_DIR / "provider_growth_trend.png")
    plt.close()


def run_eda():
    """Run full exploratory data analysis workflow."""
    df = load_clean_data()

    provider_counts_by_state(df)
    taxonomy_distribution(df)
    provider_growth_trend(df)

    print("[EDA] All visualizations generated.")


if __name__ == "__main__":
    run_eda()