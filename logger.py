"""
Central logging setup for DataQC.

Gives the terminal a readable, colour-coded stream so an operator can follow
what the service is doing without reading the source:

    13:05:12 | INFO  | api       | -> POST /DataQC_real
    13:05:12 | WARN  | realtime  | 3 alert(s) raised for depth 1035.0
    13:05:12 | INFO  | api       | <- POST /DataQC_real  200  12.4ms

Configured entirely through environment variables so the same image behaves
differently per machine without a rebuild:

    LOG_LEVEL      DEBUG | INFO | WARNING | ERROR      (default INFO)
    LOG_COLOR      auto | always | never               (default auto)

Logs go to the terminal only - nothing is written to disk. Under Docker the
terminal stream is what `docker compose logs` shows.
"""

from __future__ import annotations

import logging
import os
import sys

# --------------------------------------------------------------------------
# Colour handling
# --------------------------------------------------------------------------

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"

LEVEL_COLOR = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;41m",  # white on red
}

# Short, fixed-width level names keep the columns aligned in the terminal.
LEVEL_SHORT = {
    "DEBUG": "DEBUG",
    "INFO": "INFO ",
    "WARNING": "WARN ",
    "ERROR": "ERROR",
    "CRITICAL": "CRIT ",
}


# "dataqc.api" collapses to "api"; uvicorn's own loggers get readable names
# instead of the misleading "error" / "access" tail of their dotted paths.
SHORT_NAME = {
    "uvicorn": "uvicorn",
    "uvicorn.error": "uvicorn",
    "uvicorn.access": "http",
}


def _color_enabled() -> bool:
    mode = os.getenv("LOG_COLOR", "auto").strip().lower()

    if mode == "always":
        return True

    if mode == "never":
        return False

    # "auto": honour the NO_COLOR convention, otherwise colour only a real TTY.
    if os.getenv("NO_COLOR"):
        return False

    return sys.stderr.isatty()


class ConsoleFormatter(logging.Formatter):
    """Aligned, optionally coloured single-line records for the terminal."""

    def __init__(self, use_color: bool):
        super().__init__(datefmt="%H:%M:%S")
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        level = LEVEL_SHORT.get(record.levelname, record.levelname[:5].ljust(5))
        name = SHORT_NAME.get(record.name) or record.name.split(".")[-1]
        name = name[:9].ljust(9)
        message = record.getMessage()

        if self.use_color:
            color = LEVEL_COLOR.get(record.levelname, "")
            level = f"{color}{level}{RESET}"
            name = f"{DIM}{name}{RESET}"
            timestamp = f"{DIM}{self.formatTime(record, self.datefmt)}{RESET}"
            sep = f"{DIM}|{RESET}"
        else:
            timestamp = self.formatTime(record, self.datefmt)
            sep = "|"

        line = f"{timestamp} {sep} {level} {sep} {name} {sep} {message}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

_CONFIGURED = False


def setup_logging() -> logging.Logger:
    """
    Install the console handler on the root logger.

    Safe to call more than once; only the first call does the work.
    """
    global _CONFIGURED

    root = logging.getLogger()

    if _CONFIGURED:
        return logging.getLogger("dataqc")

    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root.setLevel(level)

    # Drop anything a library (or a previous call) already attached, so we
    # never emit a record twice.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(ConsoleFormatter(use_color=_color_enabled()))
    console.setLevel(level)
    root.addHandler(console)

    # uvicorn ships its own handlers; strip them so its output flows through
    # ours and every line in the terminal looks the same.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # We log our own request lines with timings; uvicorn's would duplicate them.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True

    return logging.getLogger("dataqc")


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger, e.g. get_logger("api")."""
    return logging.getLogger(f"dataqc.{name}")


def banner(lines: list[str]) -> None:
    """Print a boxed block of startup facts so config is obvious at a glance."""
    log = logging.getLogger("dataqc.startup")

    width = max((len(line) for line in lines), default=0)

    log.info("+-%s-+", "-" * width)

    for line in lines:
        log.info("| %s |", line.ljust(width))

    log.info("+-%s-+", "-" * width)
