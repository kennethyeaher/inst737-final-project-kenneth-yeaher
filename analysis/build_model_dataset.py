import pandas as pd
from pathlib import Path


INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_FILE = Path("data/load/provider_geo_features.csv")


def build_provider_geo_features() -> pd.DataFrame:
    """
    Aggregate provider supply features at ZIP level.
    This becomes the base modeling dataset for density / clustering analysis.
    """

    print("[MODEL-DATA] Building geographic provider features...")

    df = pd.read_csv(INPUT_FILE)

    # provider counts per ZIP + state
    provider_counts = (
        df.groupby(["practice_state", "zip5"])
        .size()
        .rename("provider_count")
    )

    # specialty diversity per ZIP + state
    taxonomy_diversity = (
        df.groupby(["practice_state", "zip5"])["taxonomy_group_1"]
        .nunique()
        .rename("unique_taxonomies")
    )

    geo_features = pd.concat(
        [provider_counts, taxonomy_diversity],
        axis=1
    ).reset_index()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    geo_features.to_csv(OUTPUT_FILE, index=False)

    print(f"[MODEL-DATA] Saved geographic feature dataset → {OUTPUT_FILE}")
    print(f"[MODEL-DATA] Rows: {geo_features.shape[0]}")

    return geo_features


if __name__ == "__main__":
    build_provider_geo_features()