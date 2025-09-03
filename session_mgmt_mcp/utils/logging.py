#!/usr/bin/env python3
"""Structured logging utilities for session management."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path


class SessionLogger:
    """Structured logging for session management with context."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (
            log_dir / f"session_management_{datetime.now().strftime('%Y%m%d')}.log"
        )

        # Configure logger
        self.logger = logging.getLogger("session_management")
        self.logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if not self.logger.handlers:
            # File handler with structured format
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(logging.INFO)

            # Console handler for errors
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.ERROR)

            # Structured formatter
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def info(self, message: str, **context) -> None:
        """Log info with optional context."""
        if context:
            message = f"{message} | Context: {json.dumps(context)}"
        self.logger.info(message)

    def warning(self, message: str, **context) -> None:
        """Log warning with optional context."""
        if context:
            message = f"{message} | Context: {json.dumps(context)}"
        self.logger.warning(message)

    def error(self, message: str, **context) -> None:
        """Log error with optional context."""
        if context:
            message = f"{message} | Context: {json.dumps(context)}"
        self.logger.error(message)

    def debug(self, message: str, **context) -> None:
        """Log debug with optional context."""
        if context:
            message = f"{message} | Context: {json.dumps(context)}"
        self.logger.debug(message)


def get_session_logger() -> SessionLogger:
    """Get the global session logger instance."""
    claude_dir = Path.home() / ".claude"
    return SessionLogger(claude_dir / "logs")
