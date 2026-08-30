from __future__ import annotations

import warnings
import requests
import numpy as np
import pandas as pd
from io import StringIO
from pathlib import Path
from scipy import stats as scipy_stats

from utils.io import save_csv, save_json
from utils.logging_config import setup_logger

warnings.filterwarnings("ignore", message=".*LibreSSL.*")

logger = setup_logger("ovara.hrsa_validation")

# file paths

DENSITY_FILE = Path("data/model_outputs/state_density_ranking.csv")
HRSA_CACHE_FILE = Path("data/reference_tables/hrsa_hpsa_raw.csv")
OUTPUT_FILE = Path("data/model_outputs/hrsa_validation.csv")
METADATA_FILE = Path("data/model_outputs/hrsa_validation_metadata.json")

HRSA_HPSA_URL = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv"
HRSA_FETCH_TIMEOUT = 45

HPSA_ACTIVE_STATUS = "Designated"
HPSA_DISCIPLINE = "Primary Care"

# HRSA burden measures, each normalized per 100k residents so a big state
# does not dominate the ranking purely by being big
BURDEN_MEASURES = {
    "hrsa_shortage_pop_per_100k": "hrsa_shortage_pop",
    "hrsa_fte_shortage_per_100k": "hrsa_fte_shortage",
    "hrsa_hpsa_count_per_100k": "hrsa_hpsa_count",
}

# smallest sample a correlation is reported on
MIN_CORRELATION_ROWS = 5

# what the burden measures are correlated against, now that the risk score is retired
DENSITY_COLUMN = "providers_per_100k"

# normalized column name candidates (HRSA uses spaces; we lowercase + underscore after load)

