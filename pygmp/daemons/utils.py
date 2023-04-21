from __future__ import annotations
from pathlib import Path
import logging
import logging.config
import inspect
import pygmp


def get_logger(name: str) -> logging.Logger:
    """Assures that the logger is configured."""
    logging.config.fileConfig(fname=Path(inspect.getfile(pygmp)).parent.joinpath("log_config.ini"))
    return logging.getLogger(name)

