import pandas as pd
from pathlib import Path

# file path 

INPUT_FILE = Path("data/transformed/nppes_provider_clean.csv")
OUTPUT_FILE = Path("data/load/provider_geo_features.csv")


def load_provider_data() -> pd.DataFrame:
    """Load cleaned reproductive health provider dataset."""
    print("[MODEL-DATA] Loading reproductive health provider data...")
 
    df = pd.read_csv(INPUT_FILE, parse_dates=["provider_enumeration_date"])
 
    print(f"[MODEL-DATA] Providers loaded: {df.shape[0]}")
    return df


def compute_supply_counts(df: pd.DataFrame) -> pd.Series:
    """Count reproductive health providers per state-ZIP pair."""
    return (
        df.groupby(["practice_state", "zip5"])
        .size()
        .rename("provider_count")
    )


def compute_taxonomy_diversity(df: pd.DataFrame) -> pd.Series:
    """Count unique reproductive health specialties per state-ZIP pair."""
    return (
        df.groupby(["practice_state", "zip5"])["taxonomy_code_1"]
        .nunique()
        .rename("unique_taxonomies")
    )


def compute_maturity_proxy(df: pd.DataFrame) -> pd.Series:
    """Average enumeration year as a workforce maturity indicator."""
    return (
        df.assign(enum_year=df["provider_enumeration_date"].dt.year)
        .groupby(["practice_state", "zip5"])["enum_year"]
        .mean()
        .rename("avg_provider_enum_year")
    )


def compute_recent_growth(df: pd.DataFrame) -> pd.Series:
    """Count providers enumerated in the last 3 years as a growth signal."""
    recent_cutoff = df["provider_enumeration_date"].max() - pd.DateOffset(years=3)
 
    return (
        df[df["provider_enumeration_date"] >= recent_cutoff]
        .groupby(["practice_state", "zip5"])
        .size()
        .rename("recent_provider_growth")
    )

def build_provider_geo_features() -> pd.DataFrame:
    """
    Build ZIP level reproductive health provider feature dataset.
    Aggregates supply counts, specialty diversity, workforce maturity,
    and recent growth from the cleaned provider data.
    """
    df = load_provider_data()
 
    geo_features = pd.concat(
        [
            compute_supply_counts(df),
            compute_taxonomy_diversity(df),
            compute_maturity_proxy(df),
            compute_recent_growth(df),
        ],
        axis=1,
    ).fillna(0).reset_index()
 
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    geo_features.to_csv(OUTPUT_FILE, index=False)
 
    print(f"[MODEL-DATA] Saved → {OUTPUT_FILE}")
    print(f"[MODEL-DATA] ZIP-level rows: {geo_features.shape[0]}")
 
    return geo_features


if __name__ == "__main__":
    build_provider_geo_features()