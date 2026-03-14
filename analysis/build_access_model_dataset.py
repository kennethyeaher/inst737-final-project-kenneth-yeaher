import pandas as pd
from pathlib import Path

PROVIDER_FILE = Path("data/load/provider_geo_features.csv")
CBSA_REF_FILE = Path("data/load/cbsa_reference_dataset.csv")
OUTPUT_FILE = Path("data/load/access_model_dataset.csv")

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load provider feature data and CBSA reference data."""
    print("\n[ACCESS-MODEL] ===== BUILDING ACCESS MODEL DATASET =====")

    providers = pd.read_csv(PROVIDER_FILE)
    cbsa_ref = pd.read_csv(CBSA_REF_FILE)

    print(f"[ACCESS-MODEL] Provider rows: {providers.shape[0]}")
    print(f"[ACCESS-MODEL] CBSA reference rows: {cbsa_ref.shape[0]}")

    return providers, cbsa_ref

def build_supply_features(providers: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate provider supply to a state level proxy.
    This is a temporary approximation until the full ZIP to CBSA merge is finished.
    """

    supply = (
        providers.groupby("practice_state", as_index=False)
        .agg(
            provider_count=("provider_count", "sum"),
            taxonomy_diversity=("unique_taxonomies", "mean"),
            avg_provider_enum_year=("avg_provider_enum_year", "mean"),
            recent_provider_growth=("recent_provider_growth", "sum")
        )
    ) 

    print(f"[ACCESS-MODEL] Aggregated supply rows: {supply.shape[0]}")
    return supply

def build_population_proxy(cbsa_ref: pd.DataFrame) -> pd.DataFrame:
    """
    Create a temporary state level population proxy from the CBSA reference dataset.
    """
    pop = (
        cbsa_ref.groupby("State Name", as_index=False)
        .agg(
            metro_population=("population_2024", "sum")
        )
        .rename(columns={"State Name": "state_name"})
    )

    return pop

def merge_access_features(
    supply: pd.DataFrame,
    pop: pd.DataFrame,
) -> pd.DataFrame:
    """Merge supply features with population proxy and compute density."""
    df = supply.merge(
        pop,
        left_on="practice_state",
        right_on="state_name",
        how="left",
    )

    df["providers_per_100k"] = (
        df["provider_count"] / df["metro_population"]
    ) * 100000

    return df

def save_output(df: pd.DataFrame) -> None:
    """Save the modeling dataset."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"[ACCESS-MODEL] Saved → {OUTPUT_FILE}")
    print("[ACCESS-MODEL] ===== DATASET READY =====")

def build_access_model_dataset() -> pd.DataFrame:
    """Run the full access-model dataset workflow."""
    providers, cbsa_ref = load_inputs()
    supply = build_supply_features(providers)
    pop = build_population_proxy(cbsa_ref)
    df = merge_access_features(supply, pop)
    save_output(df)
    return df

if __name__ == "__main__":
    build_access_model_dataset()








