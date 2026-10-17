# Tempfile Coverage Output Analysis

**Question:** Can we implement tempfiles for test coverage output?

**Answer:** YES - Highly recommended! Coverage files currently clutter the project directory.

______________________________________________________________________

## Current State ⚠️

### Files Created During Test Runs

| File/Directory | Location | Purpose | Gitignored? |
|----------------|----------|---------|-------------|
| `.coverage` | Project root | Coverage database | ✅ Yes |
| `.coverage.*` | Project root | Parallel coverage data | ✅ Yes |
| `coverage.json` | Project root | JSON coverage report | ✅ Yes |
| `htmlcov/` | Project root | HTML coverage report | ✅ Yes |
| `tests/htmlcov/` | tests/ | Legacy HTML reports | ✅ Yes |

**Configuration (pyproject.toml):**

```toml
[tool.coverage.run]
data_file = ".coverage"  # ⚠️ Root directory
parallel = true
concurrency = ["multiprocessing"]

[tool.pytest.ini_options]
addopts = """
    --cov=crackerjack
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov  # ⚠️ Root directory
    --cov-report=json          # ⚠️ Root directory (coverage.json)
"""
```

### Problems with Current Approach

1. **Directory Clutter**

   - `.coverage` files visible in project root
   - `htmlcov/` directory in root (often large)
   - `coverage.json` in root

1. **CI/CD Conflicts**

   - Multiple CI jobs can conflict on `.coverage` file
   - Parallel test runners create `.coverage.machine.pid.seq` files

1. **User Confusion**

   - Developers wonder "should I commit these?"
   - VS Code/IDEs show coverage files in file explorer

1. **Cross-Tool Issues**

   - Health metrics service reads from `htmlcov/index.html`
   - Backup service excludes `htmlcov/`
   - Various adapters exclude `**/htmlcov/**`

______________________________________________________________________

## Recommended Solution 🎯

### Move Coverage Data to Temp/Cache Directory

**Benefits:**

- ✅ Clean project root
- ✅ No gitignore needed for coverage files
- ✅ Automatic cleanup of old coverage data
- ✅ Better CI/CD isolation
- ✅ Consistent with XDG Base Directory Specification

**Location:**

```
~/.cache/crackerjack/coverage/{project-name}/
├── .coverage
├── .coverage.*
├── coverage.json
└── htmlcov/
    ├── index.html
    └── ...
```

______________________________________________________________________

## Implementation Plan 📋

### Phase 1: Update pyproject.toml Configuration

**Current:**

```toml
[tool.coverage.run]
data_file = ".coverage"

[tool.pytest.ini_options]
addopts = "--cov=crackerjack --cov-report=html:htmlcov --cov-report=json"
```

**New (with tempfile support):**

```toml
[tool.coverage.run]
# Coverage data file will be set dynamically by TestCommandBuilder
# data_file = "{cache_dir}/coverage/{project_name}/.coverage"
# Commented out - set via COVERAGE_FILE environment variable

[tool.pytest.ini_options]
# Coverage reports will be set dynamically
# addopts = "--cov=crackerjack"
testpaths = ["tests"]
```

### Phase 2: Modify TestCommandBuilder

**File:** `crackerjack/managers/test_command_builder.py`

```python
import os
from pathlib import Path
import hashlib


class TestCommandBuilder:
    def __init__(self, pkg_path: Path):
        self.pkg_path = pkg_path
        self.cache_dir = self._get_coverage_cache_dir()

    def _get_coverage_cache_dir(self) -> Path:
        """Get cache directory for coverage data.

        Returns:
            Path to coverage cache directory for this project

        Example:
            ~/.cache/crackerjack/coverage/my-project/
        """
        # XDG Base Directory Specification
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            base_cache = Path(xdg_cache)
        else:
            base_cache = Path.home() / ".cache"

        # Create unique directory per project
        project_name = self.pkg_path.name
        project_hash = hashlib.md5(str(self.pkg_path.absolute()).encode()).hexdigest()[
            :8
        ]

        coverage_dir = (
            base_cache / "crackerjack" / "coverage" / f"{project_name}-{project_hash}"
        )
        coverage_dir.mkdir(parents=True, exist_ok=True)

        return coverage_dir

    def build_test_command(
        self, options: OptionsProtocol, workers: int
    ) -> tuple[list[str], dict[str, str]]:
        """Build pytest command with tempfile coverage paths.

        Returns:
            Tuple of (command_list, environment_dict)
        """
        # Set coverage data file via environment variable
        # This overrides pyproject.toml setting
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(self.cache_dir / ".coverage")

        # Build base command
        cmd = ["uv", "run", "pytest"]

        # Add coverage options
        cmd.extend(
            [
                f"--cov={self.pkg_path.name}",
                "--cov-report=term-missing:skip-covered",
                f"--cov-report=html:{self.cache_dir / 'htmlcov'}",
                f"--cov-report=json:{self.cache_dir / 'coverage.json'}",
            ]
        )

        # Add worker config
        if workers != 1:
            cmd.append(f"-n={workers}")

        # Add test path
        cmd.append("tests")

        return cmd, env
```

