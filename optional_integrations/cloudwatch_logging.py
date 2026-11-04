"""Optional CloudWatch log shipping. Requires the optional AWS requirements."""

import logging
import os
import socket

from app.core.logging import JSONFormatter


def attach_cloudwatch_handler(
    log_group: str, region_name: str, boto3_client=None
) -> logging.Logger:
    import boto3
    from watchtower import CloudWatchLogHandler

    logger = logging.getLogger()
    if any(
        type(handler).__name__ == "CloudWatchLogHandler" for handler in logger.handlers
    ):
        return logger
    client = boto3_client or boto3.client("logs", region_name=region_name)
    handler = CloudWatchLogHandler(
        log_group_name=log_group,
        log_stream_name=f"{socket.gethostname()}-{os.getpid()}",
        boto3_client=client,
        create_log_group=True,
        create_log_stream=True,
    )
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger
