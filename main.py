"""
Ovara pipeline runner.

Lists every stage in execution order with a critical flag and hands the
sequence off to run_pipeline. Critical stages abort the run on failure so
downstream stages do not see stale or missing inputs. Non critical stages
log a warning and let the pipeline keep going.

Usage
    python main.py
"""

from __future__ import annotations

from utils.logging_config import setup_logger
from utils.pipeline import Stage, run_pipeline

logger = setup_logger("ovara.pipeline")


def _build_stages() -> list[Stage]:
    """
    Build the ordered list of pipeline stages.

    Imports happen lazily inside this function so a stage that fails to
    import does not crash the whole pipeline before logging starts.

    Returns
    list[Stage] in execution order.
    """
    # imports live inside the function so a missing dependency in one stage
    # does not break the whole module load
    from analysis.access_risk_model import run_access_risk_model
    from analysis.build_access_model_dataset import build_access_model_dataset
    from analysis.build_county_dataset import build_county_dataset
    from analysis.build_county_population import build_county_population
    from analysis.build_demand_features import build_demand_features
    from analysis.build_metro_dataset import build_metro_dataset
    from analysis.build_model_dataset import build_provider_geo_features
    from analysis.build_zip_county_crosswalk import build_zip_county_crosswalk
    from analysis.clustering_model import run_clustering_model
    from analysis.county_risk_classification import run_county_risk_classification
    from analysis.eda_provider import run_eda
    from analysis.evaluate import run_evaluation
    from analysis.hrsa_validation import run_hrsa_validation
    from analysis.regression_model import run_regression_model
    from etl.extract import extract_nppes
    from etl.transform import transform_nppes
    from vis.interactive_visualizations import run_interactive_visualizations

    return [
        # extract and transform supply the cleaned provider table that
        # everything else depends on, so they are critical
        Stage("EXTRACT", extract_nppes, critical=True),
        Stage("TRANSFORM", transform_nppes, critical=True),

        # eda is just charts, safe to skip on failure
        Stage("EDA", run_eda, critical=False),

        # state level model dataset and metro reference are required by
        # the regression stage, so they must succeed
        Stage("MODEL DATASET", build_provider_geo_features, critical=True),
        Stage("METRO REFERENCE", build_metro_dataset, critical=True),

        # demand features and county work are reference data that downstream
        # stages can run without if they have to (warn and continue)
        Stage("DEMAND FEATURES", build_demand_features, critical=False),
        Stage("ZIP-COUNTY CROSSWALK", build_zip_county_crosswalk, critical=False),
        Stage("COUNTY POPULATION", build_county_population, critical=False),
        Stage("COUNTY DATASET", build_county_dataset, critical=False),
        Stage("COUNTY RISK CLASSIFICATION", run_county_risk_classification, critical=False),

        # access model and regression are the heart of the project, must succeed
        Stage("ACCESS MODEL", build_access_model_dataset, critical=True),
        Stage("REGRESSION MODEL", run_regression_model, critical=True),

        # evaluation, access risk, hrsa validation, and clustering are
        # diagnostic outputs. Failing any of these should not block the dashboard
        Stage("EVALUATION", run_evaluation, critical=False),
        Stage("ACCESS RISK", run_access_risk_model, critical=False),
        Stage("HRSA VALIDATION", run_hrsa_validation, critical=False),
        Stage("CLUSTERING", run_clustering_model, critical=False),

        # interactive visualizations writes static html and optionally
        # launches the dashboard. Soft fail so a chart bug does not look
        # like a pipeline failure
        Stage("INTERACTIVE VISUALIZATION", run_interactive_visualizations, critical=False),
    ]


def main() -> None:
    """Run the full Ovara pipeline from extract through dashboard exports."""
    logger.info("starting Ovara pipeline...\n")
    run_pipeline(_build_stages(), logger)
    logger.info("Ovara pipeline finished")


if __name__ == "__main__":
    main()
