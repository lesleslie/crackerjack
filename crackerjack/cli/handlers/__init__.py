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
    monitoring,
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
from .monitoring import (
    handle_dashboard_mode,
    handle_enhanced_monitor_mode,
    handle_mcp_commands,
    handle_mcp_server,
    handle_monitor_mode,
    handle_monitoring_commands,
    handle_restart_mcp_server,
    handle_restart_websocket_server,
    handle_restart_zuban_lsp,
    handle_server_commands,
    handle_start_websocket_server,
    handle_start_zuban_lsp,
    handle_stop_mcp_server,
    handle_stop_websocket_server,
    handle_stop_zuban_lsp,
    handle_unified_dashboard_mode,
    handle_watchdog_mode,
    handle_websocket_commands,
    handle_zuban_lsp_commands,
)

__all__ = [
    "handle_interactive_mode",
    "handle_monitor_mode",
    "handle_orchestrated_mode",
    "handle_standard_mode",
    "handle_watchdog_mode",
    "setup_ai_agent_env",
    # Add other functions from the modular handlers
    "handle_dashboard_mode",
    "handle_enhanced_monitor_mode",
    "handle_mcp_server",
    "handle_restart_mcp_server",
    "handle_restart_websocket_server",
    "handle_restart_zuban_lsp",
    "handle_start_websocket_server",
    "handle_start_zuban_lsp",
    "handle_stop_mcp_server",
    "handle_stop_websocket_server",
    "handle_stop_zuban_lsp",
    "handle_unified_dashboard_mode",
    "handle_acb_workflow_mode",
    "handle_config_updates",
    "handle_monitoring_commands",
    "handle_websocket_commands",
    "handle_mcp_commands",
    "handle_zuban_lsp_commands",
    "handle_server_commands",
    # Add other functions as they are moved to modular handlers
]
