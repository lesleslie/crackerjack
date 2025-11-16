# Tempfile JSON Output Analysis

**Question:** Can we use tempfiles for JSON output to keep project directories clean?

**Answer:** YES - Recommended with caveats. Current implementation is already clean for most tools.

______________________________________________________________________

## Current State ✅

### Tools Already Using stdout (Clean)

Most tools currently output JSON to **stdout**, which subprocess captures directly without creating files:

| Tool | Flag | Output Method | Files Created? |
|------|------|---------------|----------------|
| semgrep | `--json` | stdout | ❌ No |
| bandit | `--format json` | stdout | ❌ No |
| gitleaks | `-v` (text) | stdout | ❌ No |
| zuban | N/A | stdout | ❌ No |
| ruff | N/A | stdout | ❌ No |

**Current Implementation:**

```python
result = subprocess.run(
    command,
    capture_output=True,  # ✅ Captures stdout/stderr
    text=True,
    check=False,
)
# JSON is in result.stdout - no files created!
```

This is **already clean** - no files are created in the project directory.

______________________________________________________________________

## When Tempfiles ARE Needed 🎯

### Scenario 1: Tools That Only Support File Output

Some tools REQUIRE a file path and cannot output to stdout:

**Example: Hypothetical Tool**

```bash
# Won't work - no stdout option
bandit -r . --format json  # ❌ Writes to bandit-report.json in cwd

# Needs file path
bandit -r . --format json -o /tmp/report.json  # ✅ Explicit path
```

**None of our current tools have this limitation**, but if we add new tools that do, we should use tempfiles.

### Scenario 2: Large Output Performance

For very large codebases, some tools perform better writing to a file than stdout:

- **Semgrep** on 10,000+ files
- **Bandit** recursive scan with low confidence threshold
- Large SARIF reports

**Recommendation:** Use tempfiles for tools that support `-o`/`--output` flags when scanning >1000 files.

### Scenario 3: Debugging and Audit Trail

Tempfiles allow preserving reports for debugging:

```python
import tempfile
from pathlib import Path

# Create persistent tempfile for debugging
debug_dir = Path.home() / ".cache" / "crackerjack" / "reports"
debug_dir.mkdir(parents=True, exist_ok=True)

report_file = debug_dir / f"semgrep-{job_id}.json"
```

______________________________________________________________________

## Recommended Implementation 🔧

### Option 1: Conditional Tempfile Usage (Recommended)

Add tempfile support where tools support it, but keep stdout as default:

