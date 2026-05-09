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

RISK_FILE = Path("data/model_outputs/access_risk_classified.csv")
HRSA_CACHE_FILE = Path("data/reference_tables/hrsa_hpsa_raw.csv")
OUTPUT_FILE = Path("data/model_outputs/hrsa_validation.csv")
METADATA_FILE = Path("data/model_outputs/hrsa_validation_metadata.json")

HRSA_HPSA_URL = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv"
HRSA_FETCH_TIMEOUT = 45

HPSA_ACTIVE_STATUS = "Designated"
HPSA_DISCIPLINE = "Primary Care"

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


def compute_validation_metrics(merged: pd.DataFrame) -> dict:
    """agreement and correlation between Ovara risk tiers and HRSA HPSA burden."""
    ovara_high = merged["risk_tier"] == "high_risk"
    hrsa_present = merged["hrsa_hpsa_present"].fillna(False)

    tp = int((ovara_high & hrsa_present).sum())
    fp = int((ovara_high & ~hrsa_present).sum())
    fn = int((~ovara_high & hrsa_present).sum())
    tn = int((~ovara_high & ~hrsa_present).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    agreement_rate = (tp + tn) / len(merged)

    # Spearman: Ovara risk_score vs raw HRSA shortage population
    spearman_pop_r = spearman_pop_p = None
    if "hrsa_shortage_pop" in merged.columns:
        d = merged[["risk_score", "hrsa_shortage_pop"]].dropna()
        if len(d) >= 5:
            r, p = scipy_stats.spearmanr(d["risk_score"], d["hrsa_shortage_pop"])
            spearman_pop_r, spearman_pop_p = round(float(r), 4), round(float(p), 4)

    # Spearman: Ovara risk_score vs HRSA avg HPSA score (already normalized, 0-25 scale)
    spearman_score_r = spearman_score_p = None
    if "hrsa_avg_score" in merged.columns:
        d = merged[merged["hrsa_hpsa_present"]][["risk_score", "hrsa_avg_score"]].dropna()
        if len(d) >= 5:
            r, p = scipy_stats.spearmanr(d["risk_score"], d["hrsa_avg_score"])
            spearman_score_r, spearman_score_p = round(float(r), 4), round(float(p), 4)

    # mean HRSA burden by Ovara risk tier
    def _tier_means(col: str) -> dict:
        if col not in merged.columns:
            return {}
        return {
            str(k): round(float(v), 2)
            for k, v in merged.groupby("risk_tier", observed=False)[col].mean().dropna().items()
        }

    burden_by_tier = _tier_means("hrsa_shortage_pop")
    avg_score_by_tier = _tier_means("hrsa_avg_score")

    # high_risk states detail
    detail_cols = [c for c in ["practice_state", "risk_score", "hrsa_hpsa_present",
                                "hrsa_hpsa_count", "hrsa_avg_score"] if c in merged.columns]
    high_risk_detail = (
        merged[ovara_high][detail_cols]
        .sort_values("risk_score", ascending=False)
        .to_dict(orient="records")
    )

    metrics = {
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "agreement_rate": round(agreement_rate, 4),
        "spearman_r_risk_vs_hpsa_shortage_pop": spearman_pop_r,
        "spearman_p_hpsa_shortage_pop": spearman_pop_p,
        "spearman_r_risk_vs_hrsa_avg_score": spearman_score_r,
        "spearman_p_hrsa_avg_score": spearman_score_p,
        "avg_hrsa_shortage_pop_by_tier": burden_by_tier,
        "avg_hrsa_hpsa_score_by_tier": avg_score_by_tier,
        "high_risk_state_detail": high_risk_detail,
    }

    logger.info(
        f"precision={precision:.2%}  recall={recall:.2%}  "
        f"f1={f1:.2%}  agreement={agreement_rate:.2%}"
    )
    if spearman_score_r is not None:
        logger.info(
            f"spearman r (risk_score vs hrsa_avg_score): {spearman_score_r}  "
            f"p={spearman_score_p}"
        )

    return metrics


def run_hrsa_validation(refresh: bool = False) -> pd.DataFrame | None:
    """
    External validation: compare Ovara access risk tiers against HRSA HPSA
    Primary Care shortage designations aggregated to the state level.
    """
    try:
        risk = pd.read_csv(RISK_FILE)
        logger.info(f"loaded risk classification: {risk.shape[0]} states")

        hrsa_raw = fetch_hrsa_hpsa(refresh=refresh)
        if hrsa_raw is None:
            logger.warning("HRSA data unavailable, validation skipped")
            return None

        hrsa_state = aggregate_hpsa_by_state(hrsa_raw)
        if hrsa_state is None:
            logger.warning("HRSA aggregation failed, validation skipped")
            return None

        merged = risk.merge(hrsa_state, on="practice_state", how="left")

        for col, fill in [
            ("hrsa_hpsa_present", False),
            ("hrsa_hpsa_count", 0),
            ("hrsa_shortage_pop", 0.0),
            ("hrsa_avg_score", np.nan),
            ("hrsa_fte_shortage", 0.0),
        ]:
            if col in merged.columns:
                merged[col] = merged[col].fillna(fill)

        metrics = compute_validation_metrics(merged)

        output_cols = [c for c in [
            "practice_state", "state_name", "risk_tier", "risk_score", "risk_rank",
            "hrsa_hpsa_present", "hrsa_hpsa_count", "hrsa_shortage_pop",
            "hrsa_avg_score", "hrsa_fte_shortage",
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
        logger.error(f"input file not found: {RISK_FILE}")
        raise

    except Exception as e:
        logger.error(f"unexpected error in HRSA validation: {e}")
        raise


if __name__ == "__main__":
    run_hrsa_validation()
