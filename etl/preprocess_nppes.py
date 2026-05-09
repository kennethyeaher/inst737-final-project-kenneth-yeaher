"""
One time preprocessing for the full NPPES weekly download.

The NPPES weekly file is around 8 GB and contains every active provider in
the country. This script reads it in chunks, keeps only rows whose primary
taxonomy code matches the reproductive and women's health code set, and
writes a much smaller csv that the regular pipeline can consume.

Run this once after each NPPES release:
    python etl/preprocess_nppes.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.io import save_csv
from utils.logging_config import setup_logger

logger = setup_logger("ovara.preprocess_nppes")


# reproductive and women's health taxonomy codes from the NUCC code set
# kept as a set so the chunk filter stays fast on a large file
REPRODUCTIVE_HEALTH_CODES: set[str] = {
    # obstetrics and gynecology
    "207V00000X", "207VC0200X", "207VE0102X", "207VF0040X",
    "207VG0400X", "207VH0002X", "207VM0101X", "207VX0000X",
    "207VX0201X", "207VR0500X",
    # midwifery
    "176B00000X", "367A00000X",
    # nurse practitioner, women's health
    "363LW0102X",
}

TAXONOMY_COLUMN = "Healthcare Provider Taxonomy Code_1"

RAW_DIR = Path("data/extracted/nppes_weekly_raw")
OUTPUT_FILE = RAW_DIR / "npidata_reproductive_health.csv"

CHUNK_SIZE = 500_000


def find_full_file() -> Path:
    """
    Locate the largest npidata file in the raw NPPES folder.

    NPPES ships both a header definition file and the actual data file
    in the same archive. The data file is always the larger of the two,
    so picking by size is safe.

    Returns
    Path to the data file.

    Raises
    FileNotFoundError if no npidata files are present.
    """
    files = [
        f for f in RAW_DIR.glob("npidata_pfile*.csv")
        if "fileheader" not in f.name.lower()
    ]
    if not files:
        raise FileNotFoundError(f"No npidata files found in {RAW_DIR}")
    return max(files, key=lambda f: f.stat().st_size)


def preprocess() -> None:
    """
    Stream the NPPES file in chunks and keep only reproductive health providers.

    Writes the filtered subset to OUTPUT_FILE so the pipeline's extract
    stage has a reasonable size csv to work with.
    """
    source = find_full_file()
    logger.info(f"source: {source}")
    logger.info(f"size: {source.stat().st_size / 1e9:.2f} GB")

    chunks: list[pd.DataFrame] = []
    rows_seen = 0

    # streaming the file in chunks keeps memory usage bounded even though
    # the source is multiple gigabytes
    for chunk in pd.read_csv(source, dtype=str, low_memory=False, chunksize=CHUNK_SIZE):
        rows_seen += len(chunk)
        filtered = chunk[chunk[TAXONOMY_COLUMN].isin(REPRODUCTIVE_HEALTH_CODES)]
        if len(filtered) > 0:
            chunks.append(filtered)
        logger.info(f"{rows_seen:,} rows scanned, {sum(len(c) for c in chunks):,} matched")

    df = pd.concat(chunks, ignore_index=True)
    save_csv(df, OUTPUT_FILE, logger)
    logger.info(f"providers kept: {len(df):,}")


if __name__ == "__main__":
    preprocess()
