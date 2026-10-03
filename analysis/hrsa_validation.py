from __future__ import annotations

import warnings
import requests
import numpy as np
import pandas as pd
from io import StringIO
from pathlib import Path
from scipy import stats as scipy_stats

from utils.fips import FIPS_TO_STATE
from utils.io import save_csv, save_json
from utils.logging_config import setup_logger

warnings.filterwarnings("ignore", message=".*LibreSSL.*")

logger = setup_logger("ovara.hrsa_validation")

# file paths

DENSITY_FILE = Path("data/model_outputs/state_density_ranking.csv")
COUNTY_RISK_FILE = Path("data/model_outputs/county_risk_classified.csv")
HRSA_CACHE_FILE = Path("data/reference_tables/hrsa_hpsa_raw.csv")
OUTPUT_FILE = Path("data/model_outputs/hrsa_validation.csv")
COUNTY_OUTPUT_FILE = Path("data/model_outputs/hrsa_county_validation.csv")
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

# the denominator each grain divides burden by
COUNTY_POPULATION_COLUMN = "total_population"

# number of population strata the shared denominator check splits counties into
POPULATION_STRATA = 4

# normalized column name candidates (HRSA uses spaces; we lowercase + underscore after load)

_STATE_COLS = ["common_state_abbr", "state_abbr", "state_abbreviation"]
_STATUS_COLS = ["hpsa_status", "status"]
_DISC_COLS = ["hpsa_discipline_class", "discipline_class"]
_ID_COLS = ["hpsa_id", "id"]
_POP_COLS = ["hpsa_designation_population", "designation_population", "hpsa_population"]
_SCORE_COLS = ["hpsa_score", "score"]
_FTE_COLS = ["hpsa_fte", "fte"]

# HRSA ships two full five digit county columns. common_state_county_fips_code is
# the cleaner of the two, the other carries a retired code and a placeholder row
_COUNTY_FIPS_COLS = [
    "common_state_county_fips_code",
    "state_and_county_federal_information_processing_standard_code",
]

# county access tiers, ordered from worst access to best, for the tier test
COUNTY_TIER_ORDER = ["access_desert", "critical", "underserved", "adequate", "well_served"]

# below this share of in universe HRSA counties resolving, the join is a finding
# rather than a result. this measures join quality, not HPSA coverage: a county
# with no designation is a real zero, not a failed match
MIN_COUNTY_MATCH_RATE = 0.95


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


def add_burden_per_100k(
    merged: pd.DataFrame,
    population_column: str = "state_population",
) -> pd.DataFrame:
    """
    Express each HRSA burden measure per 100k residents.

    Raw HRSA totals scale with how many people live in the area, so correlating
    them against density mostly measures size. Dividing by population makes the
    comparison about shortage intensity instead.

    Parameters
    merged : pd.DataFrame with a population column and the raw HRSA burden columns.
    population_column : str naming the denominator, which differs by grain.

    Returns
    pd.DataFrame with one per 100k column per available burden measure.
    """
    merged = merged.copy()

    for rate_col, raw_col in BURDEN_MEASURES.items():
        if raw_col in merged.columns:
            merged[rate_col] = merged[raw_col] / merged[population_column] * 100000

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



