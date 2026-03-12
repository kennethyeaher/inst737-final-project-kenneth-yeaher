from etl.extract import extract_nppes
from etl.transform import transform_nppes


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


if __name__ == "__main__":
    main()