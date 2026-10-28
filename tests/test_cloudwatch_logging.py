"""
Unit tests for CloudWatch logging and structured JSON formatting.

Verifies:
  - JSON formatting and required metadata fields.
  - Disabled state: stdout only, no CloudWatch calls.
  - Enabled state: attaches CloudWatch handler with mock client.
  - Idempotency: duplicate handler prevention.
  - Fail-safe: errors connecting to CloudWatch do not crash application.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from watchtower import CloudWatchLogHandler

from app.core.logging_config import JSONFormatter, setup_logging


def test_json_formatter_output():
    """Verify JSONFormatter creates valid JSON with expected fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=25,
        msg="Test message: %s",
        args=("sample",),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test message: sample"
    assert "timestamp" in parsed
    assert "module" in parsed
    assert "function" in parsed


def test_setup_logging_disabled():
    """When CloudWatch is disabled, only StreamHandler (stdout) should be present."""
    logger = setup_logging(cloudwatch_enabled=False)

    cw_handlers = [h for h in logger.handlers if isinstance(h, CloudWatchLogHandler)]
    assert len(cw_handlers) == 0


def test_setup_logging_enabled_with_mock_client():
    """When CloudWatch is enabled, attaches CloudWatchLogHandler without errors."""
    mock_logs_client = MagicMock()

    # Clear any existing CW handlers from root logger before test
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, CloudWatchLogHandler)]

    logger = setup_logging(
        cloudwatch_enabled=True,
        log_group="/test/group",
        region_name="ap-south-1",
        boto3_client=mock_logs_client,
    )

    cw_handlers = [h for h in logger.handlers if isinstance(h, CloudWatchLogHandler)]
    assert len(cw_handlers) == 1

    # Cleanup after test
    for h in cw_handlers:
        logger.removeHandler(h)


def test_setup_logging_idempotent_no_duplicate_handlers():
    """Calling setup_logging repeatedly should not duplicate handlers."""
    mock_logs_client = MagicMock()

    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, CloudWatchLogHandler)]

    setup_logging(
        cloudwatch_enabled=True,
        log_group="/test/group",
        region_name="ap-south-1",
        boto3_client=mock_logs_client,
    )
    # Second invocation
    setup_logging(
        cloudwatch_enabled=True,
        log_group="/test/group",
        region_name="ap-south-1",
        boto3_client=mock_logs_client,
    )

    cw_handlers = [h for h in root.handlers if isinstance(h, CloudWatchLogHandler)]
    assert len(cw_handlers) == 1

    # Cleanup
    for h in cw_handlers:
        root.removeHandler(h)


@patch("watchtower.CloudWatchLogHandler", side_effect=Exception("AWS Logs Connection Refused"))
def test_setup_logging_failsafe_does_not_crash(mock_cw_handler):
    """If CloudWatch initialization fails, setup_logging catches it and falls back to stdout."""
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, CloudWatchLogHandler)]

    # Must not raise an exception
    logger = setup_logging(cloudwatch_enabled=True, log_group="/test/group")
    assert logger is not None
