"""Service-related constants.

This module centralizes magic numbers used throughout the services layer,
including timeouts, retry policies, and operational parameters.
"""

# HTTP/API timeouts (in seconds)
DEFAULT_API_TIMEOUT = 10.0
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_SHORT_TIMEOUT = 5.0

# Retry policies
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0
MAX_RETRY_DELAY = 30.0

# Process management timeouts (in seconds)
PROCESS_STARTUP_TIMEOUT = 30.0
PROCESS_SHUTDOWN_TIMEOUT = 10.0
PROCESS_HEALTH_CHECK_TIMEOUT = 5.0

# Cache TTL values (in seconds)
DEFAULT_CACHE_TTL = 5.0
LONG_CACHE_TTL = 60.0
SHORT_CACHE_TTL = 1.0

# Database connection settings
DEFAULT_DB_TIMEOUT = 30.0
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10

# File I/O timeouts
FILE_READ_TIMEOUT = 10.0
FILE_WRITE_TIMEOUT = 10.0

# LSP client timeouts
LSP_RESPONSE_TIMEOUT = 5.0
LSP_PROCESS_START_TIMEOUT = 30.0
LSP_PROCESS_STOP_TIMEOUT = 10.0

# Metrics collection intervals (in seconds)
METRICS_COLLECTION_INTERVAL = 1.0
METRICS_AGGREGATION_WINDOW = 60.0

# Thread pool sizes
DEFAULT_THREAD_POOL_SIZE = 4
MAX_THREAD_POOL_SIZE = 16
IO_THREAD_POOL_SIZE = 8

# Queue sizes
DEFAULT_QUEUE_SIZE = 1000
LARGE_QUEUE_SIZE = 10_000

# Buffer sizes
DEFAULT_BUFFER_SIZE = 8192  # 8KB
LARGE_BUFFER_SIZE = 65536  # 64KB
