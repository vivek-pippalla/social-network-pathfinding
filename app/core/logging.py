import contextvars
import datetime
import json
import logging

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for key in ("method", "route", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def setup_logging() -> logging.Logger:
    import sys

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = next(
        (
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        root.addHandler(handler)
    handler.setFormatter(JSONFormatter())
    return root