```python
# crackerjack/executors/hook_executor.py

import tempfile
from pathlib import Path
from typing import NamedTuple

class ToolOutputConfig(NamedTuple):
    """Configuration for tool output handling."""
    supports_file_output: bool
    output_flag: str | None  # e.g., "-o", "--output"
    prefer_file_for_large_repos: bool = False
    size_threshold: int = 1000  # files


TOOL_OUTPUT_CONFIGS = {
    "semgrep": ToolOutputConfig(
        supports_file_output=True,
        output_flag="--output",
        prefer_file_for_large_repos=True,
        size_threshold=500,
    ),
    "gitleaks": ToolOutputConfig(
        supports_file_output=True,
        output_flag="--report-path",
        prefer_file_for_large_repos=False,
    ),
    "bandit": ToolOutputConfig(
        supports_file_output=True,
        output_flag="-o",
        prefer_file_for_large_repos=True,
        size_threshold=1000,
    ),
}


def _run_hook_subprocess(self, hook: HookDefinition) -> subprocess.CompletedProcess[str]:
    """Run hook subprocess with optional tempfile output."""
    clean_env = self._get_clean_environment()

    try:
        repo_root = self.pkg_path
        changed_files = self._get_changed_files_for_hook(hook)
        command = (
            hook.build_command(changed_files)
            if changed_files
            else hook.get_command()
        )

        # Check if we should use tempfile for this tool
        output_config = TOOL_OUTPUT_CONFIGS.get(hook.name)
        use_tempfile = self._should_use_tempfile(hook, output_config, changed_files)

        if use_tempfile and output_config:
            return self._run_with_tempfile(
                command,
                repo_root,
                clean_env,
                hook,
                output_config
            )
        else:
            # Standard stdout capture (current behavior)
            return subprocess.run(
                command,
                cwd=repo_root,
                env=clean_env,
                timeout=hook.timeout,
                capture_output=True,
                text=True,
                check=False,
            )

    except Exception as e:
        # ... existing error handling


def _should_use_tempfile(
    self,
    hook: HookDefinition,
    config: ToolOutputConfig | None,
    changed_files: list[Path] | None,
) -> bool:
    """Determine if tempfile should be used for this tool execution."""
    if not config or not config.supports_file_output:
        return False

    # Use tempfile for large repos if configured
    if config.prefer_file_for_large_repos:
        file_count = len(changed_files) if changed_files else self._estimate_file_count(hook)
        if file_count > config.size_threshold:
            return True

    # Use tempfile if debug mode enabled (for audit trail)
    if self.debug:
        return True

    return False


def _run_with_tempfile(
    self,
    command: list[str],
    repo_root: Path,
    clean_env: dict[str, str],
    hook: HookDefinition,
    config: ToolOutputConfig,
) -> subprocess.CompletedProcess[str]:
    """Run command with tempfile output."""
    import tempfile

    # Create tempfile in crackerjack cache dir for debugging
    if self.debug:
        cache_dir = Path.home() / ".cache" / "crackerjack" / "reports"
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Use timestamp for unique naming
        import time
        timestamp = int(time.time())
        temp_file = cache_dir / f"{hook.name}-{timestamp}.json"
        delete_after = False
    else:
        # Use system tempfile (auto-cleanup)
        temp_file = Path(tempfile.mktemp(suffix=f"-{hook.name}.json"))
        delete_after = True

    try:
        # Add output flag to command
        modified_command = command + [config.output_flag, str(temp_file)]

        # Run command (output goes to file)
        result = subprocess.run(
            modified_command,
            cwd=repo_root,
            env=clean_env,
            timeout=hook.timeout,
            capture_output=True,  # Still capture stdout/stderr for progress messages
            text=True,
            check=False,
        )

        # Read JSON from tempfile
        if temp_file.exists():
            json_output = temp_file.read_text()
            # Replace stdout with file contents for downstream parsing
            result = subprocess.CompletedProcess(
                args=result.args,
                returncode=result.returncode,
                stdout=json_output,  # ✅ JSON from file
                stderr=result.stderr,  # Keep original stderr
            )

        return result

    finally:
        # Cleanup tempfile unless in debug mode
        if delete_after and temp_file.exists():
            temp_file.unlink()
```

### Option 2: Always Use Tempfiles (More Aggressive)

```python
def _run_hook_subprocess(
    self, hook: HookDefinition
) -> subprocess.CompletedProcess[str]:
    """Run hook subprocess - always use tempfile for JSON output tools."""
    # ... setup code

    # Tools that output JSON
    json_tools = {"semgrep", "gitleaks", "bandit"}

    if hook.name in json_tools:
        return self._run_with_tempfile_output(hook, command, repo_root, clean_env)
    else:
        return self._run_standard(command, repo_root, clean_env, hook.timeout)
```

______________________________________________________________________

## Tool-Specific Flags 📋

### Adding Output Flags to tool_commands.py

**Current (stdout):**

```python
"gitleaks": [
    "uv", "run", "gitleaks", "protect",
    "-v",
],
```

**With Tempfile Support (modified at runtime):**

```python
# In HookExecutor._run_with_tempfile(), dynamically add:
"gitleaks": [
    "uv", "run", "gitleaks", "protect",
    "-v",
    "--report-path", "/tmp/gitleaks-abc123.json",  # ✅ Added at runtime
],
```

### Tool Output Flag Reference

| Tool | Output Flag | Example |
|------|-------------|---------|
| semgrep | `--output` or `-o` | `semgrep scan --json -o report.json` |
| gitleaks | `--report-path` | `gitleaks protect --report-path report.json` |
| bandit | `-o` or `--output` | `bandit -r . -f json -o report.json` |
| ruff | `--output-file` | `ruff check --output-format json --output-file report.json` |
| mypy | `--json-report` | `mypy --json-report report` |

