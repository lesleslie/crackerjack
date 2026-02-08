# Phase 2.1: Regex Pattern Precompilation

## Performance Audit Findings

- **108 inline regex calls** across 25 files
- **High-frequency patterns** in `test_manager.py` (12 patterns, 1000+ calls/run)
- **High-frequency patterns** in parsers (5 patterns)
- **Expected improvement**: 40-60% faster regex parsing

## Existing Infrastructure

Crackerjack has a comprehensive pattern registry system at `crackerjack/services/patterns/`:

- `__init__.py` - Merges all pattern categories into `SAFE_PATTERNS`
- `core.py` - `ValidatedPattern`, `CompiledPatternCache`
- `operations.py` - `RegexPatternsService` with safe pattern application
- Category modules: `formatting`, `testing`, `tool_output`, `security`, etc.

## Implementation Strategy

### Phase 1: High-Frequency Files (Priority)

#### 1.1 test_manager.py (12 inline patterns)

**Current inline patterns:**
```python
# Line 572-574: Summary patterns (3 patterns)
re.search(r"=+\s+(.+?)\s+in\s+([\d.]+)s?\s*=+", output)
re.search(r"(\d+\s+\w+)+\s+in\s+([\d.]+)s?", output)
re.search(r"(\d+.*)in\s+([\d.]+)s?", output)

# Line 597: Metric pattern
re.search(rf"(\d+)\s+{metric}", summary_text, re.IGNORECASE)

# Line 605: Collected pattern
re.search(r"(\d+)\s+collected", summary_text, re.IGNORECASE)

# Line 1236: Failure match pattern
re.match(r"^(.+?)\s+(FAILED|ERROR|SKIPPED|SKIP)", line)

# Line 1240: Coverage percentage pattern
re.sub(r"\s*\[[\s\d]+%\]$", "", test_path)

# Line 1271: Location pattern
re.match(r"^(.+?\.py):(\d+):\s*(.*)$", line)

# Line 1422: Summary failure pattern
re.match(r"^FAILED\s+(.+?)\s+-\s+(.+)$", line)

# Line 1425: Ellipsis pattern
re.sub(r"\.\.\.$", "", error_message)

# Line 1429: FAILED pattern
re.search(r"FAILED\s+(.+?)\s+-", line)
```

**Precompiled version:**
```python
# At module level (after line 30)
SUMMARY_PATTERNS = [
    re.compile(r"=+\s+(.+?)\s+in\s+([\d.]+)s?\s*=+"),
    re.compile(r"(\d+\s+\w+)+\s+in\s+([\d.]+)s?"),
    re.compile(r"(\d+.*)in\s+([\d.]+)s?"),
]

METRIC_PATTERN = re.compile(r"(\d+)\s+(\w+)", re.IGNORECASE)
COLLECTED_PATTERN = re.compile(r"(\d+)\s+collected", re.IGNORECASE)
FAILURE_MATCH_PATTERN = re.compile(r"^(.+?)\s+(FAILED|ERROR|SKIPPED|SKIP)")
COVERAGE_PERCENTAGE_PATTERN = re.compile(r"\s*\[[\s\d]+%\]$")
LOCATION_PATTERN = re.compile(r"^(.+?\.py):(\d+):\s*(.*)$")
SUMMARY_FAILURE_PATTERN = re.compile(r"^FAILED\s+(.+?)\s+-\s+(.+)$")
ELLIPSIS_PATTERN = re.compile(r"\.\.\.$")
FAILED_PATTERN = re.compile(r"FAILED\s+(.+?)\s+-")
```

**Usage changes:**
```python
# Before
match = re.search(pattern, output)

# After
match = SUMMARY_PATTERNS[0].search(output)
```

#### 1.2 regex_parsers.py (5 inline patterns)

