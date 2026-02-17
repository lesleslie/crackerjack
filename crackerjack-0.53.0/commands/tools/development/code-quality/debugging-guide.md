______________________________________________________________________

title: Comprehensive Debugging Guide
owner: Platform Reliability Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
- Windows
  agents:
- devops-troubleshooter
- python-pro
- javascript-pro
- golang-pro
- rust-pro
- observability-incident-lead
  required_scripts: []
  risk: low
  status: active
  id: 01K6H7DBKXPATNET8YV0JQGZX7
  category: development
  tags:
- debugging
- troubleshooting
- observability
- performance
- production

______________________________________________________________________

## Comprehensive Debugging Guide

## Context

Effective debugging requires a systematic approach combining debugging strategies, tool proficiency, and observability-driven investigation. This guide consolidates debugging techniques from local development through production incident response, replacing deprecated `debug-monitoring.md` and `advanced-debugging.md` tools.

## Requirements

- Familiarity with debugging concepts and tools for your stack
- Access to application logs, metrics, and traces (for production debugging)
- Development environment with debugger support
- Basic understanding of your application's architecture

## Inputs

- `$ISSUE_DESCRIPTION` — observed symptoms, error messages, or unexpected behavior
- `$ENVIRONMENT` — where the issue occurs (local, staging, production)
- `$STACK` — primary language/framework (python, node, go, rust, etc.)
- `$REPRODUCTION_STEPS` — steps to reproduce (optional, aids investigation)

## Outputs

- Root cause analysis with supporting evidence
- Fix implementation or mitigation strategy
- Prevention recommendations to avoid recurrence
- Documentation updates (runbooks, troubleshooting guides)

______________________________________________________________________

## Part 1: Debugging Strategies

### The Scientific Method for Debugging

Follow this systematic approach for any debugging investigation:

**1. Observe & Document**

```markdown
# Issue Report Template
## Symptoms
- What is happening?
- What should be happening?
- When did this start?

## Environment
- Platform/OS: [macOS 14.2, Ubuntu 22.04, etc.]
- Application version: [v2.3.1]
- Dependencies: [Python 3.11, Node 20.x, etc.]

## Reproduction Steps
1. Navigate to /users page
2. Click "Export CSV" button
3. Observe: Request hangs for 60s then times out

## Impact
- User-facing: Yes/No
- Frequency: Always / Intermittent (20%)
- Affected users: All users / Subset (Enterprise tier)
```

**2. Form Hypotheses**

List possible causes ranked by likelihood:

```python
# Hypothesis tracking example
hypotheses = [
    {
        "theory": "Database query timeout on large dataset",
        "likelihood": "high",
        "test": "Check query execution time in DB logs",
        "evidence_needed": ["query logs", "execution plan"],
    },
    {
        "theory": "Memory exhaustion during CSV generation",
        "likelihood": "medium",
        "test": "Monitor memory usage during export",
        "evidence_needed": ["memory metrics", "heap dump"],
    },
    {
        "theory": "Rate limiting on export endpoint",
        "likelihood": "low",
        "test": "Check rate limit headers in response",
        "evidence_needed": ["HTTP response headers"],
    },
]
```

**3. Test One Variable at a Time**

Isolate variables to pinpoint the cause:

```bash
# Example: Testing CSV export issue
# Test 1: Small dataset
curl -X POST /api/export?limit=10  # Success in 2s

# Test 2: Medium dataset
curl -X POST /api/export?limit=100  # Success in 8s

# Test 3: Large dataset
curl -X POST /api/export?limit=1000  # Timeout after 60s

# Conclusion: Issue correlates with dataset size
```

**4. Gather Evidence**

Collect data before making changes:

```bash
# Capture baseline metrics
docker stats app-container > baseline.txt

# Enable verbose logging
export DEBUG=app:*
export LOG_LEVEL=debug

# Reproduce issue and capture evidence
./reproduce-issue.sh | tee reproduction-log.txt

# Capture state after issue
kubectl logs deployment/app -n production --tail=500 > incident-logs.txt
curl http://localhost:9090/metrics > metrics-snapshot.txt
```

**5. Implement & Validate Fix**

Test thoroughly before deploying:

```python
# Example: Fix for CSV export timeout
# Before: Loading all records into memory
def export_csv(query):
    records = db.execute(query).fetchall()  # OOM on large datasets
    return generate_csv(records)


# After: Streaming approach
def export_csv_streaming(query):
    """Stream CSV generation to avoid memory issues"""

    def generate():
        cursor = db.execute(query)
        yield csv_header()

        while True:
            batch = cursor.fetchmany(size=1000)
            if not batch:
                break
            for record in batch:
                yield csv_row(record)

    return StreamingResponse(generate(), media_type="text/csv")


# Validation test
def test_large_export_memory_usage():
    """Ensure memory stays bounded during large exports"""
    tracker = MemoryTracker()

    with tracker:
        response = client.post("/api/export?limit=100000")

    assert tracker.peak_mb < 100, "Memory usage should stay under 100MB"
    assert response.status_code == 200
```

