from utils.logging_config import setup_logger

logger = setup_logger("ovara.pipeline")


def main():
    """
    Main pipeline runner for INST737 final project.
    Each stage is modular and wrapped in error handling
    so failures are logged without killing the full run.
    """
    logger.info("starting Ovara pipeline...\n")

    # extract 

    try:
        logger.info("===== EXTRACT STAGE =====")
        from etl.extract import extract_nppes
        extract_nppes()
        logger.info("extract stage complete\n")
    except Exception as e:
        logger.error(f"extract stage failed: {e}")
        return

    # transform 

    try:
        logger.info("===== TRANSFORM STAGE =====")
        from etl.transform import transform_nppes
        transform_nppes()
        logger.info("transform stage complete\n")
    except Exception as e:
        logger.error(f"transform stage failed: {e}")
        return

    # eda

    try:
        logger.info("===== EDA STAGE =====")
        from analysis.eda_provider import run_eda
        run_eda()
        logger.info("eda stage complete\n")
    except Exception as e:
        logger.error(f"eda stage failed: {e}")

    # model dataset

    try:
        logger.info("===== MODEL DATASET STAGE =====")
        from analysis.build_model_dataset import build_provider_geo_features
        build_provider_geo_features()
        logger.info("model dataset stage complete\n")
    except Exception as e:
        logger.error(f"model dataset stage failed: {e}")
        return

    # metro reference 

    try:
        logger.info("===== METRO REFERENCE STAGE =====")
        from analysis.build_metro_dataset import build_metro_dataset
        build_metro_dataset()
        logger.info("metro reference stage complete\n")
    except Exception as e:
        logger.error(f"metro reference stage failed: {e}")
        return

    # demand features

    try:
        logger.info("===== DEMAND FEATURES STAGE =====")
        from analysis.build_demand_features import build_demand_features
        build_demand_features()
        logger.info("demand features stage complete\n")
    except Exception as e:
        logger.warning(f"demand features stage failed (non-critical): {e}")

    # access model 

    try:
        logger.info("===== ACCESS MODEL STAGE =====")
        from analysis.build_access_model_dataset import build_access_model_dataset
        build_access_model_dataset()
        logger.info("access model stage complete\n")
    except Exception as e:
        logger.error(f"access model stage failed: {e}")
        return

    # regression model 

    try:
        logger.info("===== REGRESSION MODEL STAGE =====")
        from analysis.regression_model import run_regression_model
        run_regression_model()
        logger.info("regression model stage complete\n")
    except Exception as e:
        logger.error(f"regression model stage failed: {e}")
        return

    # evaluation 

    try:
        logger.info("===== EVALUATION STAGE =====")
        from analysis.evaluate import run_evaluation
        run_evaluation()
        logger.info("evaluation stage complete\n")
    except Exception as e:
        logger.error(f"evaluation stage failed: {e}")

    # access risk

    try:
        logger.info("===== ACCESS RISK STAGE =====")
        from analysis.access_risk_model import run_access_risk_model
        run_access_risk_model()
        logger.info("access risk stage complete\n")
    except Exception as e:
        logger.error(f"access risk stage failed: {e}")

    # clustering

    try:
        logger.info("===== CLUSTERING STAGE =====")
        from analysis.clustering_model import run_clustering_model
        run_clustering_model()
        logger.info("clustering stage complete\n")
    except Exception as e:
        logger.warning(f"clustering stage failed (non-critical): {e}")

    # interactive visualizations

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