_STATE_COLS = ["common_state_abbr", "state_abbr", "state_abbreviation"]
_STATUS_COLS = ["hpsa_status", "status"]
_DISC_COLS = ["hpsa_discipline_class", "discipline_class"]
_ID_COLS = ["hpsa_id", "id"]
_POP_COLS = ["hpsa_designation_population", "designation_population", "hpsa_population"]
_SCORE_COLS = ["hpsa_score", "score"]
_FTE_COLS = ["hpsa_fte", "fte"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _pick(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def fetch_hrsa_hpsa(refresh: bool = False) -> pd.DataFrame | None:
    """download HRSA Primary Care HPSA file and cache locally; return None on failure."""
    if HRSA_CACHE_FILE.exists() and not refresh:
        logger.info(f"loading HRSA cache -> {HRSA_CACHE_FILE}")
        try:
            return _normalize(pd.read_csv(HRSA_CACHE_FILE, low_memory=False))
        except Exception as e:
            logger.warning(f"cache read failed: {e} - refetching")

    try:
        logger.info("fetching HRSA HPSA Primary Care data...")
        resp = requests.get(HRSA_HPSA_URL, timeout=HRSA_FETCH_TIMEOUT)
        resp.raise_for_status()
        raw = pd.read_csv(StringIO(resp.text), low_memory=False)
        save_csv(raw, HRSA_CACHE_FILE, logger)
        return _normalize(raw)

    except requests.exceptions.Timeout:
        logger.warning(f"HRSA fetch timed out after {HRSA_FETCH_TIMEOUT}s")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"HRSA fetch failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"unexpected error loading HRSA data: {e}")
        return None


def aggregate_hpsa_by_state(hrsa: pd.DataFrame) -> pd.DataFrame | None:
    """filter to active Primary Care HPSAs and aggregate shortage burden to state level."""
    state_col = _pick(hrsa, _STATE_COLS)
    status_col = _pick(hrsa, _STATUS_COLS)
    disc_col = _pick(hrsa, _DISC_COLS)
    id_col = _pick(hrsa, _ID_COLS)
    pop_col = _pick(hrsa, _POP_COLS)
    score_col = _pick(hrsa, _SCORE_COLS)
    fte_col = _pick(hrsa, _FTE_COLS)

    missing = [n for n, c in [("state", state_col), ("status", status_col), ("discipline", disc_col)]
               if c is None]
    if missing:
        logger.warning(f"HRSA file missing required columns: {missing}")
        logger.warning(f"available columns: {list(hrsa.columns)[:20]}")
        return None

    active = hrsa[
        (hrsa[status_col].str.strip() == HPSA_ACTIVE_STATUS) &
        (hrsa[disc_col].str.strip() == HPSA_DISCIPLINE)
    ].copy()
    logger.info(f"active Primary Care HPSAs: {len(active):,}")

    agg_kwargs = {}
    if id_col:
        agg_kwargs["hrsa_hpsa_count"] = (id_col, "count")
    if pop_col:
        active[pop_col] = pd.to_numeric(active[pop_col], errors="coerce").fillna(0)
        agg_kwargs["hrsa_shortage_pop"] = (pop_col, "sum")
    if score_col:
        active[score_col] = pd.to_numeric(active[score_col], errors="coerce")
        agg_kwargs["hrsa_avg_score"] = (score_col, "mean")
    if fte_col:
        active[fte_col] = pd.to_numeric(active[fte_col], errors="coerce").fillna(0)
        agg_kwargs["hrsa_fte_shortage"] = (fte_col, "sum")

    if not agg_kwargs:
        logger.warning("no quantitative HRSA columns available for aggregation")
        return None

    agg = (
        active.groupby(state_col, as_index=False)
        .agg(**agg_kwargs)
        .rename(columns={state_col: "practice_state"})
    )
    agg["hrsa_hpsa_present"] = True
    logger.info(f"states with active Primary Care HPSAs: {len(agg)}")
    return agg


def add_burden_per_100k(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Express each HRSA burden measure per 100k residents.

    Raw HRSA totals scale with state size, so correlating them against a risk
    score mostly measures which states are large. Dividing by population makes
    the comparison about shortage intensity instead.

    Parameters
    merged : pd.DataFrame with state_population and the raw HRSA burden columns.

    Returns
    pd.DataFrame with one per 100k column per available burden measure.
    """
    merged = merged.copy()

    for rate_col, raw_col in BURDEN_MEASURES.items():
        if raw_col in merged.columns:
            merged[rate_col] = merged[raw_col] / merged["state_population"] * 100000

    return merged


def compute_validation_metrics(merged: pd.DataFrame) -> dict:
    """
    Measure rank agreement between observed provider density and HRSA burden.

    This used to correlate against a residual based risk score, which has since
    been retired along with the tiers built on it. Observed density needs no
    model, so it is the honest thing to validate. A state with more providers
    per resident should carry less federal shortage burden, meaning every
    correlation here is expected to be negative.

    Parameters
    merged : pd.DataFrame with providers_per_100k and the per 100k burden columns.

    Returns
    dict of rho and p for each burden measure.
    """
    correlations = {}

    for rate_col, raw_col in BURDEN_MEASURES.items():
        if rate_col not in merged.columns:
            continue

        pair = merged[[DENSITY_COLUMN, rate_col, raw_col]].dropna()
        if len(pair) < MIN_CORRELATION_ROWS:
            logger.warning(f"too few states to correlate risk score against {rate_col}")
            continue

        rho, p_value = scipy_stats.spearmanr(pair[DENSITY_COLUMN], pair[rate_col])
        raw_rho, raw_p = scipy_stats.spearmanr(pair[DENSITY_COLUMN], pair[raw_col])

        correlations[rate_col] = {
            "spearman_rho": round(float(rho), 4),
            "p_value": round(float(p_value), 4),
            "n_states": int(len(pair)),

            # the same correlation before dividing by population, kept only to
            # show how much of any agreement is really state size
            "size_confounded_rho": round(float(raw_rho), 4),
            "size_confounded_p_value": round(float(raw_p), 4),
        }

    # HPSA score is HRSA's own severity rating on a fixed 0 to 25 scale, so it
    # needs no population adjustment
    if "hrsa_avg_score" in merged.columns:
        pair = merged[merged["hrsa_hpsa_present"]][[DENSITY_COLUMN, "hrsa_avg_score"]].dropna()
        if len(pair) >= MIN_CORRELATION_ROWS:
            rho, p_value = scipy_stats.spearmanr(pair[DENSITY_COLUMN], pair["hrsa_avg_score"])
            correlations["hrsa_avg_score"] = {
                "spearman_rho": round(float(rho), 4),
                "p_value": round(float(p_value), 4),
                "n_states": int(len(pair)),
            }

    thinnest_detail = (
        merged.nsmallest(10, DENSITY_COLUMN)[
            [c for c in ["practice_state", DENSITY_COLUMN, "density_rank",
                         "hrsa_hpsa_count", "hrsa_shortage_pop_per_100k", "hrsa_avg_score"]
             if c in merged.columns]
        ]
        .round(4)
        .to_dict(orient="records")
    )

    metrics = {
        "correlated_against": DENSITY_COLUMN,
        "expected_direction": "negative, more providers per resident means less shortage burden",
        "rank_agreement": correlations,
        "thinnest_state_detail": thinnest_detail,
    }

    logger.info(f"rank agreement between {DENSITY_COLUMN} and HRSA burden:")
    for measure, scores in correlations.items():
        line = (
            f"  {measure}: rho {scores['spearman_rho']:+.4f} "
            f"p {scores['p_value']:.4f} (n {scores['n_states']})"
        )
        if "size_confounded_rho" in scores:
            line += (
                f", unnormalized rho {scores['size_confounded_rho']:+.4f} "
                f"p {scores['size_confounded_p_value']:.4f}"
            )
        logger.info(line)

    return metrics


def run_hrsa_validation(refresh: bool = False) -> pd.DataFrame | None:
    """
    External validation: compare observed state provider density against HRSA
    HPSA Primary Care shortage designations aggregated to the state level.
    """
    try:
        density = pd.read_csv(DENSITY_FILE)
        logger.info(f"loaded state density ranking: {density.shape[0]} states")

        hrsa_raw = fetch_hrsa_hpsa(refresh=refresh)
        if hrsa_raw is None:
            logger.warning("HRSA data unavailable, validation skipped")
            return None

        hrsa_state = aggregate_hpsa_by_state(hrsa_raw)
        if hrsa_state is None:
            logger.warning("HRSA aggregation failed, validation skipped")
            return None

        merged = density.merge(hrsa_state, on="practice_state", how="left")

        for col, fill in [
            ("hrsa_hpsa_present", False),
            ("hrsa_hpsa_count", 0),
            ("hrsa_shortage_pop", 0.0),
            ("hrsa_avg_score", np.nan),
            ("hrsa_fte_shortage", 0.0),
        ]:
            if col in merged.columns:
                merged[col] = merged[col].fillna(fill)

        merged = add_burden_per_100k(merged)
        metrics = compute_validation_metrics(merged)

        output_cols = [c for c in [
            "practice_state", "state_name", "providers_per_100k", "density_rank",
            "density_percentile",
            "hrsa_hpsa_present", "hrsa_hpsa_count", "hrsa_shortage_pop",
            "hrsa_avg_score", "hrsa_fte_shortage",
            "hrsa_shortage_pop_per_100k", "hrsa_fte_shortage_per_100k",
            "hrsa_hpsa_count_per_100k",
        ] if c in merged.columns]

        save_csv(merged[output_cols], OUTPUT_FILE, logger)

        metadata = {
            "hrsa_source": HRSA_HPSA_URL,
            "hpsa_discipline_filter": HPSA_DISCIPLINE,
            "hpsa_status_filter": HPSA_ACTIVE_STATUS,
            "total_states": len(merged),
            **metrics,
        }
        save_json(metadata, METADATA_FILE, logger)

        return merged

    except FileNotFoundError:
        logger.error(f"input file not found: {DENSITY_FILE}")
        raise

    except Exception as e:
        logger.error(f"unexpected error in HRSA validation: {e}")
        raise


if __name__ == "__main__":
    run_hrsa_validation()