### Binary Search Debugging

Efficient technique for finding the introduction point of a bug:

```bash
# Git bisect: Find commit that introduced bug
git bisect start
git bisect bad                    # Current version is broken
git bisect good v2.3.0           # v2.3.0 was working

# Git automatically checks out a commit midway
# Test if bug exists:
./run-tests.sh

git bisect good   # if tests pass
# OR
git bisect bad    # if tests fail

# Repeat until git identifies the exact commit
# Example output:
# 7a3b8c9 is the first bad commit
# commit 7a3b8c9
# Author: developer@example.com
# Date:   Mon Sep 15 14:23:19 2025
#
#     Add bulk CSV export feature
```

```python
# Binary search for problematic input value
def find_failing_threshold():
    """Find exact input size that causes failure"""
    low, high = 0, 100000

    while low < high:
        mid = (low + high) // 2
        success = test_export(record_count=mid)

        if success:
            low = mid + 1
            print(f"✓ {mid} records: SUCCESS")
        else:
            high = mid
            print(f"✗ {mid} records: FAILURE")

    print(f"\nFailing threshold: {low} records")
    return low


# Example output:
# ✓ 50000 records: SUCCESS
# ✗ 75000 records: FAILURE
# ✓ 62500 records: SUCCESS
# ✗ 68750 records: FAILURE
# ✓ 65625 records: SUCCESS
# ✗ 67187 records: FAILURE
#
# Failing threshold: 65626 records
```

### Rubber Duck Debugging

Explain your code/problem out loud (to a rubber duck, colleague, or yourself):

````markdown
# Rubber Duck Template

## The Problem
I'm seeing intermittent 500 errors on the /api/users endpoint,
affecting about 15% of requests.

## What I Know
1. Error happens randomly - can't reproduce locally
2. Stack trace shows NullPointerException in UserService
3. Only happens in production, not staging
4. Started after deployment of v2.4.0

## Walking Through the Code
The endpoint calls UserService.getUser(id):

```java
public User getUser(String id) {
    // Step 1: Fetch from cache
    User cached = cache.get(id);  // Could this return null?

    // Step 2: Return cached or fetch from DB
    return cached != null ? cached : db.findById(id);
    // ↑ Wait... what if db.findById() also returns null for deleted users?
    // ↑ And then we call cached.getName() somewhere expecting it to exist?
}
````

## Aha Moment

We're not handling the case where a user was deleted from the DB but
still exists in cache references! When cache expires and DB fetch returns
null, we get NPE.

## Solution

Add null check and throw proper exception:

```java
public User getUser(String id) {
    User cached = cache.get(id);
    if (cached != null) return cached;

    User user = db.findById(id);
    if (user == null) {
        throw new UserNotFoundException(id);
    }

    cache.set(id, user);
    return user;
}
```

````

---

## Part 2: Language & Tool-Specific Debugging

### Python Debugging with pdb/ipdb

**Basic pdb usage:**

```python
import pdb

def process_payment(amount, user_id):
    # Set breakpoint
    pdb.set_trace()  # Execution pauses here

    user = get_user(user_id)
    if user.balance < amount:
        raise InsufficientFundsError(f"User {user_id} has insufficient funds")

    # Deduct amount
    user.balance -= amount
    db.session.commit()

# pdb commands at breakpoint:
# (Pdb) p amount          # Print variable
# 100.0
# (Pdb) p user.balance
# 50.0
# (Pdb) n                 # Next line
# (Pdb) s                 # Step into function
# (Pdb) c                 # Continue execution
# (Pdb) l                 # List source code
# (Pdb) w                 # Where am I? (stack trace)
````

**Advanced: Conditional breakpoints**

```python
import pdb


def process_batch(transactions):
    for i, txn in enumerate(transactions):
        # Only break on specific condition
        if txn.amount > 10000:
            pdb.set_trace()

        process_transaction(txn)


# Alternative: Using breakpoint() (Python 3.7+)
def process_user(user_id):
    user = get_user(user_id)

    # Built-in breakpoint (respects PYTHONBREAKPOINT env var)
    breakpoint()

    return calculate_metrics(user)


# Disable all breakpoints:
# PYTHONBREAKPOINT=0 python app.py
```

**Post-mortem debugging:**

```python
import sys
import pdb


def main():
    try:
        # Your application code
        result = risky_operation()
    except Exception:
        # Drop into debugger on exception
        pdb.post_mortem(sys.exc_info()[2])
        raise


# Alternative: Automatic post-mortem
if __name__ == "__main__":
    import pdb

    pdb.run("main()")  # Run under debugger, auto-break on exception
```

