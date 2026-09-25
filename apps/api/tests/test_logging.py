"""Logging foundation: configuration initializes, the app starts, errors stay safe (Task 2.3)."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from app.logging_config import LOG_FORMAT, configure_logging
from app.main import app, lifespan


def test_configure_logging_returns_a_usable_logger() -> None:
    """Configuration succeeds, sets the level, and hands back a named logger."""
    logger = configure_logging("WARNING")

    try:
        assert logger.name == "agentschat"
        assert logger.getEffectiveLevel() == logging.WARNING
        assert logging.getLogger().level == logging.WARNING
    finally:
        configure_logging("INFO")


def test_log_format_carries_timestamp_level_and_logger_name() -> None:
    """The single central format records when, how severe, and from where."""
    assert "%(asctime)s" in LOG_FORMAT
    assert "%(levelname)s" in LOG_FORMAT
    assert "%(name)s" in LOG_FORMAT

    rendered = logging.Formatter(LOG_FORMAT).format(
        logging.LogRecord(
            name="agentschat",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="startup probe",
            args=(),
            exc_info=None,
        )
    )

    assert "agentschat" in rendered
    assert "ERROR" in rendered
    assert "startup probe" in rendered


def test_app_starts_with_logging_enabled() -> None:
    """The application (logging configured at import) starts and serves."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_lifespan_logs_startup_and_shutdown(caplog: pytest.LogCaptureFixture) -> None:
    """Startup and shutdown boundaries are observable in logs."""
    caplog.set_level(logging.INFO, logger="agentschat")

    asyncio.run(_exercise_lifespan())

    messages = [record.message for record in caplog.records]
    assert any("starting" in message for message in messages)
    assert any("shutting down" in message for message in messages)


async def _exercise_lifespan() -> None:
    """Run the lifespan once so its boundary logs are captured."""
    async with lifespan(app):
        pass
