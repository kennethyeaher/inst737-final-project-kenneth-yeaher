"""
Static HTML exports for the dashboard charts.

The pipeline always writes a small set of standalone HTML files alongside
the live dashboard so the figures can be viewed without booting the Dash
server (handy for the README and for sharing with collaborators).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from vis.state_charts import build_bar, build_choropleth, build_scatter


# default folder for static html exports
DEFAULT_OUTPUT_DIR = Path("data/visualizations")


def write_html(
    fig: go.Figure,
    filename: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    logger: logging.Logger | None = None,
) -> None:
    """
    Save one Plotly figure as a standalone HTML file.

    Uses the plotly cdn so the output stays small (no embedded plotly.js).

    Parameters
    fig : plotly Figure to write.
    filename : str
        Filename relative to output_dir, including the .html extension.
    output_dir : Path
        Folder for static exports. Created if missing.
    logger : logging.Logger or None
        Optional logger that receives one info line per save.

    Returns
    None
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_dir / filename, include_plotlyjs="cdn")
    if logger is not None:
        logger.info(f"saved -> {filename}")


def write_state_exports(
    df: pd.DataFrame,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    logger: logging.Logger | None = None,
) -> None:
    """
    Write the four state level static html exports.

    Files produced:
    - underserved_bar_chart.html
    - predicted_vs_actual_scatter.html
    - access_gap_choropleth.html
    - risk_tier_choropleth.html

    Parameters
    df : pd.DataFrame from load_regression_results.
    output_dir : Path for the html files.
    logger : optional logger.

    Returns
    None
    """
    write_html(build_bar(df), "underserved_bar_chart.html",
               output_dir=output_dir, logger=logger)
    write_html(build_scatter(df), "predicted_vs_actual_scatter.html",
               output_dir=output_dir, logger=logger)
    write_html(build_choropleth(df), "access_gap_choropleth.html",
               output_dir=output_dir, logger=logger)
    write_html(build_choropleth(df, view_mode="tier"), "risk_tier_choropleth.html",
               output_dir=output_dir, logger=logger)
