"""The add-in's log file."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# The package's import name: "fusion_export" standalone, prefixed by the
# add-in package when Fusion loads it.
PACKAGE = __package__

LOG_FILE = "fusion-export.log"
HANDLER_NAME = "fusion-export-file"
MAX_BYTES = 1_000_000
BACKUPS = 3


def configure_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Log the package to log_dir/LOG_FILE, rotating.

    Replaces the handler an earlier call attached, so add-in reloads don't
    stack handlers.
    """
    logger = logging.getLogger(PACKAGE)
    for handler in [h for h in logger.handlers if h.get_name() == HANDLER_NAME]:
        logger.removeHandler(handler)
        handler.close()
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
    )
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger
