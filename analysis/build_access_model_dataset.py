import pandas as pd
from pathlib import Path

PROVIDER_FILE = Path("data/load/provider_geo_features.csv")
CBSA_REF_FILE = Path("data/load/cbsa_reference_dataset.csv")
OUTPUT_FILE = Path("data/load/access_model_dataset.csv")

STATE_ABBR_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
}

SUPPLY_REQUIRED_COLUMNS = {
    "practice_state",
    "provider_count",
    "unique_taxonomies",
    "avg_provider_enum_year",
    "recent_provider_growth",
}

POP_REQUIRED_COLUMNS = {
    "State Name",
    "population_2024",
}

#helper code
def normalize_state_name(series: pd.Series) -> pd.Series:
    """Normalize state names for safer joins."""
    return series.astype(str).str.strip().str.lower()

def validate_columns(df: pd.DataFrame, required: set[str], df_name: str) -> None:
    """Fail fast if expected columns are missing."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {sorted(missing)}")
    
#pipline stages

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load provider geographic features and Census CBSA reference data.
    """
    print("\n[ACCESS-MODEL] ===== BUILDING ACCESS MODEL DATASET =====")

    providers = pd.read_csv(PROVIDER_FILE)
    cbsa_ref = pd.read_csv(CBSA_REF_FILE)

    validate_columns(providers, SUPPLY_REQUIRED_COLUMNS, "provider_geo_features")
    validate_columns(cbsa_ref, POP_REQUIRED_COLUMNS, "cbsa_reference_dataset")

    print(f"[ACCESS-MODEL] Provider rows: {providers.shape[0]}")
    print(f"[ACCESS-MODEL] CBSA reference rows: {cbsa_ref.shape[0]}")

    return providers, cbsa_ref


def build_supply_features(providers: pd.DataFrame) -> pd.DataFrame:
    """
    Build state level supply features as a temporary access modeling proxy
    until the full ZIP to CBSA merge is implemented.
    """
    providers = providers[providers["practice_state"].isin(STATE_ABBR_TO_NAME)].copy()

    supply = (
        providers.groupby("practice_state", as_index=False)
        .agg(
            provider_count=("provider_count", "sum"),
            taxonomy_diversity=("unique_taxonomies", "mean"),
            avg_provider_enum_year=("avg_provider_enum_year", "mean"),
            recent_provider_growth=("recent_provider_growth", "sum"),
        )
    )

    # map state abbreviation to full state name for merge compatibility
    supply["state_name"] = normalize_state_name(
        supply["practice_state"].map(STATE_ABBR_TO_NAME)
    )

    print(f"[ACCESS-MODEL] Aggregated supply rows: {supply.shape[0]}")
    return supply

def build_population_proxy(cbsa_ref: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate metro population totals to the state level.
    This acts as a temporary denominator for provider density estimation.
    """
    pop = cbsa_ref.copy()
    pop["population_2024"] = pd.to_numeric(pop["population_2024"], errors="coerce")
    pop["state_name"] = normalize_state_name(pop["State Name"])

    pop = (
        pop.groupby("state_name", as_index=False)
        .agg(metro_population=("population_2024", "sum"))
    )

    return pop

def merge_access_features(supply: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """
    Merge supply features with population proxy and compute provider density.
    """
    df = supply.merge(pop, on="state_name", how="left", validate="one_to_one")

    df["metro_population"] = pd.to_numeric(df["metro_population"], errors="coerce")
    df.loc[df["metro_population"] <= 0, "metro_population"] = pd.NA

    df["providers_per_100k"] = (
        df["provider_count"] / df["metro_population"] * 100000
    )

    missing_population = df["metro_population"].isna().sum()

    print(f"[ACCESS-MODEL] Rows after merge: {df.shape[0]}")
    print(f"[ACCESS-MODEL] Rows missing population: {missing_population}")

    # reorder columns to make final file easier to inspect
    ordered_cols = [
        "practice_state",
        "state_name",
        "provider_count",
        "taxonomy_diversity",
        "avg_provider_enum_year",
        "recent_provider_growth",
        "metro_population",
        "providers_per_100k",
    ]
    df = df[ordered_cols]

    return df

def save_output(df: pd.DataFrame) -> None:
    """
    Save the access modeling dataset for downstream regression and scoring.
    """
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"[ACCESS-MODEL] Saved → {OUTPUT_FILE}")
    print("[ACCESS-MODEL] ===== DATASET READY =====")

def build_access_model_dataset() -> pd.DataFrame:
    """
    Full workflow:
    load to validate to aggregate supply to aggregate population to merge then save
    """
    providers, cbsa_ref = load_inputs()
    supply = build_supply_features(providers)
    pop = build_population_proxy(cbsa_ref)
    access_model_df = merge_access_features(supply, pop)
    save_output(access_model_df)

    return access_model_df

if __name__ == "__main__":
    build_access_model_dataset()
