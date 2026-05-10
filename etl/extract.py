import pandas as pd
from pathlib import Path
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.extract")

# folder where raw NPPES weekly files live

DATA_DIR = Path("data/extracted/nppes_weekly_raw")

# standardized raw output that downstream pipeline stages will use

OUTPUT_FILE = Path("data/extracted/nppes_provider_raw.csv")

# only keeping core columns needed for access / geography / provider type analysis
# we intentionally avoid loading all 330 columns to reduce memory and complexity

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
    """locate the actual provider data csv (not the header file)."""
    files = list(DATA_DIR.glob("npidata*.csv"))

    # remove header definition files
    files = [f for f in files if "fileheader" not in f.name.lower()]

    if not files:
        raise FileNotFoundError(
            "no valid provider data file found. check raw NPPES folder."
        )

    return files[0]


def extract_nppes() -> pd.DataFrame:
    """
    Extraction stage of pipeline.
    Locates provider data file, selects relevant columns,
    and saves a standardized raw extract for the transform stage.
    """
    try:
        provider_file = find_provider_file()
        logger.info(f"loading provider file: {provider_file}")

        # load as string to avoid dtype issues (very common with CMS datasets)
        df = pd.read_csv(provider_file, dtype=str, low_memory=False)
        logger.info(f"original dataset shape: {df.shape}")

        # keep only columns that exist (protects pipeline if schema changes)
        cols_existing = [c for c in KEEP_COLUMNS if c in df.columns]
        cols_missing = [c for c in KEEP_COLUMNS if c not in df.columns]

        if cols_missing:
            logger.warning(f"columns not found in source: {cols_missing}")

        df = df[cols_existing].copy()
        logger.info(f"filtered dataset shape: {df.shape}")

        # save standardized raw dataset for the transform stage
        save_csv(df, OUTPUT_FILE, logger)

        return df

    except FileNotFoundError as e:
        logger.error(f"extraction failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during extraction: {e}")
        raise


if __name__ == "__main__":
    extract_nppes()