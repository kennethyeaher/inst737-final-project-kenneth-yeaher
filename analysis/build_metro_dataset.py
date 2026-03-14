import pandas as pd
from pathlib import Path

# file path 

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

# helper script

def validate_columns(df: pd.DataFrame, required: set[str], df_name: str) -> None:
    """Fail fast if expected columns are missing."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {sorted(missing)}")
    
def clean_cbsa_title(series: pd.Series) -> pd.Series:
    """
    Standardize CBSA titles so Census population titles and delineation titles
    can be merged more reliably.
    """
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"^\.", "", regex=True)          # remove leading dot from Census rows
        .str.replace(" Metro Area", "", regex=False)  # remove Census suffix
        .str.replace(r"\s+", " ", regex=True)         # normalize whitespace
        .str.strip()
    )


# load stages 

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load CBSA delineation and metro population source files.
    Both Excel workbooks use row 3 as the true header row.
    """
    print("\n[METRO] ===== BUILDING METRO REFERENCE DATASET =====")

    cbsa_county = pd.read_excel(CBSA_COUNTY_FILE, header=2)
    cbsa_pop = pd.read_excel(CBSA_POP_FILE, header=2)

    validate_columns(cbsa_county, COUNTY_REQUIRED_COLUMNS, "cbsa_county source")
    validate_columns(cbsa_pop, POP_REQUIRED_COLUMNS, "cbsa_population source")

    print(f"[METRO] CBSA-county rows: {cbsa_county.shape[0]}")
    print(f"[METRO] CBSA population rows: {cbsa_pop.shape[0]}")

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

    metro_county["county_fips"] = (
        metro_county["FIPS State Code"].astype(str).str.zfill(2)
        + metro_county["FIPS County Code"].astype(str).str.zfill(3)
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

    return pop


def merge_cbsa_reference(
    metro_county: pd.DataFrame,
    metro_pop: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge metropolitan delineation records with Census metro population values.
    """
    metro_ref = metro_county.merge(
        metro_pop[["cbsa_title", "cbsa_title_clean", "population_2024"]],
        on="cbsa_title_clean",
        how="left",
    )

    missing_population = metro_ref["population_2024"].isna().sum()
    print(f"[METRO] Rows missing population after merge: {missing_population}")

    return metro_ref

# save stages

def save_output(df: pd.DataFrame) -> None:
    """Save the metro reference dataset."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"[METRO] Saved → {OUTPUT_FILE}")
    print(f"[METRO] Rows: {df.shape[0]}")
    print("[METRO] ===== METRO REFERENCE DATASET READY =====")

# workflow manager 

def build_metro_dataset() -> pd.DataFrame:
    """
    Build the Census CBSA reference dataset used for downstream
    access modeling and metro-level joins.
    """
    cbsa_county, cbsa_pop = load_inputs()
    metro_county = prepare_cbsa_county(cbsa_county)
    metro_pop = prepare_cbsa_population(cbsa_pop)
    metro_ref = merge_cbsa_reference(metro_county, metro_pop)
    save_output(metro_ref)

    return metro_ref


if __name__ == "__main__":
    build_metro_dataset()