def aggregate_hpsa_by_county(hrsa: pd.DataFrame) -> pd.DataFrame | None:
    """
    Aggregate active Primary Care HPSA designations to county FIPS.

    HPSAs are designated at service area level, often below the county, so a
    county grain keeps far more of the geographic resolution than rolling the
    same designations up to 51 states.

    Parameters
    hrsa : pd.DataFrame of raw HRSA rows with normalized column names.

    Returns
    pd.DataFrame with one row per county, or None if the file has no usable
    county column.
    """
    fips_col = _pick(hrsa, _COUNTY_FIPS_COLS)
    status_col = _pick(hrsa, _STATUS_COLS)
    disc_col = _pick(hrsa, _DISC_COLS)

    if fips_col is None or status_col is None or disc_col is None:
        logger.warning("HRSA file has no usable county FIPS, status, or discipline column")
        return None

    active = hrsa[
        (hrsa[status_col].str.strip() == HPSA_ACTIVE_STATUS) &
        (hrsa[disc_col].str.strip() == HPSA_DISCIPLINE)
    ].copy()

    # leading zeros matter, and the column can arrive as numbers if the file
    # ever loses its placeholder rows
    active["county_fips"] = active[fips_col].astype(str).str.strip().str.zfill(5)

    id_col = _pick(active, _ID_COLS)
    pop_col = _pick(active, _POP_COLS)
    score_col = _pick(active, _SCORE_COLS)
    fte_col = _pick(active, _FTE_COLS)

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

    agg = active.groupby("county_fips", as_index=False).agg(**agg_kwargs)
    logger.info(f"counties with active Primary Care HPSAs: {len(agg):,}")
    return agg


