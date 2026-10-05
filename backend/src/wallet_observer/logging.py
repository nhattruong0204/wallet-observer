"""Allowlisted structured logs: no request URLs, arbitrary messages, or tracebacks."""

import json
import logging
import sys
from datetime import UTC, datetime

EVENTS = {
    "migration_complete",
    "migration_failed",
    "service_starting",
    "service_stopped",
    "database_ready",
    "database_unavailable",
    "worker_failed",
    "configuration_invalid",
    "configuration_valid",
    "service_failed",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service):
        super().__init__()
        self.service = service

    def format(self, record):
        event = getattr(record, "event", "library_log")
        if not isinstance(event, str) or event not in EVENTS:
            event = "library_log"
        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "event": event,
        }
        if isinstance(getattr(record, "mode", None), str) and record.mode in {"fixture", "live"}:
            result["mode"] = record.mode
        # Only our configuration wrapper supplies this already-sanitized static diagnostic.
        if event == "configuration_invalid" and isinstance(
            getattr(record, "safe_configuration_error", None), str
        ):
            result["error"] = record.safe_configuration_error
        return json.dumps(result)


def configure_logging(service):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


def event(name, **fields):
    logging.getLogger("wallet_observer").info(name, extra={"event": name, **fields})
