"""CLI handlers module for Crackerjack.

This module contains all the command handlers for the Crackerjack CLI.
"""

# Import specific functions from the modular handlers
# Import other specific functions from other handlers files
from . import (
    advanced,
    ai_features,
    analytics,
    changelog,
    config_handlers,
    coverage,
    documentation,
)
from .advanced import *
from .ai_features import *
from .analytics import *
from .changelog import *
from .config_handlers import *
from .coverage import *
from .documentation import *

# Import main handler functions that coordinate the core CLI workflows
from .main_handlers import (
    handle_acb_workflow_mode,
    handle_config_updates,
    handle_interactive_mode,
    handle_orchestrated_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)

__all__ = [
    "handle_acb_workflow_mode",
    "handle_config_updates",
    "handle_interactive_mode",
    "handle_orchestrated_mode",
    "handle_standard_mode",
    "setup_ai_agent_env",
    # Add other functions as they are moved to modular handlers
]
