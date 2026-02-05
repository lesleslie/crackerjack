# BatchProcessor Troubleshooting Guide

**Version**: 1.0
**Last Updated**: 2026-02-05

---

## Table of Contents

1. [Common Errors](#common-errors)
2. [Performance Issues](#performance-issues)
3. [Agent-Specific Issues](#agent-specific-issues)
4. [Debugging Techniques](#debugging-techniques)
5. [Getting Help](#getting-help)

---

## Common Errors

### Error 1: "Unknown agent"

**Symptom**:
```
ValueError: Unknown agent: DependencyAgent
```

**Cause**: Agent not registered in `BatchProcessor._get_agent()` method

**Solution**:
1. Check if agent exists: `crackerjack/agents/<agent>_name.py`
2. Verify agent is imported in batch_processor.py
3. Add agent to `_get_agent()` method:

```python
elif agent_name == "DependencyAgent":
    from crackerjack.agents.dependency_agent import DependencyAgent
    self._agents[agent_name] = DependencyAgent(self.context)
```

**Status**: ✅ Fixed in version 1.0

---

### Error 2: "No module named 'async_file_io'"

**Symptom**:
```
ImportError: cannot import name 'async_read_file' from 'crackerjack.services.async_file_io'
```

**Cause**: `async_file_io.py` not found or not in Python path

**Solution**:
1. Verify file exists: `crackerjack/services/async_file_io.py`
2. Check it's importable:
```bash
python -c "from crackerjack.services.async_file_io import async_read_file; print('OK')"
```

**Status**: ✅ Included in distribution

---

### Error 3: "AttributeError: 'BatchIssueResult' object has no attribute 'results'"

**Symptom**:
```
AttributeError: 'BatchIssueResult' object has no attribute 'results'
```

**Cause**: Variable shadowing in batch_processor.py

**Solution**: Fixed in version 1.0 - renamed inner variable to `issue_result`

**Status**: ✅ Fixed in version 1.0

---

### Error 4: Low Fix Rate (<50%)

**Symptom**: Most issues marked as skipped or failed

**Possible Causes**:

#### Cause 4A: Issue Type Not Supported

**Diagnosis**:
```python
# Check issue type
print(issue.type)  # Should be in IssueType enum

# Check if type has agents
from crackerjack.agents.coordinator import ISSUE_TYPE_TO_AGENTS
print(ISSUE_TYPE_TO_AGENTS.get(issue.type, []))
```

**Solution**: Only use supported issue types (see User Guide for list)

#### Cause 4B: Agent Confidence Too Low

**Diagnosis**:
```python
# Enable logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check agent confidence
for agent_name in ISSUE_TYPE_TO_AGENTS.get(issue.type, []):
    agent = processor._get_agent(agent_name)
    confidence = await agent.can_handle(issue)
    print(f"{agent_name}: {confidence:.2f}")
```

**Solution**:
- Confidence < 0.7: Agent won't attempt fix
- This is expected behavior - agent unsure it can fix

#### Cause 4C: Files Don't Exist

**Diagnosis**:
```python
# Check file paths
for issue in issues:
    path = Path(issue.file_path)
    if not path.exists():
        print(f"File not found: {issue.file_path}")
```

**Solution**: Ensure file paths are correct before processing

---

### Error 5: Batch Processing Hangs

**Symptom**: Processing never completes, console output stops

**Possible Causes**:

#### Cause 5A: Blocking Operation

**Diagnosis**: Check if agent is doing blocking I/O

**Solution**: Use async I/O methods:
```python
# Instead of:
content = context.get_file_content(file_path)

# Use:
content = await context.async_get_file_content(file_path)
```

#### Cause 5B: Infinite Loop in Agent

**Diagnosis**: Agent stuck in loop

**Solution**:
1. Enable debug logging
2. Check agent logs for repeated patterns
3. Report bug if found

---

## Performance Issues

### Issue 1: Slow Processing (>60s for 10 issues)

**Diagnosis**:
```python
print(f"Duration: {result.duration_seconds:.1f}s")
print(f"Issues: {result.total_issues}")
print(f"Avg: {result.duration_seconds / result.total_issues:.1f}s/issue")
```

**Possible Solutions**:

#### Solution 1A: Enable Async I/O

**Problem**: Sync I/O blocks event loop

**Fix**: Ensure agents use `async_get_file_content()`:

```python
# Check agent code
content = await self.context.async_get_file_content(file_path)
```

**Expected Improvement**: 3x speedup

#### Solution 1B: Increase Parallelism

**Problem**: Not enough concurrent agents

**Fix**: Increase `max_parallel`:

```python
processor = get_batch_processor(context, console, max_parallel=5)
```

**Expected Improvement**: 1.5-2x speedup

#### Solution 1C: Skip Slow Agents

**Problem**: TestCreationAgent is slow (6.9s per issue)

**Workaround**: Filter out test failures if not critical:

```python
issues = [i for i in issues if i.type != IssueType.TEST_FAILURE]
```

**Expected Improvement**: 2-3x speedup for mixed issues

---

### Issue 2: Memory Usage Too High

**Symptom**: >500MB memory usage during processing

**Diagnosis**:
```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f}MB")
```

**Possible Causes**:

#### Cause 2A: Large Batch Size

**Solution**: Process in smaller batches:

```python
# Instead of processing 100 issues at once
batch_size = 20
for i in range(0, len(issues), batch_size):
    batch = issues[i:i+batch_size]
    result = await processor.process_batch(issues=batch)
```

#### Cause 2B: Large Files in Memory

**Solution**: Increase file size limit or skip large files:

```python
# Skip large files
MAX_FILE_SIZE = 1_000_000  # 1MB
issues = [i for i in issues if Path(i.file_path).stat().st_size < MAX_FILE_SIZE]
```

---

## Agent-Specific Issues

### ImportOptimizationAgent

#### Issue: Import Not Added

**Symptom**: Agent says it fixed import, but import still missing

**Diagnosis**:
1. Check if file was actually modified
2. Verify import was added to correct location

**Solution**: Agent adds imports alphabetically. Check file manually.

---

### TestSpecialistAgent

#### Issue: Fixture Not Created

**Symptom**: Agent says fixture created, but still not found

**Diagnosis**:
```bash
# Check if conftest.py exists
ls -la tests/conftest.py

# Check fixture is defined
grep -n "def tmp_path" tests/conftest.py
```

**Possible Causes**:
1. Wrong conftest.py location
2. Fixture name mismatch
3. Pytest not discovering tests

**Solution**:
- Ensure conftest.py in tests/ directory
- Verify fixture name matches test usage
- Run `pytest --collect-only` to check discovery

---

### TestCreationAgent

#### Issue: Slow Processing

**Symptom**: 6-9 seconds per issue

**Cause**: Pytest discovery is expensive

**Current Status**: ⚠️ Known limitation, caching planned for v1.1

**Workaround**:
- Process test failures separately
- Limit number of test issues per batch
- Use sequential mode for better visibility

---

### DeadCodeRemovalAgent

#### Issue: Code Not Removed

**Symptom**: Agent reports success, but code still there

**Diagnosis**:
```bash
# Check if vulture detected it
python -m vulture crackerjack/

# Check confidence score
# Agent requires ≥80% confidence for auto-removal
```

**Possible Causes**:
1. Decorator protection (agent won't remove decorated code)
2. Low confidence (<80%)
3. In __all__ exports (public API)

**Solution**: This is safety behavior - remove manually if needed

---

## Debugging Techniques

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Run batch processing
result = await processor.process_batch(issues=issues)
```

### Profile Single Issue

```python
import cProfile
import pstats

async def debug_single_issue(issue: Issue):
    """Profile single issue processing."""
    profiler = cProfile.Profile()
    profiler.enable()

    result = await processor._process_single_issue(issue, max_retries=2)

    profiler.disable()

    # Print top 20 functions
    ps = pstats.Stats(profiler)
    ps.sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(20)

    return result
```

### Check Agent Selection

```python
async def debug_agent_selection(issue: Issue):
    """Debug which agents are selected."""
    from crackerjack.agents.coordinator import ISSUE_TYPE_TO_AGENTS

    agent_names = ISSUE_TYPE_TO_AGENTS.get(issue.type, [])

    print(f"Issue type: {issue.type}")
    print(f"Candidate agents: {agent_names}")

    for agent_name in agent_names:
        agent = processor._get_agent(agent_name)
        confidence = await agent.can_handle(issue)
        print(f"  {agent_name}: {confidence:.2f}")

        if confidence >= 0.7:
            print(f"    ✓ Selected (confidence ≥0.7)")
        else:
            print(f"    ✗ Skipped (confidence <0.7)")
```

### Trace File Operations

```python
# Monkey-patch to trace file operations
import pathlib

original_read_text = pathlib.Path.read_text

def traced_read_text(self):
    print(f"[TRACE] Reading: {self}")
    return original_read_text(self)

pathlib.Path.read_text = traced_read_text

# Run batch processing
result = await processor.process_batch(issues=issues)

# Restore
pathlib.Path.read_text = original_read_text
```

---

## Getting Help

### Information to Gather

When reporting issues, collect:

1. **Error Message**: Full traceback
2. **Issue Details**: Issue type, file path, message
3. **Configuration**: max_retries, parallel setting
4. **Environment**: Python version, OS
5. **Logs**: Debug logging output

### Minimum Reproducible Example

```python
"""Minimal reproducible example."""
import asyncio
from pathlib import Path
from rich.console import Console

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.services.batch_processor import get_batch_processor


async def main():
    context = AgentContext(Path.cwd())
    console = Console()
    processor = get_batch_processor(context, console)

    issue = Issue(
        type=IssueType.IMPORT_ERROR,
        severity=Priority.MEDIUM,
        message="ModuleNotFoundError: No module named 'test'",
        file_path="test.py",
        line_number=1,
    )

    result = await processor.process_batch(
        issues=[issue],
        batch_id="debug_test",
    )

    print(f"Status: {result.status}")
    print(f"Success: {result.successful}")


asyncio.run(main())
```

### Where to Get Help

1. **Documentation**:
   - User Guide: `docs/BATCHPROCESSOR_USER_GUIDE.md`
   - Implementation Status: `docs/IMPLEMENTATION_STATUS.md`

2. **Source Code**:
   - BatchProcessor: `crackerjack/services/batch_processor.py`
   - Agent Base: `crackerjack/agents/base.py`
   - Coordinator: `crackerjack/agents/coordinator.py`

3. **Tests**:
   - Validation: `test_batch_processor_validation.py`
   - Comprehensive: `test_comprehensive_batch_processor.py`

4. **Issues**: GitHub repository issue tracker

### Common Solutions Quick Reference

| Problem | Solution |
|---------|----------|
| Unknown agent error | Add agent to `BatchProcessor._get_agent()` |
| Slow processing | Use async I/O, increase max_parallel |
| Low fix rate | Check issue types, verify file paths |
| Memory high | Process in smaller batches |
| Import errors | Verify async_file_io.py exists |
| Fixture not found | Check conftest.py location |
| Code not removed | Safety feature (decorators, exports) |
| Processing hangs | Check for blocking operations |

---

**Status**: Production Ready ✅
**Last Reviewed**: 2026-02-05
**Maintainer**: Crackerjack Development Team