**Current inline patterns:**
```python
# Line 204: File count pattern
re.search(r"(\d+) files?", output)

# Line 491: Paren pattern
re.search(r"\(([^)]+)\)", line)

# Line 639: Line pattern
re.search(r"line (\d+)", message)

# Line 733: Code match pattern
re.match(r"^([A-Z]+\d+)\s+(.+)$", code_line)

# Line 740: Arrow match pattern
re.search(r"-->\s+(\S+):(\d+):(\d+)", arrow_line)
```

**Precompiled version:**
```python
# At module level
FILE_COUNT_PATTERN = re.compile(r"(\d+) files?")
PAREN_PATTERN = re.compile(r"\(([^)]+)\)")
LINE_PATTERN = re.compile(r"line (\d+)")
CODE_MATCH_PATTERN = re.compile(r"^([A-Z]+\d+)\s+(.+)$")
ARROW_MATCH_PATTERN = re.compile(r"-->\s+(\S+):(\d+):(\d+)")
```

### Phase 2: Medium-Frequency Files

#### 2.1 Other high-frequency files

- `agents/dependency_agent.py` (5 patterns)
- `agents/import_optimization_agent.py` (4 patterns)
- `executors/hook_executor.py` (2 patterns)
- `executors/async_hook_executor.py` (1 pattern)

### Phase 3: Low-Frequency Files

- Files with 1-2 regex calls (precompile for consistency)
- Files using dynamic patterns (keep inline if truly dynamic)

## Performance Measurement

### Benchmark Plan

```python
# Benchmark script to measure improvement
import timeit
import re

# Inline version
def inline_regex(text):
    return re.search(r"(\d+)\s+collected", text, re.IGNORECASE)

# Precompiled version
COLLECTED_PATTERN = re.compile(r"(\d+)\s+collected", re.IGNORECASE)

def precompiled_regex(text):
    return COLLECTED_PATTERN.search(text)

# Benchmark
test_text = "150 collected in 2.5s"
inline_time = timeit.timeit(lambda: inline_regex(test_text), number=10000)
precompiled_time = timeit.timeit(lambda: precompiled_regex(test_text), number=10000)

print(f"Inline: {inline_time:.4f}s")
print(f"Precompiled: {precompiled_time:.4f}s")
print(f"Improvement: {(inline_time - precompiled_time) / inline_time * 100:.1f}%")
```

**Expected Results:**
- Inline: ~2.5ms for 10k calls
- Precompiled: ~1.0ms for 10k calls
- **Improvement: 60%**

## Implementation Checklist

- [ ] Precompile patterns in `test_manager.py` (12 patterns)
- [ ] Precompile patterns in `regex_parsers.py` (5 patterns)
- [ ] Precompile patterns in `dependency_agent.py` (5 patterns)
- [ ] Precompile patterns in `import_optimization_agent.py` (4 patterns)
- [ ] Precompile patterns in `hook_executor.py` (2 patterns)
- [ ] Precompile patterns in `async_hook_executor.py` (1 pattern)
- [ ] Precompile patterns in other medium-frequency files
- [ ] Run performance benchmarks
- [ ] Verify all quality checks pass
- [ ] Update documentation

## Verification

After implementation:

1. **Run quality checks:**
   ```bash
   python -m crackerjack run --run-tests -c
   ```

2. **Run performance benchmark:**
   ```bash
   python scripts/benchmark_regex_precompilation.py
   ```

3. **Verify no regressions:**
   - All tests pass
   - No new complexity issues
   - No import errors

## Expected Impact

- **test_manager.py**: 40-60% faster regex operations (1000+ calls/run)
- **regex_parsers.py**: 40-60% faster regex operations (hundreds of calls/run)
- **Overall**: 5-10% faster test execution time
- **Memory**: Negligible increase (patterns are singleton objects)

## Notes

- Precompiled patterns are module-level singletons (no memory overhead per instance)
- Pattern compilation happens at import time (one-time cost)
- All existing functionality preserved (API unchanged)
- No breaking changes (internal optimization only)
