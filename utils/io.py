"""
Small wrappers around csv and json writes.

Almost every analysis stage saves a csv or json output to disk. The pattern
is always the same: make sure the parent folder exists, write the file,
then log the save. This module collapses that pattern into one call so
stages stay focused on the actual analysis instead of plumbing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd


def save_csv(
    df: pd.DataFrame,
    path: Path,
    logger: logging.Logger | None = None,
    *,
    index: bool = False,
) -> None:
    """
    Save a DataFrame to csv, creating parent folders if needed and logging the save.

    Parameters
    df : pd.DataFrame
        Data to write.
    path : Path
        Full output path including filename.
    logger : logging.Logger or None
        Logger to receive a single info line on success. Skipped if None.
    index : bool
        Whether to write the DataFrame index. Defaults to False to match the
        convention used everywhere else in this project.

    Returns
    None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)
    if logger is not None:
        logger.info(f"saved -> {path}")


def save_json(
    payload: Any,
    path: Path,
    logger: logging.Logger | None = None,
    *,
    indent: int = 2,
) -> None:
    """
    Save a dict or list to json, creating parent folders if needed.

    Parameters
    payload : Any
        Anything json serializable. Used here for evaluation results,
        risk metadata, and clustering metadata.
    path : Path
        Full output path including filename.
    logger : logging.Logger or None
        Logger to receive a single info line on success. Skipped if None.
    indent : int
        Pretty print indent. Defaults to 2 so the files stay human readable.

    Returns
    None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=indent)
    if logger is not None:
        logger.info(f"saved -> {path}")
