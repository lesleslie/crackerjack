# Security Documentation

## Security Hardening Implementation

This document outlines the comprehensive security measures implemented to protect the code cleaning workflow (`-x` option) and other sensitive operations.

## Critical Vulnerabilities Addressed

### 1. Command Injection Prevention (CWE-77) - CRITICAL

**Problem**: User input could contain shell metacharacters enabling command injection
**Solution**: Comprehensive input validation framework with pattern detection

- **Shell Metacharacter Detection**: Blocks dangerous characters (`;`, `&`, `|`, `$`, backticks, etc.)
- **SQL Injection Prevention**: Pattern matching for SQL injection attempts (UNION, DROP, etc.)
- **Code Injection Prevention**: Detection of Python code execution patterns (eval, exec, __import__)
- **JSON Payload Validation**: Size limits, depth limits, and structure validation
- **Rate Limiting**: Prevents abuse through excessive validation failures

### 2. Path Traversal Prevention (CWE-22) - CRITICAL

**Problem**: Original `backup_file` method was vulnerable to path traversal attacks
**Solution**: Implemented comprehensive path validation in `SecurePathValidator`

- **Path Resolution**: All paths are resolved to absolute paths to eliminate `..` components
- **Component Validation**: Dangerous path components like `..`, `.`, `~`, `$` are blocked
- **Base Directory Enforcement**: All operations are restricted to allowed base directories
- **Windows Reserved Names**: Blocks dangerous Windows reserved names (CON, PRN, AUX, NUL)

### 3. Input Size Limits (CWE-400) - HIGH

**Problem**: No protection against processing extremely large inputs (DoS attacks)
**Solution**: Comprehensive size validation across all input types

- **String Length Limits**: Configurable limits (default 10KB for general strings)
- **JSON Size Limits**: Maximum 1MB JSON payload size with depth limits
- **File Size Limits**: 100MB limit to prevent resource exhaustion
- **Path Length Limits**: Maximum 4096 character path length
- **Command Argument Limits**: Maximum 1KB per command argument

### 4. Rate Limiting (CWE-799) - HIGH

**Problem**: No protection against repeated validation failures or abuse
**Solution**: Advanced rate limiting system with client tracking

- **Sliding Window**: Accurate rate limiting using sliding window algorithm
- **Tiered Limits**: Different limits for different validation types
- **Progressive Blocking**: Escalating block durations for repeated violations
- **Critical Event Limits**: Strict limits on injection attempts (2-3 per minute)
- **Automatic Cleanup**: Expired data automatically cleaned to prevent memory leaks

### 5. Atomic File Operations (CWE-362) - MEDIUM

**Problem**: Race conditions in file operations could lead to corruption
**Solution**: Implemented atomic write operations

- **Temporary File Strategy**: Write to temporary file first, then atomic rename
- **Atomic Backup**: Creates backup atomically before modifying original
- **Proper Cleanup**: Failed operations properly clean up temporary files
- **fsync()**: Ensures data is written to disk before rename

### 6. Security Event Logging (CWE-778) - LOW

**Problem**: No audit trail for security events
**Solution**: Comprehensive security event logging

- **Structured Logging**: JSON-formatted security events with metadata
- **Event Classification**: Events categorized by type and severity level
- **Audit Trail**: Complete audit trail of all security-relevant operations
- **Real-time Monitoring**: Critical events logged immediately
- **Injection Attempt Tracking**: Detailed logging of all injection attempts

## Security Architecture

### Core Security Components

1. **SecureInputValidator** (`/services/input_validator.py`)

   - Comprehensive input validation framework
   - Pattern-based injection detection (SQL, command, code)
   - JSON payload validation with size/depth limits
   - Configurable validation rules and decorators

1. **ValidationRateLimiter** (`/services/validation_rate_limiter.py`)

   - Advanced rate limiting with sliding windows
   - Client-based tracking and progressive blocking
   - Tiered limits by validation type severity
   - Automatic cleanup of expired data

1. **SecurePathValidator** (`/services/secure_path_utils.py`)

   - Central path validation and sanitization
   - Configurable security limits and restrictions
   - Path traversal attack prevention

1. **AtomicFileOperations** (`/services/secure_path_utils.py`)

   - Race-condition-free file operations
   - Atomic backup and write operations
   - Proper cleanup on failures

1. **SecurityLogger** (`/services/security_logger.py`)

   - Structured security event logging
   - Multiple severity levels (LOW, MEDIUM, HIGH, CRITICAL)
   - Comprehensive audit trail with injection attempt tracking

