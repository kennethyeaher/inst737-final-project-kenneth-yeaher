import logging
from pathlib import Path

# log output file

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "ovara_pipeline.log"


def setup_logger(name: str = "ovara") -> logging.Logger:
    """configure and return the pipeline logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    # avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # console handler shows info and above
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    # file handler captures everything
    file_handler = logging.FileHandler(LOG_FILE, mode="a")
    file_handler.setLevel(logging.DEBUG)

    # format
    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(fmt)
    file_handler.setFormatter(fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger