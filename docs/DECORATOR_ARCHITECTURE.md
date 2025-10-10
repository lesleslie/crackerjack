# Decorator-Based Error Handling Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Crackerjack Application                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               Decorator-Based Error Handling                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   @retry     │  │  @timeout    │  │ @handle_     │         │
│  │              │  │              │  │  errors      │         │
│  │ • Exponential│  │ • Async wait │  │ • Transform  │         │
│  │   backoff    │  │ • Signal     │  │ • Fallback   │         │
│  │ • Exception  │  │   alarm      │  │ • Suppress   │         │
│  │   filtering  │  │ • Custom msg │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ @validate_   │  │  @log_       │  │ @graceful_   │         │
│  │  args        │  │   errors     │  │  degradation │         │
│  │              │  │              │  │              │         │
│  │ • Type check │  │ • Context    │  │ • Fallback   │         │
│  │ • Validators │  │ • Traceback  │  │ • Warning    │         │
│  │ • Multiple   │  │ • Logging    │  │ • Suppress   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────┐                                              │
│  │ @cache_      │                                              │
│  │  errors      │                                              │
│  │              │                                              │
│  │ • Pattern    │                                              │
│  │   detection  │                                              │
│  │ • Auto-fix   │                                              │
│  └──────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ integrates with
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Existing Crackerjack Infrastructure                │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   errors.py  │  │ ErrorHandling│  │ ErrorCache   │         │
│  │              │  │    Mixin     │  │              │         │
│  │ • Exception  │  │              │  │ • Pattern    │         │
│  │   classes    │  │ • Subprocess │  │   storage    │         │
│  │ • ErrorCode  │  │ • File ops   │  │ • Frequency  │         │
│  │   enum       │  │ • Timeout    │  │ • Auto-fix   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐                           │
│  │ Rich Console │  │   Logging    │                           │
│  │              │  │              │                           │
│  │ • Formatting │  │ • Structured │                           │
│  │ • Progress   │  │ • Context    │                           │
│  │ • Panels     │  │ • Levels     │                           │
│  └──────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Decorator Composition Flow

```
User Function
     │
     ▼
┌─────────────────────────────────────┐
│  @with_timeout(seconds=60)          │ ◄── Outermost: Timeout enforcement
│  │                                  │
│  │  ┌──────────────────────────┐   │
│  │  │ @retry(max_attempts=3)   │   │ ◄── Retry on failure
│  │  │  │                       │   │
│  │  │  │  ┌────────────────┐  │   │
│  │  │  │  │ @log_errors()  │  │   │ ◄── Log errors
│  │  │  │  │  │            │  │   │
│  │  │  │  │  │  ┌──────┐  │  │   │
│  │  │  │  │  │  │ func │  │  │   │ ◄── Original function
│  │  │  │  │  │  └──────┘  │  │   │
│  │  │  │  │  │            │  │   │
│  │  │  │  │  Return/Error  │  │   │
│  │  │  │  └────────────────┘  │   │
│  │  │  │                       │   │
│  │  │  Retry if needed         │   │
│  │  └──────────────────────────┘   │
│  │                                  │
│  Timeout if exceeded               │
└─────────────────────────────────────┘
     │
     ▼
Return to caller
```

## Data Flow for Error Handling