**Remote debugging with debugpy (for containers/remote servers):**

```python
# app.py - Enable remote debugging
import debugpy

# Listen on port 5678
debugpy.listen(("0.0.0.0", 5678))
print("Waiting for debugger attach...")
debugpy.wait_for_client()  # Block until debugger connects

# Your application code
app = create_app()
app.run()

# Connect from VS Code (launch.json):
# {
#     "name": "Python: Remote Attach",
#     "type": "python",
#     "request": "attach",
#     "connect": {
#         "host": "localhost",
#         "port": 5678
#     },
#     "pathMappings": [{
#         "localRoot": "${workspaceFolder}",
#         "remoteRoot": "/app"
#     }]
# }
```

### JavaScript/TypeScript Debugging

**Node.js with Chrome DevTools:**

```bash
# Start Node with inspector
node --inspect app.js
# Debugger listening on ws://127.0.0.1:9229/...

# Or break immediately on first line
node --inspect-brk app.js

# Open Chrome DevTools:
# 1. Open chrome://inspect in Chrome
# 2. Click "inspect" under Remote Target
# 3. Full DevTools debugging experience
```

**Debugging with VS Code:**

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Debug TypeScript",
      "runtimeArgs": ["-r", "ts-node/register"],
      "args": ["${workspaceFolder}/src/index.ts"],
      "sourceMaps": true,
      "cwd": "${workspaceFolder}",
      "protocol": "inspector",
      "env": {
        "NODE_ENV": "development"
      }
    },
    {
      "type": "node",
      "request": "attach",
      "name": "Attach to Process",
      "port": 9229,
      "skipFiles": ["<node_internals>/**"]
    }
  ]
}
```

**Console debugging techniques:**

```javascript
// Basic console methods
console.log("User:", user);           // Simple output
console.dir(user, { depth: null });   // Deep object inspection
console.table(users);                 // Tabular data
console.trace("API call");            // Stack trace

// Grouped output
console.group("Payment Processing");
console.log("Amount:", amount);
console.log("User:", userId);
console.groupEnd();

// Timing
console.time("database-query");
await db.query("SELECT * FROM users");
console.timeEnd("database-query");  // database-query: 45.2ms

// Conditional logging
console.assert(user.age >= 18, "User must be 18+");

// Performance monitoring
const mark = performance.now();
await heavyOperation();
console.log(`Operation took ${performance.now() - mark}ms`);
```

**Browser DevTools debugging:**

```javascript
// Debugger statement (breakpoint in code)
function processCheckout(cart) {
    debugger;  // Execution pauses when DevTools open

    const total = cart.items.reduce((sum, item) => sum + item.price, 0);
    return total;
}

// Monitor function calls
monitor(processCheckout);  // Logs when function is called
unmonitor(processCheckout);

// Watch object changes
const user = { name: "Alice", balance: 100 };
observe(user);  // Logs property changes

// Break on property access
const config = { apiKey: "secret" };
debug(config.apiKey);  // Break when accessed

// Copy to clipboard (in DevTools console)
copy(user);  // Copies JSON representation
```

### Go Debugging with Delve

**Basic delve usage:**

```bash
# Install delve
go install github.com/go-delve/delve/cmd/dlv@latest

# Debug a program
dlv debug main.go

# Debug a test
dlv test -- -test.run TestPaymentProcessing

# Attach to running process
dlv attach $(pgrep myapp)
```

**Delve commands:**

```go
// main.go
package main

func processOrder(orderID string) error {
    order, err := fetchOrder(orderID)
    if err != nil {
        return err
    }

    // Want to inspect order here
    total := calculateTotal(order)
    return submitPayment(total)
}

// Delve session:
// $ dlv debug main.go
// (dlv) break main.processOrder      # Set breakpoint
// (dlv) continue                      # Run until breakpoint
// (dlv) print order                   # Inspect variable
// (dlv) print order.Items[0].Price   # Navigate structs
// (dlv) next                          # Next line
// (dlv) step                          # Step into function
// (dlv) locals                        # Show all local variables
// (dlv) goroutines                    # List all goroutines
// (dlv) goroutine 5                   # Switch to goroutine 5
```

**Conditional breakpoints:**

```bash
# Break only when condition is true
(dlv) break main.go:42
(dlv) condition 1 amount > 1000

# Break with hit count
(dlv) break main.go:42
(dlv) condition 1 amount > 1000 && hitCount > 5
```

**Remote debugging:**

```bash
# On remote server
dlv exec ./myapp --headless --listen=:2345 --api-version=2

# From local machine
dlv connect remote-server:2345
```

**VS Code integration:**

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Launch Go",
      "type": "go",
      "request": "launch",
      "mode": "debug",
      "program": "${workspaceFolder}/cmd/app",
      "env": {
        "ENV": "development"
      },
      "args": ["-config", "config.yaml"]
    }
  ]
}
```

### Rust Debugging with rust-gdb/lldb

**Basic rust-gdb usage:**

```bash
# Build with debug symbols
cargo build

# Debug with rust-gdb (wrapper around gdb)
rust-gdb target/debug/myapp

# Common commands:
# (gdb) break main.rs:42        # Set breakpoint
# (gdb) run                      # Start execution
# (gdb) print variable           # Inspect variable
# (gdb) backtrace                # Stack trace
# (gdb) next                     # Next line
# (gdb) step                     # Step into
# (gdb) continue                 # Continue execution
```

**VS Code debugging:**

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "lldb",
      "request": "launch",
      "name": "Debug Rust",
      "cargo": {
        "args": ["build", "--bin=myapp"],
        "filter": {
          "name": "myapp",
          "kind": "bin"
        }
      },
      "args": [],
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

**Debug assertions:**

```rust
fn process_payment(amount: u64, user_id: &str) -> Result<(), Error> {
    debug_assert!(amount > 0, "Amount must be positive");
    debug_assert!(!user_id.is_empty(), "User ID required");

    // These checks only run in debug builds
    // Removed in release builds for performance

    let user = get_user(user_id)?;
    user.charge(amount)?;
    Ok(())
}

// Conditional compilation for debugging
#[cfg(debug_assertions)]
fn expensive_invariant_check() {
    // Only runs in debug builds
    assert_eq!(db.count_users(), cache.count_users());
}
```

______________________________________________________________________

## Part 3: Production Debugging Patterns

### Observability-Driven Debugging

**Three pillars: Logs, Metrics, Traces**

```python
from opentelemetry import trace, metrics
import structlog

# Structured logging
logger = structlog.get_logger()

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create custom metric
payment_errors = meter.create_counter(
    "payment_errors_total", description="Total payment processing errors"
)


def process_payment(order_id: str, amount: float):
    # Start trace span
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("order_id", order_id)
        span.set_attribute("amount", amount)

        try:
            # Structured log with context
            logger.info(
                "processing_payment",
                order_id=order_id,
                amount=amount,
                user_id=get_current_user_id(),
            )

            # Business logic
            result = charge_customer(order_id, amount)

            span.set_attribute("payment_status", "success")
            return result

        except PaymentError as e:
            # Increment error metric
            payment_errors.add(1, {"error_type": type(e).__name__})

            # Log with error context
            logger.error(
                "payment_failed",
                order_id=order_id,
                amount=amount,
                error=str(e),
                exc_info=True,
            )

            # Mark span as error
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise


# Query during incident:
# Logs: Show me all payment_failed logs in last hour
# Metrics: Graph payment_errors_total by error_type
# Traces: Find traces with errors in process_payment span
```

**Correlation IDs for request tracking:**

```python
import uuid
from contextvars import ContextVar

# Thread-safe request context
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def generate_request_id() -> str:
    return str(uuid.uuid4())


# Middleware to set request ID
class RequestIDMiddleware:
    async def __call__(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", generate_request_id())
        request_id_var.set(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Use in logging
logger.info(
    "processing_request", request_id=request_id_var.get(), endpoint="/api/users"
)


# Use in downstream calls
async def call_external_service(url: str):
    headers = {
        "X-Request-ID": request_id_var.get(),  # Propagate ID
        "Content-Type": "application/json",
    }
    response = await http_client.post(url, headers=headers)
    return response


# Now you can trace a request across all services:
# grep "request_id=abc-123" service1.log service2.log service3.log
```

### Live Debugging (Without Stopping Services)

**Dynamic log level adjustment:**

```python
import logging
from fastapi import FastAPI, Request

app = FastAPI()


# Runtime log level control
@app.post("/admin/log-level")
async def set_log_level(logger_name: str, level: str):
    """Dynamically adjust log levels without restart"""
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper()))
    return {"logger": logger_name, "level": level}


# Usage during incident:
# curl -X POST http://localhost:8000/admin/log-level \
#   -d '{"logger_name": "app.payments", "level": "DEBUG"}'
#
# Now you get detailed payment logs without redeploying
```

**Feature flags for debugging:**

