
"""

One time preprocessing script.

Reads the full NPPES file, filters to reproductive health

taxonomy codes, and saves a smaller file that the pipeline consumes.

Run once after downloading a new NPPES release:

    python preprocess_nppes.py

"""

import pandas as pd

from pathlib import Path

REPRODUCTIVE_HEALTH_CODES = {

    "207V00000X", "207VC0200X", "207VE0102X", "207VF0040X",

    "207VG0400X", "207VH0002X", "207VM0101X", "207VX0000X",

    "207VX0201X", "207VR0500X",

    "176B00000X", "367A00000X",

    "363LW0102X",

}

TAXONOMY_COLUMN = "Healthcare Provider Taxonomy Code_1"

RAW_DIR = Path("data/extracted/nppes_weekly_raw")

OUTPUT_FILE = RAW_DIR / "npidata_reproductive_health.csv"

def find_full_file():

    files = [f for f in RAW_DIR.glob("npidata_pfile*.csv") if "fileheader" not in f.name.lower()]

    if not files:

        raise FileNotFoundError(f"No npidata files found in {RAW_DIR}")

    return max(files, key=lambda f: f.stat().st_size)

def preprocess():

    source = find_full_file()

    print(f"[PREPROCESS] Source: {source}")

    print(f"[PREPROCESS] Size: {source.stat().st_size / 1e9:.2f} GB")

    chunks, rows = [], 0

    for chunk in pd.read_csv(source, dtype=str, low_memory=False, chunksize=500_000):

        rows += len(chunk)

        filtered = chunk[chunk[TAXONOMY_COLUMN].isin(REPRODUCTIVE_HEALTH_CODES)]

        if len(filtered) > 0:

            chunks.append(filtered)

        print(f"[PREPROCESS] {rows:,} rows — {sum(len(c) for c in chunks):,} matched")

    df = pd.concat(chunks, ignore_index=True)

    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n[PREPROCESS] Providers: {len(df):,}")

    print(f"[PREPROCESS] Saved → {OUTPUT_FILE}")

if __name__ == "__main__":

    preprocess()

