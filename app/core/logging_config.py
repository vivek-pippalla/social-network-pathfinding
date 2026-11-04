"""Compatibility imports for code not yet migrated to ``app.core.logging``."""

from app.core.logging import JSONFormatter, setup_logging

__all__ = ["JSONFormatter", "setup_logging"]