def join_hpsa_to_counties(
    counties: pd.DataFrame,
    hrsa_county: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Join county HPSA burden onto the county access tiers and report the match rate.

    A county with no designation is a real zero rather than a missing value, so
    burden columns are filled with zero. HRSA counties that match nothing are
    reported separately, because a poor join is a finding in its own right.

    Parameters
    counties : pd.DataFrame of published county access tiers.
    hrsa_county : pd.DataFrame of HPSA burden aggregated to county FIPS.

    Returns
    tuple of the joined frame and a dict describing the join.
    """
    ovara_fips = set(counties["county_fips"])
    hrsa_fips = set(hrsa_county["county_fips"])

    # HRSA covers territories and Pacific jurisdictions the model does not, so
    # join quality is measured only against codes in the 51 modeled states
    in_universe = {fips for fips in hrsa_fips if fips[:2] in FIPS_TO_STATE}
    matched = in_universe & ovara_fips

    merged = counties.merge(hrsa_county, on="county_fips", how="left")

    for col in ["hrsa_hpsa_count", "hrsa_shortage_pop", "hrsa_fte_shortage"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0)

    merged["hrsa_hpsa_present"] = merged["hrsa_hpsa_count"] > 0

    join_report = {
        "ovara_counties": len(ovara_fips),
        "hrsa_counties": len(hrsa_fips),
        "hrsa_counties_in_modeled_states": len(in_universe),
        "matched_counties": len(matched),
        "join_match_rate": round(len(matched) / len(in_universe), 4),
        "unresolved_in_universe_fips": sorted(in_universe - ovara_fips),
        "out_of_universe_hrsa_counties": len(hrsa_fips - in_universe),
        "out_of_universe_state_prefixes": sorted(
            {fips[:2] for fips in hrsa_fips - in_universe}
        ),

        # a county with no designation is a real zero, so this is HPSA coverage
        # rather than a join metric
        "ovara_counties_with_a_designation": int(merged["hrsa_hpsa_present"].sum()),
        "designation_coverage": round(float(merged["hrsa_hpsa_present"].mean()), 4),
    }

    logger.info(
        f"county join: {len(matched):,} of {len(in_universe):,} in universe HRSA counties "
        f"resolved ({join_report['join_match_rate']:.2%}), "
        f"{join_report['out_of_universe_hrsa_counties']} territory counties out of scope"
    )
    logger.info(
        f"HPSA coverage: {join_report['ovara_counties_with_a_designation']:,} of "
        f"{len(ovara_fips):,} counties carry a designation "
        f"({join_report['designation_coverage']:.1%}), the rest are real zeros"
    )

    return merged, join_report


def validate_county_tiers(merged: pd.DataFrame) -> dict:
    """
    Test whether county access tiers and county density agree with HPSA burden.

    Two tests. Spearman against the continuous density, where a negative rho is
    the expected direction because more providers per resident should mean less
    shortage burden. Kruskal Wallis across the five access tiers, which asks
    whether burden differs by tier at all without assuming a shape.

    Parameters
    merged : pd.DataFrame of county tiers joined to HPSA burden.

    Returns
    dict of correlations and the tier test result.
    """
    merged = add_burden_per_100k(merged, population_column=COUNTY_POPULATION_COLUMN)

    correlations = {}
    for rate_col in BURDEN_MEASURES:
        if rate_col not in merged.columns:
            continue

        pair = merged[["providers_per_100k", rate_col]].dropna()
        if len(pair) < MIN_CORRELATION_ROWS:
            continue

        rho, p_value = scipy_stats.spearmanr(pair["providers_per_100k"], pair[rate_col])
        correlations[rate_col] = {
            "spearman_rho": round(float(rho), 4),
            "p_value": round(float(p_value), 6),
            "n_counties": int(len(pair)),
        }

    if "hrsa_avg_score" in merged.columns:
        pair = merged[["providers_per_100k", "hrsa_avg_score"]].dropna()
        if len(pair) >= MIN_CORRELATION_ROWS:
            rho, p_value = scipy_stats.spearmanr(
                pair["providers_per_100k"], pair["hrsa_avg_score"]
            )
            correlations["hrsa_avg_score"] = {
                "spearman_rho": round(float(rho), 4),
                "p_value": round(float(p_value), 6),
                "n_counties": int(len(pair)),
            }

    tier_test = _kruskal_across_tiers(merged, "hrsa_shortage_pop_per_100k")

    # both density and every burden rate divide by county population, so the
    # pooled correlations have to be checked against that before being believed
    denominator_checks = {
        rate_col: check_shared_denominator(merged, rate_col)
        for rate_col in BURDEN_MEASURES
        if rate_col in merged.columns
    }

    logger.info("county rank agreement between providers_per_100k and HRSA burden:")
    for measure, scores in correlations.items():
        logger.info(
            f"  {measure}: rho {scores['spearman_rho']:+.4f} "
            f"p {scores['p_value']:.6f} (n {scores['n_counties']:,})"
        )

    return {
        "rank_agreement": correlations,
        "tier_test": tier_test,
        "shared_denominator_checks": denominator_checks,
    }



def check_shared_denominator(merged: pd.DataFrame, burden_col: str) -> dict:
    """
    Test whether a county correlation survives once population is held roughly fixed.

    Provider density and a burden rate both divide by county population, and
    county population spans several orders of magnitude. Two ratios over a
    shared denominator can correlate through that denominator alone, so the
    pooled correlation is not evidence on its own. Splitting counties into
    population strata and correlating within each one removes the shared term.
    If the association is real it survives; if it was the denominator it
    collapses.

    Parameters
    merged : pd.DataFrame of counties with density, burden, and population.
    burden_col : str naming the per 100k burden column to test.

    Returns
    dict with the pooled correlation and one correlation per population stratum.
    """
    if burden_col not in merged.columns:
        return {}

    frame = merged[[DENSITY_COLUMN, burden_col, COUNTY_POPULATION_COLUMN]].dropna()
    if len(frame) < MIN_CORRELATION_ROWS:
        return {}

    pooled_rho, pooled_p = scipy_stats.spearmanr(frame[DENSITY_COLUMN], frame[burden_col])

    strata = pd.qcut(frame[COUNTY_POPULATION_COLUMN], POPULATION_STRATA, labels=False)

    within = []
    for stratum in sorted(strata.unique()):
        group = frame[strata == stratum]
        rho, p_value = scipy_stats.spearmanr(group[DENSITY_COLUMN], group[burden_col])
        within.append({
            "population_stratum": int(stratum) + 1,
            "n_counties": int(len(group)),
            "spearman_rho": round(float(rho), 4),
            "p_value": float(f"{p_value:.4g}"),
        })

    # the typical stratum, not the strongest one, and it has to keep the pooled
    # sign. a stratum that correlates the other way is not the effect surviving
    median_within = float(np.median([entry["spearman_rho"] for entry in within]))
    keeps_sign = (median_within * float(pooled_rho)) > 0
    keeps_magnitude = abs(median_within) >= abs(float(pooled_rho)) / 2

    result = {
        "burden_measure": burden_col,
        "pooled_spearman_rho": round(float(pooled_rho), 4),
        "pooled_p_value": float(f"{pooled_p:.4g}"),
        "within_population_strata": within,
        "median_within_stratum_rho": round(median_within, 4),
        "survives_stratification": bool(keeps_sign and keeps_magnitude),
    }

    logger.info(
        f"shared denominator check on {burden_col}: pooled rho "
        f"{result['pooled_spearman_rho']:+.4f}, median within stratum "
        f"{result['median_within_stratum_rho']:+.4f}, "
        f"survives: {result['survives_stratification']}"
    )

    return result

def _kruskal_across_tiers(merged: pd.DataFrame, burden_col: str) -> dict:
    """Kruskal Wallis on one burden column across the five county access tiers."""
    if burden_col not in merged.columns or "risk_tier" not in merged.columns:
        return {}

    groups = []
    tier_medians = {}
    for tier in COUNTY_TIER_ORDER:
        values = merged.loc[merged["risk_tier"] == tier, burden_col].dropna()
        if values.empty:
            continue
        groups.append(values)
        tier_medians[tier] = round(float(values.median()), 2)

    if len(groups) < 2:
        return {}

    statistic, p_value = scipy_stats.kruskal(*groups)

    result = {
        "test": "Kruskal Wallis",
        "burden_measure": burden_col,
        "statistic": round(float(statistic), 4),
        "p_value": float(f"{p_value:.4g}"),
        "n_tiers": len(groups),
        "median_by_tier": tier_medians,
    }

    logger.info(
        f"county tier test: Kruskal Wallis H {result['statistic']} "
        f"p {result['p_value']} across {result['n_tiers']} tiers"
    )
    logger.info(f"  median {burden_col} by tier: {tier_medians}")

    return result


def run_county_hrsa_validation(hrsa_raw: pd.DataFrame) -> dict:
    """
    Run the county grain validation and save its joined table.

    Parameters
    hrsa_raw : pd.DataFrame of raw HRSA rows with normalized column names.

    Returns
    dict of join report, correlations, and the tier test.
    """
    if not COUNTY_RISK_FILE.exists():
        logger.warning(f"county risk file not found: {COUNTY_RISK_FILE}, skipping county grain")
        return {}

    counties = pd.read_csv(COUNTY_RISK_FILE, dtype={"county_fips": str})
    hrsa_county = aggregate_hpsa_by_county(hrsa_raw)

    if hrsa_county is None:
        return {}

    merged, join_report = join_hpsa_to_counties(counties, hrsa_county)

    if join_report["join_match_rate"] < MIN_COUNTY_MATCH_RATE:
        logger.warning(
            f"county join match rate {join_report['join_match_rate']:.1%} is below "
            f"{MIN_COUNTY_MATCH_RATE:.0%}, reporting the join and stopping"
        )
        return {"join": join_report, "stopped": "match rate too low to interpret"}

    results = validate_county_tiers(merged)
    merged = add_burden_per_100k(merged, population_column=COUNTY_POPULATION_COLUMN)

    output_cols = [c for c in [
        "county_fips", "county_name", "practice_state", "risk_tier",
        "provider_count", "total_population", "providers_per_100k",
        "hrsa_hpsa_present", "hrsa_hpsa_count", "hrsa_shortage_pop",
        "hrsa_avg_score", "hrsa_fte_shortage",
        "hrsa_shortage_pop_per_100k", "hrsa_fte_shortage_per_100k",
        "hrsa_hpsa_count_per_100k",
    ] if c in merged.columns]

    save_csv(merged[output_cols], COUNTY_OUTPUT_FILE, logger)

    return {"join": join_report, **results}

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

        county_results = run_county_hrsa_validation(hrsa_raw)

        metadata = {
            "hrsa_source": HRSA_HPSA_URL,
            "hpsa_discipline_filter": HPSA_DISCIPLINE,
            "hpsa_status_filter": HPSA_ACTIVE_STATUS,
            "total_states": len(merged),
            "state_grain": metrics,
            "county_grain": county_results,
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
