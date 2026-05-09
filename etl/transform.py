import pandas as pd
from pathlib import Path
from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.transform")

# file paths

RAW_FILE = Path("data/extracted/nppes_provider_raw.csv")
CLEAN_FILE = Path("data/transformed/nppes_provider_clean.csv")

# reproductive and women's health taxonomy codes
# source: NUCC Health Care Provider Taxonomy Code Set

REPRODUCTIVE_HEALTH_TAXONOMY = {
    # obstetrics and gynecology
    "207V00000X": "Obstetrics & Gynecology",
    "207VC0200X": "Critical Care Medicine",
    "207VE0102X": "Reproductive Endocrinology",
    "207VF0040X": "Female Pelvic Medicine and Reconstructive Surgery",
    "207VG0400X": "Gynecology",
    "207VH0002X": "OB/GYN, Hospice and Palliative Medicine",
    "207VM0101X": "Maternal-Fetal Medicine",
    "207VX0000X": "Obstetrics",
    "207VX0201X": "Gynecologic Oncology",
    "207VR0500X": "Reproductive Endocrinology & Infertility",

    # midwifery
    "176B00000X": "Midwife",
    "367A00000X": "Certified Nurse Midwife",

    # nurse practitioner — women's health
    "363LW0102X": "Nurse Practitioner, Women's Health",
}


def load_raw_data() -> pd.DataFrame:
    """load the standardized raw provider dataset from the extract stage."""
    logger.info("loading standardized provider dataset...")
    df = pd.read_csv(RAW_FILE, dtype=str)
    logger.info(f"raw shape: {df.shape}")
    return df


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """rename columns into cleaner snake_case style."""
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
        "NPI Reactivation Date": "npi_reactivation_date",
    })

    logger.info("standardized column names")
    return df


def filter_active_providers(df: pd.DataFrame) -> pd.DataFrame:
    """keep only active npis."""
    before = df.shape[0]
    df = df[df["npi_deactivation_date"].isna()].copy()
    removed = before - df.shape[0]

    logger.info(f"after active filter: {df.shape} (removed {removed} inactive)")
    return df


def filter_reproductive_health_providers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only providers in reproductive and women's health specialties.
    Codes defined in REPRODUCTIVE_HEALTH_TAXONOMY constant.
    """
    valid_codes = set(REPRODUCTIVE_HEALTH_TAXONOMY.keys())
    before = df.shape[0]

    df = df[df["taxonomy_code_1"].isin(valid_codes)].copy()

    after = df.shape[0]
    matched_codes = df["taxonomy_code_1"].nunique()

    logger.info(f"reproductive health filter: {before:,} -> {after:,} providers")
    logger.info(f"matched {matched_codes} of {len(valid_codes)} taxonomy codes")

    if after == 0:
        raise ValueError(
            "no providers matched reproductive health taxonomy codes. "
            "check that taxonomy_code_1 column exists and contains valid NUCC codes."
        )

    return df


def drop_duplicate_npis(df: pd.DataFrame) -> pd.DataFrame:
    """ensure each npi only appears once."""
    before = df.shape[0]
    df = df.drop_duplicates(subset="npi").copy()
    dropped = before - df.shape[0]

    if dropped > 0:
        logger.warning(f"dropped {dropped} duplicate npi rows")
    else:
        logger.info("no duplicate npis found")

    return df


def clean_geographic_fields(df: pd.DataFrame) -> pd.DataFrame:
    """clean location fields and extract 5 digit zip."""
    df["practice_state"] = df["practice_state"].str.strip().str.upper()
    df["practice_city"] = df["practice_city"].str.strip()

    # keep first 5 digits only
    df["zip5"] = df["practice_zip"].str.extract(r"(\d{5})")

    missing_before = df.shape[0]
    df = df.dropna(subset=["practice_state", "zip5"]).copy()
    missing_dropped = missing_before - df.shape[0]

    if missing_dropped > 0:
        logger.warning(f"dropped {missing_dropped} rows missing state or zip")

    logger.info(f"after geography cleaning: {df.shape}")
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """convert date fields for downstream time based analysis."""
    date_cols = [
        "provider_enumeration_date",
        "last_update_date",
        "npi_deactivation_date",
        "npi_reactivation_date",
    ]

    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    logger.info("parsed date columns")
    return df


def save_clean_data(df: pd.DataFrame) -> None:
    """Save the cleaned provider dataset so analysis and modeling stages can read it."""
    save_csv(df, CLEAN_FILE, logger)


def transform_nppes() -> pd.DataFrame:
    """
    Full transform workflow.
    load, rename, filter active, filter specialty, deduplicate,
    clean geography, parse dates, save.
    """
    try:
        df = load_raw_data()
        df = standardize_column_names(df)
        df = filter_active_providers(df)
        df = filter_reproductive_health_providers(df)
        df = drop_duplicate_npis(df)
        df = clean_geographic_fields(df)
        df = parse_dates(df)

        logger.info(f"final shape: {df.shape}")
        save_clean_data(df)

        return df

    except FileNotFoundError:
        logger.error(f"raw file not found: {RAW_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except KeyError as e:
        logger.error(f"missing expected column during transform: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during transform: {e}")
        raise


if __name__ == "__main__":
    transform_nppes()