```
Function Call
     │
     ▼
┌─────────────────────────────────────┐
│  Decorator Stack Entry              │
│  • Validate arguments               │
│  • Set timeout timer                │
│  • Start retry counter              │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│  Function Execution                 │
└─────────────────────────────────────┘
     │
     ├──► Success ─────────────────────┐
     │                                 │
     ▼                                 ▼
┌─────────────────────────────────────┐
│  Error Occurred                     │   Return result
│  • TimeoutError                     │   to caller
│  • ValidationError                  │
│  • NetworkError                     │
│  • FileError                        │
│  • etc.                             │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│  Error Handling Decision Tree       │
│                                     │
│  1. Log error (if @log_errors)      │
│  2. Cache pattern (if @cache_errors)│
│  3. Check retry (if @retry)         │
│     ├─ Retries left? → Retry        │
│     └─ No retries → Continue        │
│  4. Transform (if @handle_errors)   │
│  5. Fallback (if graceful_degradation)│
└─────────────────────────────────────┘
     │
     ├──► Retry ────────────────────► Back to execution
     │
     ├──► Fallback ──────────────────┐
     │                                │
     ▼                                ▼
┌─────────────────────────────────────┐
│  Re-raise or Suppress               │   Return fallback
│  • Original exception               │   value
│  • Transformed exception            │
│  • Suppressed (return None/fallback)│
└─────────────────────────────────────┘
```

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                      │
│  • WorkflowOrchestrator                                     │
│  • Managers (HookManager, PublishManager, etc.)             │
│  • Coordinators (PhaseCoordinator, SessionCoordinator)      │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ uses decorators
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Decorator Layer                          │
│  Function-level error handling                              │
│  • @retry, @timeout, @validate_args                         │
│  • @handle_errors, @log_errors                              │
│  • Composable, type-safe, async-aware                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ complements
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Mixin Layer                              │
│  Class-level error handling utilities                       │
│  • ErrorHandlingMixin                                       │
│  • Common error patterns                                    │
│  • Shared error handling methods                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ uses
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│  • CrackerjackError hierarchy (errors.py)                   │
│  • ErrorCache (pattern detection)                           │
│  • Rich Console (beautiful output)                          │
│  • Logging (structured logging)                             │
└─────────────────────────────────────────────────────────────┘
```

## Decision Matrix: When to Use Each Decorator

```
┌─────────────────────────┬──────────────────────────────────────┐
│  Use Case               │  Recommended Decorator(s)            │
├─────────────────────────┼──────────────────────────────────────┤
│ Network operations      │  @retry + @with_timeout              │
│ File I/O                │  @handle_errors + @log_errors        │
│ Database queries        │  @with_timeout + @retry              │
│ Optional features       │  @graceful_degradation               │
│ Critical operations     │  @validate_args + @handle_errors     │
│ External API calls      │  @retry + @cache_errors              │
│ User input validation   │  @validate_args                      │
│ Background tasks        │  @log_errors + @graceful_degradation │
│ Subprocess execution    │  @with_timeout + @handle_errors      │
│ Configuration loading   │  @handle_errors (fallback={})        │
└─────────────────────────┴──────────────────────────────────────┘
```

## Performance Characteristics

```
┌──────────────────────┬──────────┬────────────┬──────────────┐
│  Decorator           │ Overhead │ Memory     │ Async Support│
├──────────────────────┼──────────┼────────────┼──────────────┤
│ @retry               │  ~2μs    │ Minimal    │  ✅          │
│ @with_timeout        │  ~1μs    │ Minimal    │  ✅          │
│ @handle_errors       │  ~1μs    │ Minimal    │  ✅          │
│ @log_errors          │  ~3μs    │ Low        │  ✅          │
│ @validate_args       │  ~5μs    │ Low        │  ✅          │
│ @graceful_degradation│  ~1μs    │ Minimal    │  ✅          │
│ @cache_errors        │  ~10μs   │ Medium     │  ✅          │
├──────────────────────┼──────────┼────────────┼──────────────┤
│ Stacked (3 deep)     │  ~7μs    │ Minimal    │  ✅          │
└──────────────────────┴──────────┴────────────┴──────────────┘
```

## Error Transformation Pipeline

```
Original Exception
     │
     ▼
┌──────────────────────────────────────┐
│  Exception Type Detection            │
│  • isinstance checks                 │
│  • Type matching                     │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  Context Extraction                  │
│  • Function name                     │
│  • Module                            │
│  • Parameters                        │
│  • Stack trace                       │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  Pattern Detection (@cache_errors)   │
│  • Error message parsing             │
│  • Pattern identification            │
│  • Frequency tracking                │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  Transformation (@handle_errors)     │
│  • Wrap in CrackerjackError          │
│  • Add context details               │
│  • Set error code                    │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  Logging (@log_errors)               │
│  • Structured logging                │
│  • Context inclusion                 │
│  • Level selection                   │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  Output Decision                     │
│  ├─ Re-raise exception               │
│  ├─ Return fallback value            │
│  └─ Suppress (return None)           │
└──────────────────────────────────────┘
```

## Type Safety Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Type Annotations                         │
│  • Full type hints on all decorators                        │
│  • Generic types (TypeVar, Callable)                        │
│  • Protocol support                                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Static Analysis                           │
│  • Pyright validation                                       │
│  • Ruff type checking                                       │
│  • IDE autocomplete                                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Runtime Validation                         │
│  • @validate_args type checking                             │
│  • Exception type filtering                                 │
│  • Async function detection                                 │
└─────────────────────────────────────────────────────────────┘
```

## Extension Points

Future decorators can be added to the system:

```
┌──────────────────────────────────────────────────────────────┐
│  Potential Future Decorators                                 │
│                                                              │
│  • @circuit_breaker   - Prevent cascading failures          │
│  • @rate_limit        - Rate limiting                        │
│  • @metrics           - Metric collection                    │
│  • @cache_result      - Result caching                       │
│  • @lock              - Resource locking                     │
│  • @deprecate         - Deprecation warnings                 │
│  • @benchmark         - Performance benchmarking             │
│  • @trace             - Distributed tracing                  │
└──────────────────────────────────────────────────────────────┘
```

All following the same patterns:
- Type-safe
- Async/sync support
- Composable
- Rich integration
- Comprehensive tests
