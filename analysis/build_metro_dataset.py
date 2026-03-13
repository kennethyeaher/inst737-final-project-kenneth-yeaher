import pandas as pd
from pathlib import Path


# ---------------------------
# File paths
# ---------------------------

PROVIDER_FILE = Path("data/load/provider_geo_features.csv")
ZIP_COUNTY_FILE = Path("data/external/list1_2023.xlsx")
CBSA_COUNTY_FILE = Path("data/external/list2_2023.xlsx")
CBSA_POP_FILE = Path("data/external/cbsa-met-est2024-pop.xlsx")

OUTPUT_FILE = Path("data/load/provider_metro_features.csv")


def build_metro_dataset():
    """
    Construct metro-level provider access dataset.

    Pipeline logic:
    1. Load provider geographic features (ZIP level)
    2. Map ZIP → County
    3. Map County → CBSA (metro area)
    4. Attach metro population estimates
    5. Compute provider density features

    Final dataset supports underserved metro analysis + modeling.
    """

    print("\n[METRO] ===== BUILDING METRO MODEL DATASET =====")

    # ---------------------------
    # Load datasets
    # ---------------------------

    providers = pd.read_csv(PROVIDER_FILE)
    zip_county = pd.read_excel(ZIP_COUNTY_FILE)
    county_cbsa = pd.read_excel(CBSA_COUNTY_FILE)
    cbsa_pop = pd.read_excel(CBSA_POP_FILE)

    print(f"[METRO] Provider rows: {providers.shape[0]}")

    # ---------------------------
    # Standardize ZIP formatting
    # ---------------------------

    providers["zip5"] = providers["zip5"].astype(str).str.zfill(5)
    zip_county["ZIP"] = zip_county["ZIP"].astype(str).str.zfill(5)

    # ---------------------------
    # Merge ZIP → County
    # ---------------------------

    df = providers.merge(
        zip_county,
        left_on="zip5",
        right_on="ZIP",
        how="left",
        validate="many_to_one"
    )

    print(f"[METRO] After ZIP merge: {df.shape[0]} rows")

    # ---------------------------
    # Merge County → CBSA
    # ---------------------------

    df = df.merge(
        county_cbsa,
        on="COUNTY",
        how="left",
        validate="many_to_one"
    )

    print(f"[METRO] After CBSA merge: {df.shape[0]} rows")

    # ---------------------------
    # Aggregate at metro level
    # ---------------------------

    metro = (
        df.groupby("CBSA Code", as_index=False)
        .agg(
            provider_count=("provider_count", "sum"),
            taxonomy_diversity=("unique_taxonomies", "mean")
        )
    )

    print(f"[METRO] Metro groups formed: {metro.shape[0]}")

    # ---------------------------
    # Merge population estimates
    # ---------------------------

    metro = metro.merge(
        cbsa_pop,
        left_on="CBSA Code",
        right_on="CBSA",
        how="left",
        validate="one_to_one"
    )

    # ---------------------------
    # Create density feature
    # ---------------------------

    metro["providers_per_100k"] = (
        metro["provider_count"] / metro["Population"] * 100000
    )

    # ---------------------------
    # Save dataset
    # ---------------------------

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    metro.to_csv(OUTPUT_FILE, index=False)

    print(f"[METRO] Saved → {OUTPUT_FILE}")
    print("[METRO] ===== METRO DATASET READY =====\n")

    return metro


if __name__ == "__main__":
    build_metro_dataset()