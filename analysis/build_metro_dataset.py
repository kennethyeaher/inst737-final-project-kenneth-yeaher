import pandas as pd
from pathlib import Path


CBSA_COUNTY_FILE = Path("data/external/list1_2023.xlsx")
CBSA_POP_FILE = Path("data/external/cbsa-met-est2024-pop.xlsx")
OUTPUT_FILE = Path("data/load/cbsa_reference_dataset.csv")


def build_metro_dataset() -> pd.DataFrame:
    """
    Build a CBSA reference dataset from Census files.

    For Part 2, this prepares the metro lookup + population layer that will
    later be merged with provider geography once a ZIP-to-county crosswalk
    is added to the pipeline.
    """

    print("\n[METRO] ===== BUILDING METRO REFERENCE DATASET =====")

    # list1_2023 has the real headers on row 3
    cbsa_county = pd.read_excel(CBSA_COUNTY_FILE, header=2)

    # cbsa population file also needs header row 3
    cbsa_pop = pd.read_excel(CBSA_POP_FILE, header=2)

    print(f"[METRO] CBSA-county rows: {cbsa_county.shape[0]}")
    print(f"[METRO] CBSA population rows: {cbsa_pop.shape[0]}")

    # keep only metro areas, not micropolitan
    cbsa_county = cbsa_county[
        cbsa_county["Metropolitan/Micropolitan Statistical Area"] == "Metropolitan Statistical Area"
    ].copy()

    # build a clean county FIPS code
    cbsa_county["county_fips"] = (
        cbsa_county["FIPS State Code"].astype(str).str.zfill(2)
        + cbsa_county["FIPS County Code"].astype(str).str.zfill(3)
    )

    # keep only useful columns
    cbsa_county = cbsa_county[
        ["CBSA Code", "CBSA Title", "county_fips", "County/County Equivalent", "State Name"]
    ].drop_duplicates()

    # clean population file
    cbsa_pop = cbsa_pop.rename(columns={
        "Geographic Area": "cbsa_title",
        "Unnamed: 6": "population_2024"
    })

    cbsa_pop = cbsa_pop[["cbsa_title", "population_2024"]].copy()
    cbsa_pop = cbsa_pop.dropna(subset=["cbsa_title", "population_2024"])

    # only keep rows that look like metro names
    cbsa_pop = cbsa_pop[
        cbsa_pop["cbsa_title"].astype(str).str.contains("Metro Area", na=False)
    ].copy()

    # normalize title for rough joining
    cbsa_pop["cbsa_title_clean"] = (
        cbsa_pop["cbsa_title"]
        .str.replace(" Metro Area", "", regex=False)
        .str.strip()
    )

    cbsa_county["cbsa_title_clean"] = cbsa_county["CBSA Title"].astype(str).str.strip()

    metro_ref = cbsa_county.merge(
        cbsa_pop,
        on="cbsa_title_clean",
        how="left"
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    metro_ref.to_csv(OUTPUT_FILE, index=False)

    print(f"[METRO] Saved → {OUTPUT_FILE}")
    print(f"[METRO] Rows: {metro_ref.shape[0]}")
    print("[METRO] ===== METRO REFERENCE DATASET READY =====\n")

    return metro_ref


if __name__ == "__main__":
    build_metro_dataset()