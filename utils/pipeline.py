"""
Pipeline staging primitives.

The Ovara pipeline runs about fifteen sequential stages. Each stage has the
same shape (log a header, run a function, catch errors, decide whether to
abort or continue). This module provides a Stage dataclass and a runner so
main.py can describe the pipeline as a list instead of a long stack of
try and except blocks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Stage:
    """
    One executable step in the pipeline.

    Fields
    name : str
        Display name shown in the stage header banner.
    runner : Callable
        Zero argument function that performs the work. Usually the
        run_X function exported by an analysis or etl module.
    critical : bool
        If True, a failure aborts the rest of the pipeline (data needed
        downstream). If False, the failure is logged as a warning and
        the pipeline continues to the next stage.
    """

    name: str
    runner: Callable[[], Any]
    critical: bool = True


def run_stage(stage: Stage, logger: logging.Logger) -> bool:
    """
    Execute a single pipeline stage with consistent logging and error handling.

    Parameters
    stage : Stage
        Stage to run.
    logger : logging.Logger
        Logger that receives the banner line, completion line, and any
        error or warning if the stage fails.

    Returns
    bool: True on success or non critical failure, False if a critical
    stage failed and the caller should abort the pipeline.
    """
    logger.info(f"===== {stage.name} STAGE =====")
    try:
        stage.runner()
        logger.info(f"{stage.name.lower()} stage complete\n")
        return True

    except Exception as e:
        if stage.critical:
            logger.error(f"{stage.name.lower()} stage failed: {e}")
            return False

        # non critical stages just log a warning and let the pipeline continue
        logger.warning(f"{stage.name.lower()} stage failed (non critical): {e}")
        return True


def run_pipeline(stages: list[Stage], logger: logging.Logger) -> None:
    """
    Run a sequence of pipeline stages in order, stopping on the first
    critical failure.

    Parameters
    stages : list[Stage]
        Stages to run in order.
    logger : logging.Logger
        Shared pipeline logger.

    Returns
    None
    """
    for stage in stages:
        if not run_stage(stage, logger):
            # critical failure, abort early so we do not run downstream stages
            # against stale or missing inputs
            return
