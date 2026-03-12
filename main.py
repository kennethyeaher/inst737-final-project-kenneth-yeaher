from etl.extract import extract_nppes
from etl.transform import transform_nppes
from analysis.eda_provider import run_eda

def main():
    """
    Main pipeline runner for INST737 final project.
    Each stage is modular so we can expand into modeling + visualization later.
    """

    print("[PIPELINE] Starting INST737 Final Project Workflow...\n")

    print("[PIPELINE] ===== EXTRACT STAGE START =====")
    extract_nppes()
    print("[PIPELINE] ===== EXTRACT STAGE COMPLETE =====\n")

    print("[PIPELINE] ===== TRANSFORM STAGE START =====")
    transform_nppes()
    print("[PIPELINE] ===== TRANSFORM STAGE COMPLETE =====\n")

    print("[PIPELINE] Workflow finished successfully.")

    print("[PIPELINE] ===== EDA STAGE START =====")
    run_eda()
    print("[PIPELINE] ===== EDA STAGE COMPLETE =====\n")


if __name__ == "__main__":
    main()