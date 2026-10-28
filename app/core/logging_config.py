"""
Structured Logging Configuration with CloudWatch Integration.

Features:
  - Formats all logs as single-line JSON with level, message, module, and timestamps.
  - Preserves stdout stream logging for local development, Docker, and container log drivers.
  - Conditionally attaches CloudWatch Logs handler (via watchtower) when CLOUDWATCH_ENABLED=True.
  - Idempotent: checks for existing handlers to prevent duplicate log events.
  - Fail-safe: CloudWatch connection errors are reported to stdout without crashing the app.
"""

import datetime
import json
import logging
import os
import socket
import sys
from typing import Optional

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON — easy to parse by any log collector."""

    def format(self, record: logging.LogRecord) -> str:
        log_object = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_object)


def _has_cloudwatch_handler(logger: logging.Logger) -> bool:
    """Check if a CloudWatchLogHandler is already attached to prevent duplicates."""
    return any(type(h).__name__ == "CloudWatchLogHandler" for h in logger.handlers)


def setup_logging(
    cloudwatch_enabled: Optional[bool] = None,
    log_group: Optional[str] = None,
    region_name: Optional[str] = None,
    boto3_client: Optional[object] = None,
) -> logging.Logger:
    """
    Configure application-wide logging.
    Always configures stdout JSON logging.
    Optionally attaches CloudWatch log shipping when enabled.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 1. Configure stdout handler (preserve single handler to prevent duplicates)
    stdout_handler = None
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler) and h.stream == sys.stdout:
            stdout_handler = h
            break

    if not stdout_handler:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(stdout_handler)
    else:
        stdout_handler.setFormatter(JSONFormatter())

    # 2. Attach CloudWatch Handler if enabled
    is_cw_enabled = (
        cloudwatch_enabled
        if cloudwatch_enabled is not None
        else settings.CLOUDWATCH_ENABLED
    )

    if is_cw_enabled:
        if _has_cloudwatch_handler(root_logger):
            root_logger.info("CloudWatch log handler already attached; skipping.")
            return root_logger

        group = log_group or settings.CLOUDWATCH_LOG_GROUP
        region = region_name or settings.AWS_REGION
        stream_name = f"{socket.gethostname()}-{os.getpid()}"

        try:
            import boto3
            from watchtower import CloudWatchLogHandler

            cw_client = boto3_client or boto3.client("logs", region_name=region)

            cw_handler = CloudWatchLogHandler(
                log_group_name=group,
                log_stream_name=stream_name,
                boto3_client=cw_client,
                create_log_group=True,
                create_log_stream=True,
            )
            cw_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(cw_handler)
            root_logger.info(
                f"CloudWatch logging enabled | group='{group}' | stream='{stream_name}'"
            )
        except Exception as e:
            # Must not crash application if CloudWatch fails
            root_logger.error(
                f"Failed to initialize CloudWatch log handler: {e}. Falling back to stdout only."
            )

    return root_logger
