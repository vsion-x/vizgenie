"""
Logging configuration for VizGenie
Python 3.12 compatible
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str     = "INFO",
    log_to_file: bool  = True,
    log_dir: str       = "logs",
) -> None:
    """
    Configure application-wide logging.

    Args:
        log_level:   Logging level (DEBUG / INFO / WARNING / ERROR)
        log_to_file: Whether to write logs to a file
        log_dir:     Directory for log files
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Root-logger configuration
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove existing handlers so we don't double-log
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ─────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # ── File handler ─────────────────────────────────────────────────────
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        log_filename = log_path / f"vizgenie_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_filename,
            maxBytes=10 * 1024 * 1024,   # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "aiohttp", "chromadb", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.info(f"Logging initialised — level={log_level}, file={log_to_file}")
