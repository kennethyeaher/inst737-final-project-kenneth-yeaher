import pandas as pd
from pathlib import Path
from utils.logging_config import setup_logger

logger = setup_logger("ovara.build_metro_dataset")

# file paths

CBSA_COUNTY_FILE = Path("data/external/list1_2023.xlsx")
CBSA_POP_FILE = Path("data/external/cbsa-met-est2024-pop.xlsx")
OUTPUT_FILE = Path("data/load/cbsa_reference_dataset.csv")

# expected columns

COUNTY_REQUIRED_COLUMNS = {
    "CBSA Code",
    "CBSA Title",
    "FIPS State Code",
    "FIPS County Code",
    "County/County Equivalent",
    "State Name",
    "Metropolitan/Micropolitan Statistical Area",
}

POP_REQUIRED_COLUMNS = {
    "Geographic Area",
    "Unnamed: 6",
}


# helpers

def validate_columns(df: pd.DataFrame, required: set[str], df_name: str) -> None:
    """fail fast if expected columns are missing."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {sorted(missing)}")


def clean_cbsa_title(series: pd.Series) -> pd.Series:
    """
    Standardize CBSA titles so Census population titles and delineation
    titles can be merged more reliably.
    """
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"^\.", "", regex=True)
        .str.replace(" Metro Area", "", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


# load stage

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load CBSA delineation and metro population source files.
    Both Excel workbooks use row 3 as the true header row.
    """
    logger.info("loading CBSA source files...")

    cbsa_county = pd.read_excel(CBSA_COUNTY_FILE, header=2)
    cbsa_pop = pd.read_excel(CBSA_POP_FILE, header=2)

    validate_columns(cbsa_county, COUNTY_REQUIRED_COLUMNS, "cbsa_county source")
    validate_columns(cbsa_pop, POP_REQUIRED_COLUMNS, "cbsa_population source")

    logger.info(f"CBSA-county rows: {cbsa_county.shape[0]:,}")
    logger.info(f"CBSA population rows: {cbsa_pop.shape[0]:,}")

    return cbsa_county, cbsa_pop


# transform stages

def prepare_cbsa_county(cbsa_county: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only metropolitan areas, build county FIPS linkage,
    and retain columns needed for downstream merges.
    """
    metro_county = cbsa_county[
        cbsa_county["Metropolitan/Micropolitan Statistical Area"]
        == "Metropolitan Statistical Area"
    ].copy()

    logger.info(f"metropolitan county rows: {metro_county.shape[0]:,}")

    metro_county["county_fips"] = (
        metro_county["FIPS State Code"].astype(int).astype(str).str.zfill(2)
        + metro_county["FIPS County Code"].astype(int).astype(str).str.zfill(3)
    )

    metro_county = metro_county[
        ["CBSA Code", "CBSA Title", "county_fips", "County/County Equivalent", "State Name"]
    ].drop_duplicates()

    metro_county["cbsa_title_clean"] = clean_cbsa_title(metro_county["CBSA Title"])

    return metro_county


def prepare_cbsa_population(cbsa_pop: pd.DataFrame) -> pd.DataFrame:
    """
    Clean Census metro population workbook and keep only rows
    representing actual metropolitan areas.
    """
    pop = cbsa_pop.rename(columns={
        "Geographic Area": "cbsa_title",
        "Unnamed: 6": "population_2024",
    }).copy()

    pop = pop[["cbsa_title", "population_2024"]].copy()
    pop["cbsa_title"] = pop["cbsa_title"].astype(str).str.strip()
    pop["population_2024"] = pd.to_numeric(pop["population_2024"], errors="coerce")

    pop = pop[pop["cbsa_title"].str.contains("Metro Area", na=False)].copy()
    pop["cbsa_title_clean"] = clean_cbsa_title(pop["cbsa_title"])

    logger.info(f"metro population rows after filter: {pop.shape[0]:,}")

    return pop


def merge_cbsa_reference(
    metro_county: pd.DataFrame,
    metro_pop: pd.DataFrame,
) -> pd.DataFrame:
    """merge metropolitan delineation records with Census metro population values."""
    metro_ref = metro_county.merge(
        metro_pop[["cbsa_title", "cbsa_title_clean", "population_2024"]],
        on="cbsa_title_clean",
        how="left",
    )

    missing_population = metro_ref["population_2024"].isna().sum()

    if missing_population > 0:
        logger.warning(f"rows missing population after merge: {missing_population}")
    else:
        logger.info("all rows matched population data")

    return metro_ref


# save stage

def save_output(df: pd.DataFrame) -> None:
    """save the metro reference dataset."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    logger.info(f"rows: {df.shape[0]:,}")
    logger.info(f"saved -> {OUTPUT_FILE}")


# workflow manager

def build_metro_dataset() -> pd.DataFrame:
    """
    Build the Census CBSA reference dataset used for downstream
    access modeling and metro-level joins.
    """
    try:
        cbsa_county, cbsa_pop = load_inputs()
        metro_county = prepare_cbsa_county(cbsa_county)
        metro_pop = prepare_cbsa_population(cbsa_pop)
        metro_ref = merge_cbsa_reference(metro_county, metro_pop)
        save_output(metro_ref)

        return metro_ref

    except FileNotFoundError as e:
        logger.error(f"source file not found: {e}")
        raise

    except ValueError as e:
        logger.error(f"column validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error building metro dataset: {e}")
        raise


if __name__ == "__main__":
    build_metro_dataset()