```python
from typing import Dict, Any
import os


class FeatureFlags:
    """Runtime feature toggles for debugging"""

    def __init__(self):
        self._flags = {
            "enable_payment_debug_logging": os.getenv(
                "FF_PAYMENT_DEBUG", "false"
            ).lower()
            == "true",
            "use_backup_payment_provider": False,
            "enable_request_dumping": False,
        }

    def is_enabled(self, flag: str) -> bool:
        return self._flags.get(flag, False)

    def set(self, flag: str, value: bool):
        """Dynamically enable/disable flags"""
        self._flags[flag] = value


flags = FeatureFlags()


def process_payment(amount: float):
    if flags.is_enabled("enable_payment_debug_logging"):
        logger.debug(
            "payment_debug_context",
            amount=amount,
            provider=get_payment_provider(),
            user_balance=get_user_balance(),
            recent_transactions=get_recent_transactions(limit=5),
        )

    if flags.is_enabled("use_backup_payment_provider"):
        return backup_provider.charge(amount)

    return primary_provider.charge(amount)


# API to toggle flags
@app.post("/admin/feature-flag/{flag}")
async def toggle_flag(flag: str, enabled: bool):
    flags.set(flag, enabled)
    return {"flag": flag, "enabled": enabled}


# During incident:
# curl -X POST http://localhost:8000/admin/feature-flag/use_backup_payment_provider?enabled=true
```

**Memory profiling in production:**

```python
import tracemalloc
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()


# On-demand memory profiling
@app.post("/admin/start-memory-profiling")
async def start_profiling():
    tracemalloc.start()
    return {"status": "profiling started"}


@app.get("/admin/memory-snapshot")
async def get_memory_snapshot():
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")

    return {
        "top_10_memory_allocations": [
            {
                "file": str(stat.traceback),
                "size_mb": stat.size / 1024 / 1024,
                "count": stat.count,
            }
            for stat in top_stats[:10]
        ]
    }


# Automatic heap dump on OOM
import signal
import psutil


def heap_dump_handler(signum, frame):
    """Trigger heap dump when memory exceeds threshold"""
    process = psutil.Process()
    mem_percent = process.memory_percent()

    if mem_percent > 80:
        logger.warning(f"High memory usage: {mem_percent}%")
        snapshot = tracemalloc.take_snapshot()
        snapshot.dump(f"/tmp/heap-{os.getpid()}.dump")


signal.signal(signal.SIGUSR1, heap_dump_handler)
```

### Database Query Debugging

**Slow query logging:**

```python
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - conn.info["query_start_time"].pop(-1)

    if total_time > 1.0:  # Log queries slower than 1 second
        logger.warning(
            "slow_query",
            duration_ms=total_time * 1000,
            query=statement[:200],  # Truncate long queries
            parameters=parameters,
        )


# Example output:
# {
#   "event": "slow_query",
#   "duration_ms": 2341.5,
#   "query": "SELECT * FROM orders JOIN users ON orders.user_id = users.id WHERE...",
#   "parameters": {"user_id": 12345}
# }
```

**Explain plan analysis:**

```python
from sqlalchemy import text


def analyze_query(query: str, params: dict = None):
    """Get query execution plan"""
    explain_query = f"EXPLAIN ANALYZE {query}"

    result = db.session.execute(text(explain_query), params or {})
    plan = result.fetchall()

    # Parse plan for issues
    issues = []
    for line in plan:
        if "Seq Scan" in str(line):
            issues.append("Sequential scan detected - consider adding index")
        if "cost=" in str(line):
            cost = float(str(line).split("cost=")[1].split()[0])
            if cost > 10000:
                issues.append(f"High cost operation: {cost}")

    return {
        "query": query,
        "execution_plan": [str(line) for line in plan],
        "issues": issues,
    }


# Usage:
# analysis = analyze_query(
#     "SELECT * FROM orders WHERE user_id = :user_id",
#     {"user_id": 12345}
# )
```

### Distributed Systems Debugging

**Trace-based debugging across services:**

```python
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

tracer = trace.get_tracer(__name__)
propagator = TraceContextTextMapPropagator()


# Service A: Initiate request
async def create_order(order_data: dict):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order_id", order_data["id"])

        # Save order locally
        order = await db.save_order(order_data)

        # Call inventory service with trace context
        headers = {}
        propagator.inject(headers)  # Inject trace context

        response = await http_client.post(
            "http://inventory-service/reserve",
            json={"order_id": order.id, "items": order.items},
            headers=headers,  # Propagate trace
        )

        return order


# Service B (Inventory): Continue trace
async def reserve_inventory(request):
    # Extract trace context from headers
    ctx = propagator.extract(request.headers)

    with tracer.start_as_current_span("reserve_inventory", context=ctx) as span:
        span.set_attribute("order_id", request.json["order_id"])

        # Business logic
        for item in request.json["items"]:
            await reserve_item(item)

        return {"status": "reserved"}


# Now in Jaeger/Zipkin UI, you can see:
# Trace ID: abc-123-def-456
#   ├─ create_order (Service A) - 245ms
#   │   └─ reserve_inventory (Service B) - 189ms
#   │       ├─ reserve_item (Service B) - 45ms
#   │       └─ reserve_item (Service B) - 52ms
```

**Circuit breaker debugging:**