### Phase 3: Update TestExecutor

**File:** `crackerjack/managers/test_executor.py`

```python
class TestExecutor:
    def execute_tests(
        self,
        command: list[str],
        env: dict[str, str],  # ✅ Accept environment
        pkg_path: Path,
    ) -> subprocess.CompletedProcess:
        """Execute pytest with custom environment."""
        return subprocess.run(
            command,
            cwd=pkg_path,
            env=env,  # ✅ Use custom environment
            capture_output=True,
            text=True,
            check=False,
        )
```

### Phase 4: Update Coverage Service Readers

**File:** `crackerjack/services/health_metrics.py`

```python
class HealthMetricsService:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        # ✅ Read from cache directory instead of project root
        self.coverage_cache = self._get_coverage_cache_dir()

    def _get_coverage_cache_dir(self) -> Path:
        """Get coverage cache directory for this project."""
        # Same logic as TestCommandBuilder
        xdg_cache = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        project_name = self.project_root.name
        project_hash = hashlib.md5(
            str(self.project_root.absolute()).encode()
        ).hexdigest()[:8]

        return (
            Path(xdg_cache)
            / "crackerjack"
            / "coverage"
            / f"{project_name}-{project_hash}"
        )

    def get_coverage_percentage(self) -> float | None:
        """Read coverage from cache directory."""
        coverage_json = self.coverage_cache / "coverage.json"

        if not coverage_json.exists():
            return None

        try:
            data = json.loads(coverage_json.read_text())
            return data["totals"]["percent_covered"]
        except Exception:
            return None
```

### Phase 5: Add Coverage Cache Utilities

**File:** `crackerjack/utils/coverage_cache.py` (new file)

```python
"""Utilities for managing coverage cache directory."""

import hashlib
import os
import shutil
from pathlib import Path


def get_coverage_cache_dir(project_root: Path) -> Path:
    """Get coverage cache directory for a project.

    Uses XDG Base Directory Specification:
    - $XDG_CACHE_HOME/crackerjack/coverage/{project}-{hash}/
    - Defaults to ~/.cache/crackerjack/coverage/{project}-{hash}/

    Args:
        project_root: Root directory of the project

    Returns:
        Path to coverage cache directory

    Example:
        >>> get_coverage_cache_dir(Path("/home/user/my-project"))
        Path('/home/user/.cache/crackerjack/coverage/my-project-a1b2c3d4')
    """
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base_cache = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"

    project_name = project_root.name
    project_hash = hashlib.md5(str(project_root.absolute()).encode()).hexdigest()[:8]

    coverage_dir = (
        base_cache / "crackerjack" / "coverage" / f"{project_name}-{project_hash}"
    )
    coverage_dir.mkdir(parents=True, exist_ok=True)

    return coverage_dir


def clean_old_coverage(project_root: Path, keep_last_n: int = 5) -> int:
    """Clean old coverage data, keeping only recent runs.

    Args:
        project_root: Root directory of the project
        keep_last_n: Number of recent coverage runs to keep

    Returns:
        Number of coverage files removed
    """
    cache_dir = get_coverage_cache_dir(project_root)

    # Find all .coverage.* files (parallel coverage data)
    coverage_files = sorted(
        cache_dir.glob(".coverage.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # Newest first
    )

    # Remove old files
    removed = 0
    for old_file in coverage_files[keep_last_n:]:
        old_file.unlink()
        removed += 1

    return removed


def get_coverage_html_path(project_root: Path) -> Path:
    """Get path to HTML coverage report.

    Args:
        project_root: Root directory of the project

    Returns:
        Path to htmlcov/index.html
    """
    cache_dir = get_coverage_cache_dir(project_root)
    return cache_dir / "htmlcov" / "index.html"


def open_coverage_report(project_root: Path) -> bool:
    """Open coverage HTML report in browser.

    Args:
        project_root: Root directory of the project

    Returns:
        True if report was opened successfully
    """
    html_path = get_coverage_html_path(project_root)

    if not html_path.exists():
        return False

    import webbrowser

    webbrowser.open(f"file://{html_path}")
    return True


def clear_coverage_cache(project_root: Path) -> bool:
    """Clear all coverage data for a project.

    Args:
        project_root: Root directory of the project

    Returns:
        True if cache was cleared successfully
    """
    cache_dir = get_coverage_cache_dir(project_root)

    if not cache_dir.exists():
        return False

    try:
        shutil.rmtree(cache_dir)
        return True
    except Exception:
        return False
```

______________________________________________________________________

