import pandas as pd
from pathlib import Path


# folder where raw NPPES weekly files live

DATA_DIR = Path("data/extracted/nppes_weekly_raw")

# standardized raw output that downstream pipeline stages will use

OUTPUT_FILE = Path("data/extracted/nppes_provider_raw.csv")

# core columns needed for reproductive health access modeling
# the full NPPES file has about 330 columns,  we keep only identity,
# taxonomy, geography, and enrollment fields


KEEP_COLUMNS = [
    "NPI",
    "Entity Type Code",
    "Provider Organization Name (Legal Business Name)",
    "Provider Last Name (Legal Name)",
    "Provider First Name",
    "Provider Credential Text",
    "Provider Business Practice Location Address City Name",
    "Provider Business Practice Location Address State Name",
    "Provider Business Practice Location Address Postal Code",
    "Provider Business Practice Location Address Telephone Number",
    "Healthcare Provider Taxonomy Code_1",
    "Healthcare Provider Primary Taxonomy Switch_1",
    "Healthcare Provider Taxonomy Group_1",
    "Provider Enumeration Date",
    "Last Update Date",
    "NPI Deactivation Date",
    "NPI Reactivation Date",
]


def find_provider_file() -> Path:
    """Locate the NPPES provider data CSV, ignoring header definition files."""
    files = list(DATA_DIR.glob("npidata*.csv"))

    # remove header definition files
    files = [f for f in files if "fileheader" not in f.name.lower()]

    if not files:
        raise FileNotFoundError(
            "No valid provider data file found. Check data/extracted/nppes_weekly_raw/."
        )

    return files[0]


def extract_nppes() -> pd.DataFrame:
    """
    Extract raw NPPES provider data for downstream reproductive health filtering.
    Loads the full national file, selects analytical columns, and saves
    a standardized extract. Specialty filtering happens in the transform stage.
    """
    
    provider_file = find_provider_file()

    print(f"[EXTRACT] Loading provider file: {provider_file}")

    # load as string to avoid dtype issues (very common with CMS datasets)
    df = pd.read_csv(provider_file, dtype=str, low_memory=False)

    print(f"[EXTRACT] Full NPPES shape: {df.shape}")

    # keep only columns that exist (protects against schema changes)
    cols_existing = [c for c in KEEP_COLUMNS if c in df.columns]
    
    df = df[cols_existing].copy()
 
    print(f"[EXTRACT] After column selection: {df.shape}")
 
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(OUTPUT_FILE, index=False)
 
    print(f"[EXTRACT] Saved → {OUTPUT_FILE}")
 
    return df



if __name__ == "__main__":
    extract_nppes()