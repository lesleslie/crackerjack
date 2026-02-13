from __future__ import annotations

import logging

from .docs_commands import check_docs, validate_docs
from .main_handlers import (
    handle_config_updates,
    handle_interactive_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)

logger = logging.getLogger(__name__)

__all__ = [
    "check_docs",
    "handle_config_updates",
    "handle_interactive_mode",
    "handle_standard_mode",
    "logger",
    "setup_ai_agent_env",
    "validate_docs",
]
