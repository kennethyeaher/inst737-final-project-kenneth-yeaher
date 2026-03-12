import pandas as pd
from pathlib import Path


# ===== File Paths =====
RAW_FILE = Path("data/extracted/nppes_provider_raw.csv")
CLEAN_FILE = Path("data/transformed/nppes_provider_clean.csv")


def load_raw_data() -> pd.DataFrame:
    """Load standardized raw provider dataset."""
    print("[TRANSFORM] Loading standardized provider dataset...")
    df = pd.read_csv(RAW_FILE, dtype=str)
    print(f"[TRANSFORM] Raw shape: {df.shape}")
    return df


def filter_active_providers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only active NPIs.
    This avoids modeling supply that no longer exists.
    """
    df = df[df["NPI Deactivation Date"].isna()].copy()
    print(f"[TRANSFORM] After active filter: {df.shape}")
    return df


def standardize_zip(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create ZIP5 feature.
    Needed for geographic joins (ZCTA / metro / population later).
    """
    df["zip5"] = df[
        "Provider Business Practice Location Address Postal Code"
    ].str[:5]

    return df


def save_clean_data(df: pd.DataFrame):
    """Persist modeling-ready dataset."""
    CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_FILE, index=False)
    print(f"[TRANSFORM] Saved clean dataset → {CLEAN_FILE}")


def transform_nppes() -> pd.DataFrame:
    """
    Full transform workflow:
    load → clean → feature engineer → save
    """

    df = load_raw_data()

    df = filter_active_providers(df)

    df = standardize_zip(df)

    print(f"[TRANSFORM] Final shape: {df.shape}")

    save_clean_data(df)

    return df


if __name__ == "__main__":
    transform_nppes()