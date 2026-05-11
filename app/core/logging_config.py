import logging
import json
import sys


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON — easy to parse by any log collector."""

    def format(self, record: logging.LogRecord) -> str:
        log_object = {
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_object)


def setup_logging() -> None:
    """Call once at application startup to configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]