```python
from circuitbreaker import circuit
import time


# Circuit breaker with detailed state tracking
@circuit(failure_threshold=5, recovery_timeout=60, expected_exception=ServiceError)
def call_payment_service(amount: float):
    logger.info(
        "calling_payment_service",
        amount=amount,
        circuit_state=call_payment_service.current_state,  # open/closed/half-open
        failure_count=call_payment_service.failure_count,
    )

    try:
        response = payment_client.charge(amount)
        return response
    except Exception as e:
        logger.error(
            "payment_service_error",
            error=str(e),
            circuit_state=call_payment_service.current_state,
            will_open=call_payment_service.failure_count >= 4,
        )
        raise


# Monitor circuit breaker state
@app.get("/health/circuit-breakers")
async def circuit_breaker_status():
    return {
        "payment_service": {
            "state": call_payment_service.current_state,
            "failure_count": call_payment_service.failure_count,
            "last_failure": call_payment_service.last_failure_time,
        }
    }
```

______________________________________________________________________

## Security Considerations

### Debugging Information Exposure

**Prevent sensitive data leakage:**

```python
import re
from typing import Any, Dict


class SafeDebugLogger:
    """Sanitize sensitive data before logging"""

    SENSITIVE_PATTERNS = [
        (r"\b\d{16}\b", "CARD_REDACTED"),  # Credit card
        (
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "EMAIL_REDACTED",
        ),  # Email
        (r'password["\']?\s*[:=]\s*["\']?[^"\'}\s]+', "password=REDACTED"),  # Password
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'}\s]+', "api_key=REDACTED"),  # API key
    ]

    @classmethod
    def sanitize(cls, data: Any) -> Any:
        """Recursively sanitize sensitive data"""
        if isinstance(data, dict):
            return {k: cls.sanitize(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [cls.sanitize(item) for item in data]
        elif isinstance(data, str):
            for pattern, replacement in cls.SENSITIVE_PATTERNS:
                data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
            return data
        else:
            return data

    @classmethod
    def debug(cls, message: str, **context):
        sanitized_context = cls.sanitize(context)
        logger.debug(message, **sanitized_context)


# Usage:
SafeDebugLogger.debug(
    "processing_payment",
    user_email="user@example.com",  # Will be redacted
    card_number="4532123456789012",  # Will be redacted
    amount=99.99,  # Safe to log
)
# Output: processing_payment user_email=EMAIL_REDACTED card_number=CARD_REDACTED amount=99.99
```

**Production debug endpoints protection:**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()


def verify_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Protect debug endpoints with authentication"""
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(
        credentials.password, os.getenv("ADMIN_PASSWORD", "changeme")
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Log access to debug endpoints
    logger.warning(
        "admin_endpoint_access", username=credentials.username, ip=request.client.host
    )

    return credentials.username


# Protected debug endpoint
@app.get("/admin/debug/memory", dependencies=[Depends(verify_admin_credentials)])
async def get_memory_debug():
    return get_memory_snapshot()
```

### Debugging in Multi-Tenant Systems

**Tenant isolation during debugging:**

```python
from contextvars import ContextVar

tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")


class TenantAwareDebugger:
    """Ensure debugging respects tenant boundaries"""

    @staticmethod
    def enable_debug_mode(tenant_id: str):
        """Enable debug logging for specific tenant only"""
        if tenant_id_var.get() != tenant_id:
            return  # Don't debug other tenants

        logger.setLevel(logging.DEBUG)

    @staticmethod
    def debug_query(query: str, tenant_id: str):
        """Debug query with tenant verification"""
        current_tenant = tenant_id_var.get()

        if current_tenant != tenant_id:
            raise SecurityError("Cannot debug queries for other tenants")

        return analyze_query(query)


# Usage:
@app.middleware("http")
async def tenant_context_middleware(request, call_next):
    tenant_id = request.headers.get("X-Tenant-ID")
    tenant_id_var.set(tenant_id)

    response = await call_next(request)
    return response
```

______________________________________________________________________

## Testing & Validation

### Debugging Test Failures

**Pytest debugging techniques:**

```python
import pytest

# Run pytest with debugger on failure
# pytest --pdb  # Drop into pdb on first failure
# pytest --pdbcls=IPython.terminal.debugger:TerminalPdb  # Use ipdb


# Capture and print on failure only
@pytest.fixture
def debug_on_failure(request):
    yield
    if request.node.rep_call.failed:
        # Print debugging info on failure
        print(f"\n=== DEBUG INFO FOR {request.node.name} ===")
        print(f"Locals: {request.node.funcargs}")


def test_payment_processing(debug_on_failure):
    user = create_test_user(balance=100)
    result = process_payment(user_id=user.id, amount=150)
    assert result.success  # Will print debug info if this fails


# Verbose assertion output
def test_with_detailed_assertions():
    users = get_active_users()

    # Poor: Just fails with no context
    assert len(users) == 5

    # Better: Provides context on failure
    assert len(users) == 5, (
        f"Expected 5 active users, got {len(users)}: {[u.id for u in users]}"
    )


# Parameterized test debugging
@pytest.mark.parametrize(
    "amount,expected",
    [
        (100, True),
        (1000, True),
        (10000, False),  # Fails - easier to identify which input
    ],
    ids=["small", "medium", "large"],
)
def test_payment_limits(amount, expected):
    result = can_process_payment(amount)
    assert result == expected
```

**Test isolation debugging:**

```python
import pytest
from unittest.mock import patch, MagicMock


# Track test state to debug pollution
@pytest.fixture(autouse=True)
def verify_clean_state():
    """Ensure tests don't leak state"""
    before_user_count = db.query(User).count()
    before_cache_size = len(cache.keys())

    yield  # Run test

    after_user_count = db.query(User).count()
    after_cache_size = len(cache.keys())

    if after_user_count != before_user_count:
        pytest.fail(f"Test leaked {after_user_count - before_user_count} users in DB")

    if after_cache_size != before_cache_size:
        pytest.fail(f"Test leaked {after_cache_size - before_cache_size} cache entries")


