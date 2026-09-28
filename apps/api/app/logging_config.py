"""Centralized logging configuration for the FastAPI application.

Uses Python's standard ``logging`` module only — no external service, no custom
framework (Task 2.3). One place configures the root logger with readable
local-development output: timestamps, level, logger name, and message.

Sensitive information must never reach a log call: no passwords, tokens, API
keys, secrets, cookies, authorization headers, full request bodies, user
private data, environment values, or database credentials. Unexpected failures
log only the exception type — never its message, traceback, or request data.
"""

from __future__ import annotations

import logging
from typing import Final

#: Readable local-development format: timestamp, level, logger name, message.
#: The format itself is an explicit requirement — log records carry their own
#: timestamp and origin without a custom framework.
LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: int | str = logging.INFO) -> logging.Logger:
    """Configure the root logger once and return the shared logger.

    Existing handlers keep their formatters. ``logging.basicConfig`` adds a
    handler only when none exists, so set the root level separately as well.
    Returns the ``agentschat`` logger so call sites share one origin name.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT, force=False)
    logging.getLogger().setLevel(level)
    logger = logging.getLogger("agentschat")
    logger.setLevel(level)
    return logger


logger: Final[logging.Logger] = logging.getLogger("agentschat")
