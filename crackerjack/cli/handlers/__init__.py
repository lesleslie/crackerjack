from __future__ import annotations

import logging

from crackerjack.cli.cache_handlers import (
    handle_cache_stats,
    handle_clear_cache,
)
from crackerjack.cli.handlers.advanced import handle_advanced_optimizer
from crackerjack.cli.handlers.ai_features import handle_contextual_ai
from crackerjack.cli.handlers.analytics import (
    handle_anomaly_detection,
    handle_heatmap_generation,
    handle_predictive_analytics,
)
from crackerjack.cli.handlers.changelog import (
    handle_changelog_commands,
    handle_version_analysis,
    setup_debug_and_verbose_flags,
)
from crackerjack.cli.handlers.config_handlers import (
    handle_config_updates as config_handle_config_updates,
)
from crackerjack.cli.handlers.coverage import handle_coverage_status
from crackerjack.cli.handlers.docs_commands import (
    check_docs,
    validate_docs,
)
from crackerjack.cli.handlers.documentation import (
    handle_documentation_commands,
    handle_mkdocs_integration,
)
from crackerjack.cli.handlers.main_handlers import (
    handle_config_updates,
    handle_interactive_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)
from crackerjack.cli.handlers.provider_selection import handle_select_provider
from crackerjack.cli.lifecycle_handlers import (
    health_probe_handler,
    start_handler,
    stop_handler,
)
from crackerjack.cli.semantic_handlers import (
    handle_remove_from_semantic_index,
    handle_semantic_index,
    handle_semantic_search,
)

logger = logging.getLogger(__name__)

__all__ = [
    "handle_anomaly_detection",
    "handle_heatmap_generation",
    "handle_predictive_analytics",
    "handle_changelog_commands",
    "handle_version_analysis",
    "setup_debug_and_verbose_flags",
    "handle_coverage_status",
    "handle_documentation_commands",
    "handle_mkdocs_integration",
    "health_probe_handler",
    "start_handler",
    "stop_handler",
    "handle_config_updates",
    "handle_interactive_mode",
    "handle_standard_mode",
    "setup_ai_agent_env",
    "handle_remove_from_semantic_index",
    "handle_semantic_index",
    "handle_semantic_search",
    "handle_advanced_optimizer",
    "handle_contextual_ai",
    "handle_clear_cache",
    "handle_cache_stats",
    "config_handle_config_updates",
    "check_docs",
    "validate_docs",
    "handle_select_provider",
]