1. **Enhanced FileProcessor** (`/code_cleaner.py`)

   - Integrates security validation into all file operations
   - Uses atomic operations for safety
   - Comprehensive error handling and logging

### Security Configuration

```python
# Input Validation Configuration
class ValidationConfig:
    MAX_STRING_LENGTH = 10000  # 10KB string limit
    MAX_PROJECT_NAME_LENGTH = 255  # Project name limit
    MAX_JOB_ID_LENGTH = 128  # Job ID limit
    MAX_JSON_SIZE = 1024 * 1024  # 1MB JSON limit
    MAX_JSON_DEPTH = 10  # JSON nesting limit
    ALLOW_SHELL_METACHARACTERS = False  # Shell injection protection
    STRICT_ALPHANUMERIC_MODE = False  # Alphanumeric-only mode


# Rate Limiting Configuration
class ValidationRateLimit:
    max_failures = 10  # Max failures per window
    window_seconds = 60  # Time window in seconds
    block_duration = 300  # Block duration (5 minutes)


# Path Validation Configuration
class SecurePathValidator:
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB file limit
    MAX_PATH_LENGTH = 4096  # Path length limit
    DANGEROUS_COMPONENTS = {  # Blocked path components
        "..",
        ".",
        "~",
        "$",
        "`",
        ";",
        "&",
        "|",
        "<",
        ">",
        "CON",
        "PRN",
        "AUX",
        "NUL",  # Windows reserved names
    }
```

## Security Event Types

The system logs the following security events:

**Critical Security Events:**

- `COMMAND_INJECTION_ATTEMPT`: Shell metacharacters or command injection detected
- `SQL_INJECTION_ATTEMPT`: SQL injection patterns detected in input
- `CODE_INJECTION_ATTEMPT`: Code execution patterns detected (eval, exec, etc.)
- `PATH_TRAVERSAL_ATTEMPT`: Directory traversal attack attempt
- `UNAUTHORIZED_ACCESS_ATTEMPT`: Access to restricted resources

**High Priority Events:**

- `RATE_LIMIT_EXCEEDED`: Client exceeded validation failure limits
- `INPUT_SIZE_EXCEEDED`: Input exceeded maximum size limits
- `FILE_SIZE_EXCEEDED`: File exceeded maximum size limit
- `DANGEROUS_PATH_DETECTED`: Dangerous path component found

**Medium Priority Events:**

- `INVALID_JSON_PAYLOAD`: Malformed or invalid JSON input
- `VALIDATION_FAILED`: General security validation failure

**Low Priority Events:**

- `BACKUP_CREATED`: Secure backup file created
- `FILE_CLEANED`: File successfully processed
- `ATOMIC_OPERATION`: Atomic file operation performed
- `TEMP_FILE_CREATED`: Secure temporary file created

## Usage Examples

### Input Validation Framework

```python
from crackerjack.services.input_validator import (
    get_input_validator,
    validate_and_sanitize_string,
)

# Comprehensive input validation
validator = get_input_validator()

# Validate user input
result = validator.validate_command_args("safe_command arg1 arg2")
if result.valid:
    sanitized_args = result.sanitized_value
    # Safe to execute
else:
    # Input validation failed - log and reject
    print(f"Invalid input: {result.error_message}")

# Convenience function for quick validation
try:
    safe_string = validate_and_sanitize_string("user_input")
    # Use safe_string
except ExecutionError as e:
    # Handle validation failure
    pass
```

### Validation Decorators

```python
from crackerjack.services.input_validator import validation_required


@validation_required(validate_args=True, validate_kwargs=True)
def process_user_input(command: str, options: str = ""):
    # Function automatically validates all string parameters
    return f"Processing: {command} with {options}"


# Automatic validation on function call
try:
    result = process_user_input("safe_command", options="safe_options")
except ExecutionError:
    # Validation failed - input was rejected
    pass
```

### MCP Tool Integration

```python
# MCP tools automatically use input validation
@mcp_app.tool()
async def secure_mcp_tool(stage: str, kwargs: str) -> str:
    validator = get_input_validator()

    # Validate stage parameter
    stage_result = validator.sanitizer.sanitize_string(
        stage, max_length=50, strict_alphanumeric=True
    )
    if not stage_result.valid:
        return f'{{"error": "Invalid stage: {stage_result.error_message}"}}'

    # Validate JSON kwargs
    if kwargs.strip():
        json_result = validator.validate_json_payload(kwargs)
        if not json_result.valid:
            return f'{{"error": "Invalid JSON: {json_result.error_message}"}}'

    # Process with sanitized inputs
    return process_stage(stage_result.sanitized_value)
