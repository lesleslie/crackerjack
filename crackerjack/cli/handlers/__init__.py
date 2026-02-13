from __future__ import annotations

import logging

# Import cache handlers from the correct module (cli root, not handlers subpackage)
from crackerjack.cli.cache_handlers import (
    handle_cache_stats,
    handle_clear_cache,
)

# Import advanced handlers from two separate modules
from crackerjack.cli.handlers.advanced import handle_advanced_optimizer
from crackerjack.cli.handlers.ai_features import handle_contextual_ai

# Import handlers using absolute imports to avoid circular imports during initialization
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

# Import config handlers from two separate modules
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

# Import provider selection handler with correct function name
from crackerjack.cli.handlers.provider_selection import handle_select_provider

# Import lifecycle handlers from the correct module (cli root, not handlers subpackage)
from crackerjack.cli.lifecycle_handlers import (
    health_probe_handler,
    start_handler,
    stop_handler,
)

# Import semantic handlers from the correct module (cli root, not handlers subpackage)
from crackerjack.cli.semantic_handlers import (
    handle_remove_from_semantic_index,
    handle_semantic_index,
    handle_semantic_search,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Analytics handlers
    "handle_anomaly_detection",
    "handle_heatmap_generation",
    "handle_predictive_analytics",
    # Changelog handlers
    "handle_changelog_commands",
    "handle_version_analysis",
    "setup_debug_and_verbose_flags",
    # Coverage handlers
    "handle_coverage_status",
    # Documentation handlers
    "handle_documentation_commands",
    "handle_mkdocs_integration",
    # Lifecycle handlers
    "health_probe_handler",
    "start_handler",
    "stop_handler",
    # Main handlers
    "handle_config_updates",
    "handle_interactive_mode",
    "handle_standard_mode",
    "setup_ai_agent_env",
    # Semantic handlers
    "handle_remove_from_semantic_index",
    "handle_semantic_index",
    "handle_semantic_search",
    # Advanced handlers
    "handle_advanced_optimizer",
    "handle_contextual_ai",
    # Cache handlers
    "handle_clear_cache",
    "handle_cache_stats",
    # Config handlers
    "config_handle_config_updates",
    "check_docs",
    "validate_docs",
    # Provider selection
    "handle_select_provider",
]
