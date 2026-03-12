import pandas as pd
from pathlib import Path


# ===== File Paths =====
RAW_FILE = Path("data/extracted/nppes_provider_raw.csv")
CLEAN_FILE = Path("data/transformed/nppes_provider_clean.csv")


def load_raw_data() -> pd.DataFrame:
    """Load the standardized raw provider dataset from the extract stage."""
    print("[TRANSFORM] Loading standardized provider dataset...")
    df = pd.read_csv(RAW_FILE, dtype=str)
    print(f"[TRANSFORM] Raw shape: {df.shape}")
    return df


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename columns into a cleaner snake_case style.
    This makes later modeling and visualization code way easier to read.
    """
    df = df.rename(columns={
        "NPI": "npi",
        "Entity Type Code": "entity_type_code",
        "Provider Organization Name (Legal Business Name)": "provider_org_name",
        "Provider Last Name (Legal Name)": "provider_last_name",
        "Provider First Name": "provider_first_name",
        "Provider Credential Text": "provider_credential",
        "Provider Business Practice Location Address City Name": "practice_city",
        "Provider Business Practice Location Address State Name": "practice_state",
        "Provider Business Practice Location Address Postal Code": "practice_zip",
        "Provider Business Practice Location Address Telephone Number": "practice_phone",
        "Healthcare Provider Taxonomy Code_1": "taxonomy_code_1",
        "Healthcare Provider Primary Taxonomy Switch_1": "primary_taxonomy_switch_1",
        "Healthcare Provider Taxonomy Group_1": "taxonomy_group_1",
        "Provider Enumeration Date": "provider_enumeration_date",
        "Last Update Date": "last_update_date",
        "NPI Deactivation Date": "npi_deactivation_date",
        "NPI Reactivation Date": "npi_reactivation_date"
    })

    print("[TRANSFORM] Standardized column names.")
    return df


def filter_active_providers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only active NPIs.
    No reason to model provider supply that is already deactivated.
    """
    df = df[df["npi_deactivation_date"].isna()].copy()
    print(f"[TRANSFORM] After active filter: {df.shape}")
    return df


def drop_duplicate_npis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make sure each NPI only appears once.
    This is a basic integrity check before any analysis.
    """
    before = df.shape[0]
    df = df.drop_duplicates(subset="npi").copy()
    after = df.shape[0]
    print(f"[TRANSFORM] Dropped {before - after} duplicate NPI rows.")
    return df


def clean_geographic_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean basic location fields.
    For now, keep only records with state and ZIP since those will be needed
    for geography joins later.
    """
    df["practice_state"] = df["practice_state"].str.strip().str.upper()
    df["practice_city"] = df["practice_city"].str.strip()

    # keep first 5 digits only
    df["zip5"] = df["practice_zip"].str.extract(r"(\d{5})")

    df = df.dropna(subset=["practice_state", "zip5"]).copy()

    print(f"[TRANSFORM] After geography cleaning: {df.shape}")
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert date fields so later time-based analysis is easier.
    """
    date_cols = [
        "provider_enumeration_date",
        "last_update_date",
        "npi_deactivation_date",
        "npi_reactivation_date"
    ]

    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    print("[TRANSFORM] Parsed date columns.")
    return df


def save_clean_data(df: pd.DataFrame) -> None:
    """Save the cleaned provider dataset for analysis and modeling."""
    CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_FILE, index=False)
    print(f"[TRANSFORM] Saved clean dataset → {CLEAN_FILE}")


def transform_nppes() -> pd.DataFrame:
    """
    Full transform workflow:
    load → rename → filter → deduplicate → clean geography → parse dates → save
    """
    df = load_raw_data()
    df = standardize_column_names(df)
    df = filter_active_providers(df)
    df = drop_duplicate_npis(df)
    df = clean_geographic_fields(df)
    df = parse_dates(df)

    print(f"[TRANSFORM] Final shape: {df.shape}")

    save_clean_data(df)

    return df


if __name__ == "__main__":
    transform_nppes()