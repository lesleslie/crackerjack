"""CLI-related constants.

This module centralizes magic numbers used throughout the CLI layer,
making the codebase more maintainable and self-documenting.
"""

# Default timeout values (in seconds)
DEFAULT_ZUBAN_LSP_TIMEOUT = 120
DEFAULT_GLOBAL_LOCK_TIMEOUT = 1800
DEFAULT_TEST_TIMEOUT = 600
DEFAULT_COMMAND_TIMEOUT = 300

# Maximum iterations for AI agents
DEFAULT_MAX_AI_ITERATIONS = 10

# Coverage thresholds
DEFAULT_COVERAGE_GOAL = 100.0
COVERAGE_RATCHET_THRESHOLD = 0.0

# File size limits (in bytes)
MAX_FILE_SIZE_BYTES = 100_000  # 100KB default for large file checks

# Display limits
MAX_FAILURES_TO_DISPLAY = 10
MAX_ISSUES_TO_DISPLAY = 20

# Progress reporting intervals (in seconds)
PROGRESS_UPDATE_INTERVAL = 1
PROGRESS_SLOW_UPDATE_INTERVAL = 5

# LSP configuration
DEFAULT_LSP_PORT = 8677
DEFAULT_LSP_MODE = "tcp"

# Xcode build defaults
DEFAULT_XCODE_PROJECT = "app/MdInjectApp/MdInjectApp.xcodeproj"
DEFAULT_XCODE_SCHEME = "MdInjectApp"
DEFAULT_XCODE_CONFIGURATION = "Debug"
DEFAULT_XCODE_DESTINATION = "platform=macOS"

# Heatmap settings
DEFAULT_HEATMAP_TYPE = "error_frequency"
ANOMALY_DETECTION_SENSITIVITY = 2.0
PREDICTION_PERIODS_DEFAULT = 10

# Cache and file management
TEMP_FILE_EXTENSION = ".tmp"
CACHE_DIR_NAME = ".cache"

# Git-related
DEFAULT_GIT_REMOTE = "origin"
DEFAULT_GIT_BRANCH = "main"

# Version info
PROJECT_NAME = "crackerjack"
VARIABLE_PREFIX = "CRACKERJACK"
