"""Persistent, rotating log for field diagnostics.

The detector runs classical computer vision with no network and no account, so
when a cut goes wrong on a customer machine the only evidence is whatever the
process wrote down. This module gives the app one rotating log file, kept small
and free of image data, that the diagnostic package can carry back for support.

Configuration is optional and must never stop the app from running: if the log
file cannot be created the app keeps working and simply has no log to attach.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "lalikul.cutprep"
LOG_FILENAME = "detection.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5

_log_path: Path | None = None

# Library idiom: a NullHandler keeps the logger quiet (no "lastResort" stderr
# dump) until the app attaches the rotating file handler via configure_logging.
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())


def _default_log_dir() -> Path:
    """Per-user, writable log directory following each platform's convention."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Lalikul" / "CutPrep" / "logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "Lalikul" / "CutPrep"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "Lalikul" / "CutPrep" / "logs"


def configure_logging(log_dir: str | Path | None = None) -> Path | None:
    """Attach a rotating file handler to the app logger. Idempotent.

    Returns the active log file path, or ``None`` if the log file could not be
    created. Repeated calls for the same destination keep the existing handler;
    a different destination replaces it so handlers never stack.
    """
    global _log_path
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    directory = Path(log_dir) if log_dir is not None else _default_log_dir()
    target = directory / LOG_FILENAME
    if _log_path == target and any(
        isinstance(h, RotatingFileHandler) for h in logger.handlers
    ):
        return _log_path
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            target, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
    except OSError:
        return None
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    for existing in [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]:
        logger.removeHandler(existing)
        existing.close()
    logger.addHandler(handler)
    _log_path = target
    return target


def get_logger() -> logging.Logger:
    """The app logger. Safe to use before :func:`configure_logging`."""
    return logging.getLogger(LOGGER_NAME)


def log_file_path() -> Path | None:
    """The active log file, or ``None`` when logging is not configured."""
    return _log_path