## Updated Commands 🔧

### Opening Coverage Reports

**Old (project root):**

```bash
# Opens ./htmlcov/index.html
open htmlcov/index.html
```

**New (cache directory):**

```bash
# Opens ~/.cache/crackerjack/coverage/my-project-abc123/htmlcov/index.html
python -m crackerjack --open-coverage

# Or via CLI utility
crackerjack coverage show
```

### Cleaning Old Coverage Data

```bash
# Clean coverage data older than last 5 runs
crackerjack coverage clean

# Clear all coverage data for current project
crackerjack coverage clear
```

______________________________________________________________________

## Benefits Summary ✨

### 1. **Clean Project Root**

```
my-project/
├── src/
├── tests/
├── pyproject.toml
└── README.md

# NO MORE:
# ├── .coverage
# ├── .coverage.*
# ├── coverage.json
# └── htmlcov/
```

### 2. **Better CI/CD**

```yaml
# GitHub Actions - no conflicts between jobs
jobs:
  test-job-1:
    # Coverage data in: ~/.cache/crackerjack/coverage/my-project-{hash}/
  test-job-2:
    # Different cache directory per job
```

### 3. **Automatic Cleanup**

- Old coverage data automatically cleaned
- Keep last N runs for comparison
- No manual deletion needed

### 4. **Multi-Project Support**

```
~/.cache/crackerjack/coverage/
├── project-a-abc123/
│   └── .coverage
├── project-b-def456/
│   └── .coverage
└── project-c-ghi789/
    └── .coverage
```

### 5. **XDG Compliance**

- Follows Linux/Unix standards
- Respects `$XDG_CACHE_HOME`
- Easy to clear: `rm -rf ~/.cache/crackerjack`

______________________________________________________________________

## Migration Path 🛣️

### Step 1: Add Utilities (Week 1)

- [ ] Create `utils/coverage_cache.py`
- [ ] Add `get_coverage_cache_dir()` function
- [ ] Add tests for cache directory creation

### Step 2: Update Test Builder (Week 1)

- [ ] Modify `TestCommandBuilder.build_test_command()`
- [ ] Set `COVERAGE_FILE` environment variable
- [ ] Update coverage report paths
- [ ] Add tests

### Step 3: Update Services (Week 2)

- [ ] Update `HealthMetricsService.get_coverage_percentage()`
- [ ] Update any other services reading coverage files
- [ ] Add backward compatibility for existing coverage files

### Step 4: Add CLI Commands (Week 2)

- [ ] `crackerjack coverage show` - Open HTML report
- [ ] `crackerjack coverage clean` - Clean old data
- [ ] `crackerjack coverage clear` - Clear all data
- [ ] `crackerjack coverage path` - Print cache directory path

### Step 5: Documentation (Week 3)

- [ ] Update README.md
- [ ] Update CLAUDE.md
- [ ] Add migration guide for existing projects
- [ ] Update troubleshooting guide

### Step 6: Backward Compatibility (Week 3)

```python
def get_coverage_percentage(self) -> float | None:
    """Read coverage from cache directory with fallback."""
    # Try cache directory first
    cache_json = self.coverage_cache / "coverage.json"
    if cache_json.exists():
        return self._read_coverage_json(cache_json)

    # Fallback to project root (legacy)
    root_json = self.project_root / "coverage.json"
    if root_json.exists():
        self.console.print(
            "[yellow]⚠️  Coverage data in project root is deprecated. "
            "Run tests to migrate to cache directory.[/yellow]"
        )
        return self._read_coverage_json(root_json)

    return None
```

______________________________________________________________________

## Configuration Options ⚙️

### Settings File

**File:** `settings/crackerjack.yaml`

```yaml
coverage:
  # Cache directory strategy
  use_cache_dir: true  # Set to false to use project root (legacy)

  # Cache location
  cache_base: "~/.cache/crackerjack"  # Override with custom path

  # Cleanup policy
  keep_last_n_runs: 5
  auto_cleanup: true

  # Reports
  html_report: true
  json_report: true
  terminal_report: true

  # Open report after tests
  auto_open_html: false
```

### Environment Variables

```bash
# Override cache base directory
export CRACKERJACK_CACHE_DIR="$HOME/.local/share/crackerjack"

# Disable tempfile (use project root - legacy)
export CRACKERJACK_COVERAGE_USE_ROOT=1

# Keep more historical data
export CRACKERJACK_COVERAGE_KEEP_RUNS=10
```

______________________________________________________________________

## Rollback Plan 🔙

If tempfiles cause issues:

1. **Immediate Rollback:**

   ```bash
   export CRACKERJACK_COVERAGE_USE_ROOT=1
   ```

1. **Configuration Rollback:**

   ```yaml
   # settings/local.yaml
   coverage:
     use_cache_dir: false
   ```

