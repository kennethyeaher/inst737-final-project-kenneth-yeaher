import pandas as pd
from pathlib import Path


# folder where raw NPPES weekly files live
DATA_DIR = Path("data/extracted/nppes_weekly_raw")

# standardized raw output that downstream pipeline stages will use
OUTPUT_FILE = Path("data/extracted/nppes_provider_raw.csv")


# only keeping core columns needed for access / geography / provider type analysis
# we intentionally avoid loading all ~330 columns to reduce memory + complexity
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
    "NPI Reactivation Date"
]


def find_provider_file() -> Path:
    """
    Dynamically locate the main provider CSV file inside the weekly NPPES folder.

    We avoid hardcoding filenames because CMS releases files with new dates each week/month.
    This makes the pipeline more reusable and production-friendly.
    """
    files = list(DATA_DIR.glob("npidata*.csv"))

    if not files:
        raise FileNotFoundError(
            "No provider file found in NPPES raw directory. "
            "Check that weekly data was downloaded correctly."
        )

    return files[0]


def extract_nppes() -> pd.DataFrame:
    """
    Extraction stage of pipeline.

    Steps:
    1. Locate provider data file
    2. Load full dataset
    3. Select only relevant analytical columns
    4. Save standardized raw extract for transform stage
    """

    provider_file = find_provider_file()

    print(f"[EXTRACT] Loading provider file: {provider_file}")

    # load as string to avoid dtype issues (very common with CMS datasets)
    df = pd.read_csv(provider_file, dtype=str, low_memory=False)

    print(f"[EXTRACT] Original dataset shape: {df.shape}")

    # keep only columns that exist (protects pipeline if schema changes)
    cols_existing = [c for c in KEEP_COLUMNS if c in df.columns]

    df = df[cols_existing].copy()

    print(f"[EXTRACT] Filtered dataset shape: {df.shape}")

    # ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # save standardized raw dataset
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"[EXTRACT] Saved standardized raw file → {OUTPUT_FILE}")

    return df


# allows script to run standalone OR be imported into main pipeline runner
if __name__ == "__main__":
    extract_nppes()