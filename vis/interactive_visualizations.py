"""
Interactive visualization workflow.

Thin orchestrator that pulls the chart builders, summary text, dashboard
layout, and static html exports together. Each piece lives in its own
module under vis/. This file keeps the public entry point that main.py
imports (run_interactive_visualizations) plus the script entry point
that launches the dashboard directly.

Behavior
- Always writes the four static html files to data/visualizations.
- Only launches the live Dash server when explicitly asked, so
  python main.py finishes cleanly instead of blocking on the server.

Run modes
- python main.py                                  static exports only
- OVARA_LAUNCH_DASHBOARD=1 python main.py         exports plus live dashboard
- python vis/interactive_visualizations.py        exports plus live dashboard
"""

from __future__ import annotations

import os
import warnings as _warnings

# hide the LibreSSL warning that fires before we even reach a real network call
_warnings.filterwarnings("ignore", message=".*LibreSSL.*")

from utils.logging_config import setup_logger
from vis.dashboard import run_dashboard
from vis.exports import write_state_exports
from vis.state_charts import INPUT_FILE, load_regression_results

logger = setup_logger("ovara.visualizations")

__all__ = ["run_interactive_visualizations"]


def _wants_live_dashboard(launch_dashboard: bool | None) -> bool:
    """Resolve whether to boot the Dash server based on the explicit flag or env var."""
    if launch_dashboard is not None:
        return launch_dashboard
    return os.environ.get("OVARA_LAUNCH_DASHBOARD", "").lower() in ("1", "true", "yes")


def run_interactive_visualizations(launch_dashboard: bool | None = None) -> None:
    """
    Run the full visualization workflow.

    Always writes static html exports. Optionally launches the live Dash
    server when launch_dashboard is True (or the OVARA_LAUNCH_DASHBOARD
    env var is set).

    Parameters
    launch_dashboard : bool or None
        Force the live server on or off. None defers to the env var.

    Returns
    None
    """
    try:
        df = load_regression_results()
        dropped = df.attrs.get("dropped_rows", 0)
        if dropped:
            logger.warning(f"dropped {dropped} rows with missing required values")
        logger.info(f"rows available: {df.shape[0]}")

        # static exports always run so the html files stay in sync with the data
        write_state_exports(df, logger=logger)
        logger.info("static exports complete")

        if _wants_live_dashboard(launch_dashboard):
            run_dashboard(df, debug=False, logger=logger)
        else:
            logger.info(
                "skipping dashboard launch "
                "(set OVARA_LAUNCH_DASHBOARD=1 or run "
                "`python vis/interactive_visualizations.py` to start it)"
            )

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during visualization: {e}")
        raise


if __name__ == "__main__":
    run_interactive_visualizations(launch_dashboard=True)