1. **Code Rollback:**

   - Revert `TestCommandBuilder` changes
   - Keep `coverage_cache.py` utilities for future use

______________________________________________________________________

## Comparison with Other Tools 🔍

### How Other Tools Handle Coverage

| Tool | Coverage Location | Notes |
|------|-------------------|-------|
| **pytest-cov** | `.coverage` in project root | Default behavior |
| **Jest** | `coverage/` in project root | Configurable via `coverageDirectory` |
| **Go** | `coverage.out` in project root | Standard practice |
| **Rust (cargo-tarpaulin)** | `target/tarpaulin/` | Uses build directory |
| **Ruby (SimpleCov)** | `coverage/` in project root | Standard location |

**Crackerjack Approach:**

- ✅ More aggressive cleanup
- ✅ XDG-compliant
- ✅ Multi-project support
- ✅ Automatic old data cleanup

______________________________________________________________________

## Risks & Mitigation ⚠️

### Risk 1: Path Too Long

**Problem:** Cache paths can get long on deeply nested projects

**Mitigation:**

- Use hash instead of full path
- Max length: `~/.cache/crackerjack/coverage/project-name-12345678/`

### Risk 2: Permissions

**Problem:** Cache directory not writable in some environments

**Mitigation:**

```python
def get_coverage_cache_dir(project_root: Path) -> Path:
    """Get writable coverage cache directory."""
    candidates = [
        Path(os.environ.get("XDG_CACHE_HOME", "")),
        Path.home() / ".cache",
        project_root / ".crackerjack-cache",  # Fallback
        Path("/tmp") / "crackerjack-cache",  # Last resort
    ]

    for candidate in candidates:
        if candidate and _is_writable(candidate):
            return candidate / "crackerjack" / "coverage" / ...

    # Final fallback: project root (legacy behavior)
    return project_root
```

### Risk 3: CI/CD Cache Eviction

**Problem:** CI cache directories cleared between runs

**Mitigation:**

- Document CI cache configuration
- Provide option to use project root in CI

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: python -m crackerjack --run-tests
  env:
    CRACKERJACK_COVERAGE_USE_ROOT: 1  # Use project root in CI
```

______________________________________________________________________

## Testing Plan 🧪

### Unit Tests

```python
# tests/test_coverage_cache.py


def test_get_coverage_cache_dir():
    """Test coverage cache directory creation."""
    project = Path("/home/user/my-project")
    cache_dir = get_coverage_cache_dir(project)

    assert cache_dir.exists()
    assert "crackerjack" in str(cache_dir)
    assert "coverage" in str(cache_dir)
    assert "my-project" in str(cache_dir)


def test_coverage_cache_unique_per_project():
    """Test different projects get different cache dirs."""
    project_a = Path("/home/user/project-a")
    project_b = Path("/home/user/project-b")

    cache_a = get_coverage_cache_dir(project_a)
    cache_b = get_coverage_cache_dir(project_b)

    assert cache_a != cache_b


def test_clean_old_coverage():
    """Test cleaning old coverage data."""
    project = Path("/home/user/my-project")
    cache_dir = get_coverage_cache_dir(project)

    # Create 10 fake coverage files
    for i in range(10):
        (cache_dir / f".coverage.{i}").touch()

    # Keep only last 5
    removed = clean_old_coverage(project, keep_last_n=5)

    assert removed == 5
    assert len(list(cache_dir.glob(".coverage.*"))) == 5
```

### Integration Tests

```python
def test_coverage_data_in_cache(tmp_path):
    """Test coverage data written to cache directory."""
    # Run tests
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--run-tests"],
        cwd=tmp_path,
        capture_output=True,
    )

    # Check cache directory
    cache_dir = get_coverage_cache_dir(tmp_path)
    assert (cache_dir / ".coverage").exists()
    assert (cache_dir / "coverage.json").exists()
    assert (cache_dir / "htmlcov" / "index.html").exists()

    # Check project root is clean
    assert not (tmp_path / ".coverage").exists()
    assert not (tmp_path / "htmlcov").exists()
```

______________________________________________________________________

## Recommendation 🎯

**IMPLEMENT THIS** - High value, low risk

**Priority:** Priority 2 (after fixing hardcoded package name issue)

**Benefits:**

- ✅ Clean project directories
- ✅ Better developer experience
- ✅ XDG compliance
- ✅ Automatic cleanup

**Effort:** ~2-3 days

- Day 1: Implement utilities + test builder changes
- Day 2: Update services + add CLI commands
- Day 3: Testing + documentation

**Risk:** Low

- Easy rollback via environment variable
- Backward compatibility with fallback
- No breaking changes to external APIs

______________________________________________________________________

**Next Steps:**

1. ✅ Review and approve this design
1. Create `utils/coverage_cache.py`
1. Update `TestCommandBuilder`
1. Add CLI commands
1. Update documentation
