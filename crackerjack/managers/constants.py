"""Manager-related constants.

This module centralizes magic numbers used throughout the managers layer,
including test thresholds, timeout multipliers, and workflow parameters.
"""

# Test execution thresholds
TIMEOUT_THRESHOLD_MULTIPLIER = 0.9  # 90% of timeout considered "close"
MAX_TEST_DURATION_WARNING = 300.0  # 5 minutes

# Test result display limits
MAX_TEST_FAILURES_TO_DISPLAY = 50
MAX_TEST_ERRORS_TO_DISPLAY = 100

# Parallel execution limits
DEFAULT_PARALLEL_TESTS = 4
MIN_PARALLEL_THRESHOLD = 10  # Only parallelize if >= 10 tests

# Progress reporting granularity
PROGRESS_UPDATE_PERCENTAGE = 5  # Update every 5% progress

# AI agent operational limits
MAX_AI_FIX_ITERATIONS = 10
MIN_AI_CONFIDENCE_THRESHOLD = 0.7

# Hook execution time warnings
SLOW_HOOK_THRESHOLD = 5.0  # Hooks taking >5 seconds are considered slow
VERY_SLOW_HOOK_THRESHOLD = 30.0  # Hooks taking >30 seconds are very slow

# Publication workflow defaults
DEFAULT_PYPI_TIMEOUT = 300
DEFAULT_GITHUB_TIMEOUT = 60

# Cache invalidation intervals
PATTERN_CACHE_TTL = 300  # 5 minutes
INDEX_CACHE_TTL = 600  # 10 minutes

# File watching limits
MAX_WATCHED_FILES = 1000
DEBOUNCE_INTERVAL = 0.5  # 500ms

# Workflow orchestration
MAX_CONCURRENT_WORKERS = 8
TASK_DISPATCH_TIMEOUT = 60.0

# Panel display widths
DEFAULT_PANEL_WIDTH = 80
DEFAULT_COLUMN_WIDTH = 120