# Debug flaky tests with retries
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_potentially_flaky_api_call():
    """Re-run up to 3 times if fails"""
    response = external_api.get_data()
    assert response.status_code == 200


# Capture timing for slow tests
@pytest.fixture
def timing_tracker(request):
    start = time.time()
    yield
    duration = time.time() - start
    if duration > 1.0:
        print(f"\n⚠️  Slow test: {request.node.name} took {duration:.2f}s")
```

______________________________________________________________________

## Troubleshooting

### Common Debugging Pitfalls

**Issue 1: Heisenbug - Bug disappears when debugging**

```python
# Problem: Race condition only visible without debugger
import threading
import time


class BrokenCounter:
    def __init__(self):
        self.value = 0

    def increment(self):
        # Race condition: read-modify-write is not atomic
        temp = self.value
        time.sleep(0.0001)  # Simulate work
        self.value = temp + 1


# Fix: Use proper synchronization
import threading


class SafeCounter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.value += 1


# Alternative: Use atomic operations
from threading import Lock
from collections import Counter

counter = Counter()
counter.update(["increment"])  # Thread-safe
```

**Issue 2: Logging changes behavior (performance/timing)**

```python
# Problem: Adding logging makes problem disappear
def process_batch(items):
    for item in items:
        # Adding this log statement changes timing
        logger.debug(f"Processing {item.id}")  # Adds delay
        process_item(item)


# Solution: Use sampling for high-volume logging
import random


def process_batch(items):
    for item in items:
        # Only log 1% of items
        if random.random() < 0.01:
            logger.debug(f"Processing sample item {item.id}")
        process_item(item)


# Or use metrics instead of logs
items_processed = metrics.counter("items_processed_total")


def process_batch(items):
    for item in items:
        process_item(item)
        items_processed.inc()  # Minimal overhead
```

**Issue 3: Cannot reproduce locally**

```python
# Debugging checklist for environment-specific bugs:


class EnvironmentDebugger:
    """Compare local vs production environment"""

    @staticmethod
    def capture_environment_context():
        import platform
        import sys
        import os

        return {
            # System info
            "python_version": sys.version,
            "platform": platform.platform(),
            "hostname": platform.node(),
            # Dependencies
            "dependencies": {pkg: version for pkg, version in pip_freeze_output()},
            # Environment variables
            "env_vars": {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("SECRET_")  # Don't leak secrets
            },
            # Configuration
            "config": {
                "database_url": os.getenv("DATABASE_URL", "").split("@")[
                    -1
                ],  # Redact credentials
                "cache_backend": os.getenv("CACHE_BACKEND"),
                "debug_mode": os.getenv("DEBUG", "false"),
            },
            # Resource limits
            "limits": {
                "max_memory": resource.getrlimit(resource.RLIMIT_AS),
                "max_files": resource.getrlimit(resource.RLIMIT_NOFILE),
            },
        }


# Add to error reports
try:
    process_payment(order_id)
except Exception as e:
    logger.error(
        "payment_processing_error",
        error=str(e),
        environment_context=EnvironmentDebugger.capture_environment_context(),
    )
    raise
```

**Issue 4: Intermittent failures**

```python
import time
from functools import wraps


