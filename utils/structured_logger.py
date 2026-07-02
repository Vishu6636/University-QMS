import logging
import json
from datetime import datetime, timezone

# Use standard logger for structured JSON events
logger = logging.getLogger("uqms_structured")

# Ensure it outputs cleanly to stdout
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Prevent propagation to the root logger to avoid double logging
    logger.propagate = False

def log_event(event_name: str, **kwargs) -> None:
    """Log a structured JSON event to stdout."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_name,
        **kwargs
    }
    logger.info(json.dumps(payload))
