import pandas as pd
from pathlib import Path


INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_FILE = Path("data/load/provider_geo_features.csv")


def build_provider_geo_features() -> pd.DataFrame:
    """
    Build geographic provider feature dataset.

    Adds:
    - provider_count
    - taxonomy diversity
    - avg enumeration year (provider maturity proxy)
    - recent provider growth proxy
    """

    print("[MODEL-DATA] Building enhanced geographic provider features...")

    df = pd.read_csv(INPUT_FILE, parse_dates=["provider_enumeration_date"])

    # ----- basic supply counts -----
    provider_counts = (
        df.groupby(["practice_state", "zip5"])
        .size()
        .rename("provider_count")
    )

    # ----- specialty diversity -----
    taxonomy_diversity = (
        df.groupby(["practice_state", "zip5"])["taxonomy_group_1"]
        .nunique()
        .rename("unique_taxonomies")
    )

    # ----- maturity proxy -----
    avg_enum_year = (
        df.assign(enum_year=df["provider_enumeration_date"].dt.year)
        .groupby(["practice_state", "zip5"])["enum_year"]
        .mean()
        .rename("avg_provider_enum_year")
    )

    # ----- growth proxy (recent providers) -----
    recent_cutoff = df["provider_enumeration_date"].max() - pd.DateOffset(years=3)

    recent_growth = (
        df[df["provider_enumeration_date"] >= recent_cutoff]
        .groupby(["practice_state", "zip5"])
        .size()
        .rename("recent_provider_growth")
    )

    geo_features = pd.concat(
        [
            provider_counts,
            taxonomy_diversity,
            avg_enum_year,
            recent_growth
        ],
        axis=1
    ).fillna(0).reset_index()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    geo_features.to_csv(OUTPUT_FILE, index=False)

    print(f"[MODEL-DATA] Saved enhanced dataset → {OUTPUT_FILE}")
    print(f"[MODEL-DATA] Rows: {geo_features.shape[0]}")

    return geo_features


if __name__ == "__main__":
    build_provider_geo_features()