def debug_retry(max_attempts=10, delay=0.1):
    """Decorator to retry and collect failure patterns"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            failures = []

            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)

                    if failures:
                        # We had failures before success
                        logger.warning(
                            "intermittent_failure_pattern",
                            function=func.__name__,
                            failure_rate=len(failures) / attempt,
                            failures=failures,
                            succeeded_on_attempt=attempt + 1,
                        )

                    return result

                except Exception as e:
                    failures.append(
                        {
                            "attempt": attempt + 1,
                            "error": str(e),
                            "timestamp": time.time(),
                        }
                    )

                    if attempt == max_attempts - 1:
                        # All attempts failed
                        logger.error(
                            "consistent_failure_after_retries",
                            function=func.__name__,
                            failures=failures,
                        )
                        raise

                    time.sleep(delay)

        return wrapper

    return decorator


# Usage:
@debug_retry(max_attempts=10)
def flaky_api_call():
    response = external_service.get_data()
    return response.json()


# Example output if intermittent:
# {
#   "event": "intermittent_failure_pattern",
#   "function": "flaky_api_call",
#   "failure_rate": 0.3,  # Failed 3 out of 10 attempts
#   "failures": [
#     {"attempt": 2, "error": "ConnectionTimeout", "timestamp": 1633024800},
#     {"attempt": 5, "error": "ConnectionTimeout", "timestamp": 1633024802},
#     {"attempt": 7, "error": "ConnectionTimeout", "timestamp": 1633024804}
#   ],
#   "succeeded_on_attempt": 8
# }
```

### Performance Debugging

**CPU profiling:**

```python
import cProfile
import pstats
from io import StringIO


def profile_function(func):
    """Decorator to profile function execution"""

    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()

        result = func(*args, **kwargs)

        profiler.disable()

        # Print stats
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(20)  # Top 20 functions

        logger.info(f"Profile for {func.__name__}:\n{s.getvalue()}")
        return result

    return wrapper


@profile_function
def expensive_operation():
    return process_large_dataset()


# Alternative: Line-by-line profiling
from line_profiler import LineProfiler


def profile_line_by_line():
    lp = LineProfiler()
    lp.add_function(expensive_operation)
    lp.run("expensive_operation()")
    lp.print_stats()
```

**Memory leak detection:**

```python
import gc
import sys
from collections import defaultdict


class MemoryLeakDetector:
    """Track object growth to find memory leaks"""

    def __init__(self):
        self.snapshots = []

    def take_snapshot(self):
        """Capture current object counts"""
        gc.collect()  # Force garbage collection first

        counts = defaultdict(int)
        for obj in gc.get_objects():
            counts[type(obj).__name__] += 1

        self.snapshots.append(counts)
        return counts

    def compare_snapshots(self, snapshot1_idx=0, snapshot2_idx=-1):
        """Compare two snapshots to find growing objects"""
        s1 = self.snapshots[snapshot1_idx]
        s2 = self.snapshots[snapshot2_idx]

        growth = {}
        for obj_type in s2:
            delta = s2[obj_type] - s1.get(obj_type, 0)
            if delta > 0:
                growth[obj_type] = delta

        # Sort by growth
        return sorted(growth.items(), key=lambda x: x[1], reverse=True)


# Usage:
detector = MemoryLeakDetector()

detector.take_snapshot()  # Baseline

# Run suspect code
for i in range(1000):
    process_request()

detector.take_snapshot()  # After load

# Check for leaks
leaks = detector.compare_snapshots()
print("Top 10 growing object types:")
for obj_type, count in leaks[:10]:
    print(f"{obj_type}: +{count} objects")

# Example output:
# dict: +5423 objects  ← Potential leak
# list: +2341 objects
# tuple: +891 objects
```

______________________________________________________________________

## Related Tools & Resources

- **distributed-tracing-setup.md** - Comprehensive OpenTelemetry instrumentation
- **monitor-setup.md** - Prometheus/Grafana monitoring configuration
- **observability-lifecycle.md** - High-level observability process guide
- **observability-incident-lead agent** - Specialized performance optimization assistance
- **devops-troubleshooter agent** - Production incident response expertise

______________________________________________________________________

## Summary

This guide provides comprehensive debugging strategies from local development to production systems:

1. **Systematic Approaches**: Scientific method, binary search, rubber duck debugging
1. **Tool Mastery**: Language-specific debuggers (pdb, Chrome DevTools, delve, gdb)
1. **Production Techniques**: Observability-driven debugging, live debugging, distributed tracing
1. **Security**: Sensitive data sanitization, protected debug endpoints, tenant isolation
1. **Testing**: Test failure debugging, isolation verification, flaky test handling
1. **Troubleshooting**: Heisenbugs, environment mismatches, intermittent failures, performance

**Key Principles:**

- Always debug systematically with hypotheses and evidence
- Use observability (logs, metrics, traces) for production debugging
- Protect sensitive data in debug output
- Validate fixes thoroughly before deployment
- Document learnings to prevent recurrence

This consolidated guide replaces `debug-monitoring.md` and `advanced-debugging.md` with production-ready debugging practices.