```

### Rate Limiting Integration

```python
from crackerjack.services.validation_rate_limiter import get_validation_rate_limiter

rate_limiter = get_validation_rate_limiter()

# Check if client is blocked
if rate_limiter.is_blocked("client_id"):
    remaining = rate_limiter.get_block_time_remaining("client_id")
    raise ExecutionError(f"Rate limited. Try again in {remaining} seconds.")

# Record validation failure
rate_limiter.record_failure(
    "client_id", "command_injection", SecurityEventLevel.CRITICAL
)
```

### Manual Security Validation

```python
from crackerjack.services.secure_path_utils import SecurePathValidator

# Validate file path
try:
    validated_path = SecurePathValidator.validate_file_path(
        user_path, base_directory=project_root
    )
    # Safe to process
except ExecutionError:
    # Security validation failed
    pass
```

## Security Testing

Comprehensive security tests are provided in multiple test files:

### Core Input Validation Tests (`/tests/test_input_validation.py`)

- Command injection prevention testing
- SQL injection pattern detection
- Code injection pattern detection
- Path traversal attack simulation
- JSON payload validation (size, depth, syntax)
- Rate limiting functionality
- Validation decorator testing
- Security logging integration

### Security Hardening Tests (`/tests/test_security_hardening.py`)

- File size limit enforcement
- Base directory restriction validation
- Atomic operation integrity
- Security event logging verification

### Integration Testing

- MCP tool parameter validation
- WebSocket message validation
- Slash command security
- Project initialization validation

Run all security tests:

```bash
# Run comprehensive input validation tests
python -m pytest tests/test_input_validation.py -v

# Run security hardening tests
python -m pytest tests/test_security_hardening.py -v

# Run all security-related tests
python -m pytest tests/ -k "security" -v
```

## Security Headers and Configuration

### Recommended File Permissions

- **Source Files**: 644 (read/write owner, read group/others)
- **Backup Files**: 600 (read/write owner only)
- **Temporary Files**: 600 (read/write owner only)

### Logging Configuration

Security events are logged with appropriate severity levels:

- **CRITICAL**: Immediate security threats (path traversal attempts)
- **HIGH**: Security policy violations (file size exceeded)
- **MEDIUM**: Security validation failures
- **LOW**: Normal security operations (backups, file cleaning)

## Security Checklist

### Input Validation Security

- [x] Command injection prevention implemented
- [x] SQL injection pattern detection
- [x] Code injection pattern detection
- [x] Shell metacharacter blocking
- [x] JSON payload validation (size, depth, syntax)
- [x] Input size limits enforced
- [x] Strict alphanumeric validation modes
- [x] Validation decorators for automatic protection

### Rate Limiting and DoS Protection

- [x] Advanced rate limiting system implemented
- [x] Sliding window algorithm for accurate limits
- [x] Progressive blocking for repeated violations
- [x] Tiered limits by validation type severity
- [x] Client-based tracking and blocking
- [x] Automatic cleanup of expired data

### Path Security

- [x] Path traversal vulnerability fixed
- [x] Base directory restrictions enforced
- [x] Dangerous path component detection
- [x] Windows reserved name blocking

### File Operations Security

- [x] File size limits implemented
- [x] Atomic file operations implemented
- [x] Secure temporary file handling
- [x] Race condition prevention

### Security Monitoring

- [x] Comprehensive security event logging
- [x] Structured JSON security events
- [x] Multiple severity levels (LOW, MEDIUM, HIGH, CRITICAL)
- [x] Injection attempt tracking and logging

### Integration Security

- [x] MCP tool parameter validation
- [x] WebSocket message validation
- [x] Slash command security validation
- [x] Project initialization validation

### Testing and Documentation

- [x] Comprehensive security test suite
- [x] Integration testing for all entry points
- [x] Security documentation and usage examples
- [x] Rate limiting test coverage
- [x] Injection prevention test coverage

## Incident Response

If security issues are discovered:

1. **Report**: Create issue with "security" label
1. **Assessment**: Evaluate severity using CVSS framework
1. **Containment**: Implement temporary mitigations
1. **Resolution**: Develop and test security fix
1. **Verification**: Run security test suite
1. **Documentation**: Update security documentation

## Security Updates

This security implementation addresses all identified vulnerabilities in the code cleaning workflow. Regular security reviews should be conducted to identify and address new threats.

**Last Security Review**: January 2025
**Next Scheduled Review**: July 2025
