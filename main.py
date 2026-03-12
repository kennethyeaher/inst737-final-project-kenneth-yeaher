"""
INST737 Final Project
Main pipeline runner.

This script acts as the single entry point for the full data science workflow.
Right now we are only executing the EXTRACT stage, but this will later expand
to include transform, modeling, valuation, and visualization.
"""

from etl.extract import extract_nppes


def run_extract_stage():
    """
    Runs the NPPES extraction step.

    This loads the raw CMS NPPES provider dataset,
    selects only the columns needed for downstream modeling,
    and saves a standardized raw file into the project data directory.
    """
    print("\n[PIPELINE] ===== EXTRACT STAGE START =====")
    extract_nppes()
    print("[PIPELINE] ===== EXTRACT STAGE COMPLETE =====\n")


def main():
    """
    Main orchestrator for the final project pipeline.

    The goal is to keep this file very readable and modular so that
    each pipeline stage can be turned on/off easily as the project evolves.
    """
    print("[PIPELINE] Starting INST737 Final Project Workflow...")

    run_extract_stage()

    print("[PIPELINE] Workflow finished successfully.")


if __name__ == "__main__":
    main()