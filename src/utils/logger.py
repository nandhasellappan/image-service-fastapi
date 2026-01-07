import logging
import os
import sys
from config import settings

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "TRACE": logging.DEBUG,
}

# Keep whatever is assigned in env; fallback to INFO only if nothing is set.
_level_str = os.getenv("LOG_LEVEL")
_level = _LEVELS.get((_level_str or "INFO").strip().upper(), logging.INFO)

_root = logging.getLogger()
_root.setLevel(_level)

if _root.handlers:
    for h in _root.handlers:
        h.setLevel(_level)
else:
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(_level)
    _root.addHandler(h)

def get_logger(name: str) -> logging.LoggerAdapter:
    base = logging.getLogger(name)
    return logging.LoggerAdapter(
        base, {"service": settings.app_name, "environment": settings.environment}
    )
