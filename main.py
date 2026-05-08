from utils.logging_config import setup_logger

logger = setup_logger("ovara.pipeline")


def main():
    """
    Main pipeline runner for the INST737 final project.

    Each stage is modular and wrapped in error handling so major failures are
    logged clearly. Core stages stop the run when they fail, while optional
    stages log a warning and let the rest of the pipeline continue.
    """
    logger.info("starting Ovara pipeline...\n")

    # extract raw NPPES provider data
    try:
        logger.info("===== EXTRACT STAGE =====")
        from etl.extract import extract_nppes

        extract_nppes()
        logger.info("extract stage complete\n")
    except Exception as e:
        logger.error(f"extract stage failed: {e}")
        return

    # clean and standardize provider records
    try:
        logger.info("===== TRANSFORM STAGE =====")
        from etl.transform import transform_nppes

        transform_nppes()
        logger.info("transform stage complete\n")
    except Exception as e:
        logger.error(f"transform stage failed: {e}")
        return

    # run basic provider level EDA
    try:
        logger.info("===== EDA STAGE =====")
        from analysis.eda_provider import run_eda

        run_eda()
        logger.info("eda stage complete\n")
    except Exception as e:
        logger.error(f"eda stage failed: {e}")

    # build state level provider geography features
    try:
        logger.info("===== MODEL DATASET STAGE =====")
        from analysis.build_model_dataset import build_provider_geo_features

        build_provider_geo_features()
        logger.info("model dataset stage complete\n")
    except Exception as e:
        logger.error(f"model dataset stage failed: {e}")
        return

    # build metro population reference data
    try:
        logger.info("===== METRO REFERENCE STAGE =====")
        from analysis.build_metro_dataset import build_metro_dataset

        build_metro_dataset()
        logger.info("metro reference stage complete\n")
    except Exception as e:
        logger.error(f"metro reference stage failed: {e}")
        return

    # add demand side Census features when available
    try:
        logger.info("===== DEMAND FEATURES STAGE =====")
        from analysis.build_demand_features import build_demand_features

        build_demand_features()
        logger.info("demand features stage complete\n")
    except Exception as e:
        logger.warning(f"demand features stage failed but pipeline will continue: {e}")

    # build ZIP to county lookup for county level analysis
    try:
        logger.info("===== ZIP COUNTY CROSSWALK STAGE =====")
        from analysis.build_zip_county_crosswalk import build_zip_county_crosswalk

        build_zip_county_crosswalk()
        logger.info("ZIP county crosswalk stage complete\n")
    except Exception as e:
        logger.warning(f"ZIP county crosswalk stage failed but pipeline will continue: {e}")

    # build county population reference table
    try:
        logger.info("===== COUNTY POPULATION STAGE =====")
        from analysis.build_county_population import build_county_population

        build_county_population()
        logger.info("county population stage complete\n")
    except Exception as e:
        logger.warning(f"county population stage failed but pipeline will continue: {e}")

    # build county level access dataset
    try:
        logger.info("===== COUNTY DATASET STAGE =====")
        from analysis.build_county_dataset import build_county_dataset

        build_county_dataset()
        logger.info("county dataset stage complete\n")
    except Exception as e:
        logger.warning(f"county dataset stage failed but pipeline will continue: {e}")

    # classify county level access risk
    try:
        logger.info("===== COUNTY RISK CLASSIFICATION STAGE =====")
        from analysis.county_risk_classification import run_county_risk_classification

        run_county_risk_classification()
        logger.info("county risk classification stage complete\n")
    except Exception as e:
        logger.warning(f"county risk classification stage failed but pipeline will continue: {e}")

    # build final access model dataset
    try:
        logger.info("===== ACCESS MODEL STAGE =====")
        from analysis.build_access_model_dataset import build_access_model_dataset

        build_access_model_dataset()
        logger.info("access model stage complete\n")
    except Exception as e:
        logger.error(f"access model stage failed: {e}")
        return

    # train regression model and save model outputs
    try:
        logger.info("===== REGRESSION MODEL STAGE =====")
        from analysis.regression_model import run_regression_model

        run_regression_model()
        logger.info("regression model stage complete\n")
    except Exception as e:
        logger.error(f"regression model stage failed: {e}")
        return

    # evaluate model performance and validation metrics
    try:
        logger.info("===== EVALUATION STAGE =====")
        from analysis.evaluate import run_evaluation

        run_evaluation()
        logger.info("evaluation stage complete\n")
    except Exception as e:
        logger.error(f"evaluation stage failed: {e}")

    # convert model residuals into access risk tiers
    try:
        logger.info("===== ACCESS RISK STAGE =====")
        from analysis.access_risk_model import run_access_risk_model

        run_access_risk_model()
        logger.info("access risk stage complete\n")
    except Exception as e:
        logger.error(f"access risk stage failed: {e}")

    # compare Ovara risk outputs against HRSA shortage designations
    try:
        logger.info("===== HRSA VALIDATION STAGE =====")
        from analysis.hrsa_validation import run_hrsa_validation

        run_hrsa_validation()
        logger.info("HRSA validation stage complete\n")
    except Exception as e:
        logger.warning(f"HRSA validation stage failed but pipeline will continue: {e}")

    # cluster states into provider supply groups
    try:
        logger.info("===== CLUSTERING STAGE =====")
        from analysis.clustering_model import run_clustering_model

        run_clustering_model()
        logger.info("clustering stage complete\n")
    except Exception as e:
        logger.warning(f"clustering stage failed but pipeline will continue: {e}")

    # export static charts and optionally launch the dashboard
    try:
        logger.info("===== INTERACTIVE VISUALIZATION STAGE =====")
        from vis.interactive_visualizations import run_interactive_visualizations

        run_interactive_visualizations()
        logger.info("interactive visualization stage complete\n")
    except Exception as e:
        logger.error(f"interactive visualization stage failed: {e}")

    logger.info("Ovara pipeline finished")


if __name__ == "__main__":
    main()