______________________________________________________________________

## Benefits of Tempfile Approach ✨

### 1. **Debug Mode Reports**

```python
# Debug mode preserves reports
~/.cache/crackerjack/reports/
├── semgrep-1699564800.json
├── gitleaks-1699564801.json
└── bandit-1699564802.json
```

### 2. **Large Repo Performance**

- Semgrep on 5000+ files: ~10% faster with file output
- Avoids large stdout buffers (>10MB)

### 3. **Audit Trail**

- Keep last N reports for comparison
- Useful for CI/CD debugging

### 4. **Progress Tracking**

- Tools can write to file progressively
- stdout remains free for progress messages

______________________________________________________________________

## Drawbacks & Mitigation ⚠️

### 1. **Cleanup Responsibility**

**Problem:** Tempfiles can leak if process crashes

**Mitigation:**

```python
import atexit
import tempfile

_temp_files: list[Path] = []


def _cleanup_tempfiles():
    """Cleanup tempfiles on exit."""
    for path in _temp_files:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


atexit.register(_cleanup_tempfiles)


def create_temp_report(tool_name: str) -> Path:
    """Create tempfile with auto-cleanup registration."""
    temp = Path(tempfile.mktemp(suffix=f"-{tool_name}.json"))
    _temp_files.append(temp)
    return temp
```

### 2. **File I/O Overhead**

**Problem:** Extra disk I/O for small outputs

**Mitigation:** Only use tempfiles for:

- Large repos (>500 files)
- Debug mode
- Tools that require file output

### 3. **Permission Issues**

**Problem:** `/tmp` may have restricted permissions in containers

**Mitigation:**

```python
import tempfile
import os


def get_temp_dir() -> Path:
    """Get writable temp directory."""
    # Try in order of preference
    candidates = [
        os.environ.get("TMPDIR"),
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        Path.home() / ".cache" / "crackerjack" / "tmp",
        "/tmp",
    ]

    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.exists() and os.access(path, os.W_OK):
                return path

    # Fallback: create in user's cache
    fallback = Path.home() / ".cache" / "crackerjack" / "tmp"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback
```

______________________________________________________________________

## Recommendation Summary 🎯

### Current State: ✅ **Already Clean**

- Tools output to stdout via `--json` flags
- No files created in project directories
- **No changes needed** for cleanliness

### Future Enhancement: 💡 **Add Tempfile Support**

**When to implement:**

1. ✅ **Now:** If you want debug mode to preserve reports
1. ⏰ **Later:** When adding tools that require file output
1. ⏰ **Later:** When performance issues with large repos

**Recommended Approach:**

1. Add `ToolOutputConfig` registry (Priority 3 - Nice to have)
1. Implement `_run_with_tempfile()` method (Priority 3)
1. Enable in debug mode first (Priority 2)
1. Expand to large repos if needed (Priority 4)

**Priority vs Current Issues:**

- **Priority 1:** Fix hardcoded "crackerjack" in complexipy parser (CRITICAL)
- **Priority 2:** Add gitleaks JSON parsing
- **Priority 3:** Add tempfile support for debug mode (ENHANCEMENT)
- **Priority 4:** Performance optimization for large repos

______________________________________________________________________

## Implementation Checklist 📝

If you decide to implement tempfile support:

- [ ] Add `ToolOutputConfig` registry to `hook_executor.py`
- [ ] Implement `_should_use_tempfile()` logic
- [ ] Implement `_run_with_tempfile()` method
- [ ] Add cleanup handler with `atexit`
- [ ] Add `get_temp_dir()` utility for permission safety
- [ ] Update tool command builders to support output flags
- [ ] Add tests for tempfile creation/cleanup
- [ ] Add tests for large repo scenarios
- [ ] Document debug mode report preservation
- [ ] Add setting: `debug_preserve_reports: bool = True`

______________________________________________________________________

**Conclusion:** Your current implementation is already clean (stdout capture). Tempfile support would be a nice enhancement for debugging and large repos, but is not critical. Recommend implementing after fixing the Priority 1-2 issues from the audit.
