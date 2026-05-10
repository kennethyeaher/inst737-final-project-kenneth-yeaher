"""
Cached fetch helper for slow external sources.

Several reference tables come from the Census API or HRSA downloads.
Once fetched, those files almost never change between pipeline runs, so
the project caches them under data/reference_tables and reuses them
unless the caller explicitly asks for a refresh. This module centralizes
that read or download dance.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pandas as pd


def load_or_fetch(
    cache_path: Path,
    fetcher: Callable[[], pd.DataFrame],
    *,
    refresh: bool = False,
    logger: logging.Logger | None = None,
    read_kwargs: dict | None = None,
) -> pd.DataFrame:
    """
    Return a cached csv if it exists, otherwise call fetcher and cache the result.

    The fetcher is only invoked when the cache is missing or refresh is True.
    On a cache miss the result is written to cache_path before being returned,
    so the next run is fast.

    Parameters
    cache_path : Path
        Where the cached csv lives. Parent folders are created on save.
    fetcher : Callable returning pd.DataFrame
        Zero argument function that pulls fresh data (typically an API call).
    refresh : bool
        Force a re fetch even if the cache file is present.
    logger : logging.Logger or None
        Logger for the cache hit or miss line. Skipped if None.
    read_kwargs : dict or None
        Optional kwargs forwarded to pd.read_csv when loading the cache
        (e.g. dtype overrides for FIPS strings with leading zeros).

    Returns
    pd.DataFrame loaded from cache or freshly fetched.
    """
    read_kwargs = read_kwargs or {}

    # cache hit: skip the network call and return the saved file
    if cache_path.exists() and not refresh:
        if logger is not None:
            logger.info(f"loading cache -> {cache_path}")
        return pd.read_csv(cache_path, **read_kwargs)

    # cache miss or forced refresh: pull fresh data and persist for next time
    if logger is not None:
        logger.info(f"fetching fresh data (cache miss or refresh requested)")
    df = fetcher()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)

    if logger is not None:
        logger.info(f"cached -> {cache_path} ({len(df):,} rows)")

    return df
