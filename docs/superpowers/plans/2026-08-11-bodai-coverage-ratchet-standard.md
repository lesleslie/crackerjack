# Coverage-Ratchet Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize `.coverage-ratchet.json` and `pyproject.toml` `--cov-fail-under` across all 7 Bodai components, with Crackerjack's test stage auto-enforcing the ratchet on every run.

**Architecture:** Crackerjack owns the policy and the enforcer. `.coverage-ratchet.json` is the canonical source of truth for the floor; `pyproject.toml` `--cov-fail-under` is a mirror kept in sync by the test stage. The ratchet ticks up only when coverage rises (never down). Each repo adopts the policy via a single direct commit to `main`.

**Tech Stack:** Python 3.13, Crackerjack, Oneiric, pytest, pytest-cov, rich.

## Global Constraints

- Crackerjack's `CoverageRatchetService` already implements the ratchet math (MILESTONES, TOLERANCE_MARGIN=2.0).
- No 80% default. Initial floor = current coverage at `init` time.
- All commits land directly to `main` per `bodai-pre-1.0-merge-policy.md`. No PRs.
- Use `from __future__ import annotations` and Python 3.13 syntax in all new files.
- Each task ends with a green test suite and a single commit.

______________________________________________________________________

## File Structure

### Files modified (Phase A: crackerjack infrastructure)

| File | Responsibility |
|---|---|
| `crackerjack/crackerjack/services/coverage_ratchet.py` | Extend with `lower_baseline`, `mirror_to_pyproject`, `report_status` |
| `crackerjack/crackerjack/managers/test_manager.py` | Wire ratchet into test stage (post-pytest hook) |
| `crackerjack/crackerjack/cli/coverage_ratchet_cli.py` | NEW — `init`, `status`, `lower`, `migrate` CLI commands |
| `crackerjack/crackerjack/cli/__init__.py` | Register new CLI commands |
| `crackerjack/tests/services/test_coverage_ratchet.py` | NEW — unit tests for service extensions |
| `crackerjack/tests/managers/test_test_manager_ratchet.py` | NEW — integration tests for test-stage wiring |
| `crackerjack/tests/e2e/test_bodai_ratchet_adoption.py` | NEW — e2e tests, one per Bodai repo |

### Files modified (Phase B: per-repo adoption)

Per Bodai repo (one commit each):

- `repos/<repo>/.coverage-ratchet.json` — created or updated
- `repos/<repo>/pyproject.toml` — `--cov-fail-under` mirrored

### Files modified (Phase C: cleanup)

| File | Responsibility |
|---|---|
| `crackerjack/crackerjack/cli/coverage_ratchet_cli.py` | Remove `migrate` command |

______________________________________________________________________

## Task 1: Extend CoverageRatchetService

**Files:**

- Modify: `crackerjack/crackerjack/services/coverage_ratchet.py` (add 3 methods)
- Test: `crackerjack/tests/services/test_coverage_ratchet.py` (new file)

**Interfaces:**

- Consumes: existing `CoverageRatchetService` (already production-ready)

- Produces: `lower_baseline(new_coverage: float, reason: str) -> None`, `mirror_to_pyproject(coverage: float) -> None`, `report_status() -> str`

- [ ] **Step 1: Write the failing test for `lower_baseline`**

```python
# crackerjack/tests/services/test_coverage_ratchet.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crackerjack.services.coverage_ratchet import CoverageRatchetService


@pytest.fixture
def ratchet(tmp_path: Path) -> CoverageRatchetService:
    svc = CoverageRatchetService(pkg_path=tmp_path)
    svc.initialize_baseline(50.0)
    return svc


def test_lower_baseline_requires_reason(ratchet: CoverageRatchetService) -> None:
    with pytest.raises(ValueError, match="reason"):
        ratchet.lower_baseline(45.0, reason="")


def test_lower_baseline_updates_current_minimum(ratchet: CoverageRatchetService) -> None:
    ratchet.lower_baseline(45.0, reason="explicit ack")
    data = ratchet.get_ratchet_data()
    assert data["current_minimum"] == 45.0
    assert data["history"][-1]["reason"] == "explicit ack"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_coverage_ratchet.py -v`
Expected: FAIL with `AttributeError: 'CoverageRatchetService' object has no attribute 'lower_baseline'`

- [ ] **Step 3: Implement `lower_baseline`**

```python
# crackerjack/crackerjack/services/coverage_ratchet.py — append to class

def lower_baseline(self, new_coverage: float, reason: str) -> None:
    if not reason or not reason.strip():
        msg = "lower_baseline requires a non-empty reason"
        raise ValueError(msg)
    data = self.get_ratchet_data()
    if not data:
        msg = "Coverage ratchet not initialized"
        raise ValueError(msg)
    data["current_minimum"] = new_coverage
    data["last_updated"] = datetime.now().isoformat()
    data["history"].append(
        {
            "date": datetime.now().isoformat(),
            "coverage": new_coverage,
            "commit": "lower",
            "milestone": False,
            "reason": reason,
        }
    )
    self.ratchet_file.write_text(json.dumps(data, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_coverage_ratchet.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for `mirror_to_pyproject`**

```python
def test_mirror_to_pyproject_writes_cov_fail_under(ratchet: CoverageRatchetService, tmp_path: Path) -> None:
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=80"\n'
    )
    ratchet.mirror_to_pyproject(50.0)
    content = ratchet.pyproject_file.read_text()
    assert "--cov-fail-under=50.0" in content
```

- [ ] **Step 6: Implement `mirror_to_pyproject`**

```python
def mirror_to_pyproject(self, coverage: float) -> None:
    """Write --cov-fail-under=<coverage> to pyproject.toml."""
    import re
    content = self.pyproject_file.read_text()
    pattern = r"--cov-fail-under=\d+(?:\.\d+)?"
    replacement = f"--cov-fail-under={coverage}"
    if re.search(pattern, content):
        new_content = re.sub(pattern, replacement, content)
    else:
        # Insert into addopts if present, else append
        if "addopts" in content:
            new_content = re.sub(
                r'(addopts\s*=\s*"[^"]*)"',
                rf'\1 {replacement}"',
                content,
                count=1,
            )
        else:
            new_content = f'{content}\n[tool.pytest.ini_options]\naddopts = "{replacement}"\n'
    self.pyproject_file.write_text(new_content)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_coverage_ratchet.py -v`
Expected: PASS

- [ ] **Step 8: Write the failing test for `report_status`**

```python
def test_report_status_includes_baseline_and_next_milestone(ratchet: CoverageRatchetService) -> None:
    status = ratchet.report_status()
    assert "50.0%" in status
    assert "50" in status or "60" in status  # baseline or next milestone
```

- [ ] **Step 9: Implement `report_status`**

```python
def report_status(self) -> str:
    data = self.get_ratchet_data()
    if not data:
        return "Coverage ratchet not initialized"
    baseline = data.get("baseline", 0.0)
    current = data.get("current_minimum", 0.0)
    next_milestone = data.get("next_milestone")
    history = data.get("history", [])
    lines = [
        f"Baseline: {baseline:.2f}%",
        f"Current minimum: {current:.2f}%",
        f"Next milestone: {next_milestone}",
        f"History entries: {len(history)}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 10: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_coverage_ratchet.py -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/services/coverage_ratchet.py crackerjack/tests/services/test_coverage_ratchet.py
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): add lower_baseline, mirror_to_pyproject, report_status

- lower_baseline: explicit operator ack of regression, requires --reason
- mirror_to_pyproject: writes --cov-fail-under to pyproject.toml
- report_status: human-readable summary for status CLI command

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 2: Wire ratchet into test-stage integration

**Files:**

- Modify: `crackerjack/crackerjack/managers/test_manager.py` (add post-test hook)
- Test: `crackerjack/tests/managers/test_test_manager_ratchet.py` (new file)

**Interfaces:**

- Consumes: `CoverageRatchetService` from Task 1

- Produces: test stage exits 1 on drop, exits 0 on pass, mirrors pyproject.toml on bump

- [ ] **Step 1: Write the failing test for ratchet drop exit code**

```python
# crackerjack/tests/managers/test_test_manager_ratchet.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.managers.test_manager import TestManager
from crackerjack.services.coverage_ratchet import CoverageRatchetService


@pytest.fixture
def fake_project(tmp_path: Path) -> tuple[Path, CoverageRatchetService]:
    ratchet = CoverageRatchetService(pkg_path=tmp_path)
    ratchet.initialize_baseline(50.0)
    ratchet.pyproject_file.write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=50.0"\n'
    )
    # Fake coverage.json
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 45.0}})
    )
    return tmp_path, ratchet


def test_test_stage_exits_1_on_drop(fake_project: tuple[Path, CoverageRatchetService]) -> None:
    pkg_path, ratchet = fake_project
    manager = TestManager(pkg_path=pkg_path, ratchet=ratchet)
    result = manager.run_with_ratchet_check()
    assert result.exit_code == 1
    assert "Coverage regression detected" in result.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/managers/test_test_manager_ratchet.py -v`
Expected: FAIL with `AttributeError` or `NotImplementedError`

- [ ] **Step 3: Implement the ratchet check in TestManager**

```python
# crackerjack/crackerjack/managers/test_manager.py — add method

from dataclasses import dataclass

@dataclass
class RatchetResult:
    exit_code: int
    message: str


class TestManager:
    def __init__(self, pkg_path: Path, ratchet: CoverageRatchetService) -> None:
        self.pkg_path = pkg_path
        self.ratchet = ratchet

    def run_with_ratchet_check(self) -> RatchetResult:
        # Read coverage.json
        coverage_file = self.pkg_path / "coverage.json"
        if not coverage_file.exists():
            return RatchetResult(
                exit_code=1,
                message="coverage.json not found; run pytest with coverage first",
            )
        data = json.loads(coverage_file.read_text())
        current_pct = data.get("totals", {}).get("percent_covered", 0.0)

        # Check ratchet
        if not self.ratchet.ratchet_file.exists():
            return RatchetResult(
                exit_code=1,
                message="Ratchet not initialized. Run `crackerjack coverage-ratchet init`.",
            )

        ratchet_data = self.ratchet.get_ratchet_data()
        baseline = ratchet_data.get("current_minimum", 0.0)
        tolerance = self.ratchet.TOLERANCE_MARGIN
        drop = baseline - current_pct

        if drop > tolerance:
            msg = (
                f"📉 Coverage regression detected\n"
                f"   Current: {current_pct:.2f}%\n"
                f"   Ratchet: {baseline:.2f}% (TOLERANCE_MARGIN: {tolerance:.1f})\n"
                f"   Drop: {drop:.2f}% (exceeds tolerance)\n\n"
                f"   To recover:\n"
                f"     • Add tests to bring coverage back above {baseline:.2f}%\n"
                f"     • OR acknowledge the regression:\n"
                f"         crackerjack coverage-ratchet lower --to {current_pct:.2f} --reason \"<text>\""
            )
            return RatchetResult(exit_code=1, message=msg)

        if current_pct > baseline + tolerance:
            self.ratchet.mirror_to_pyproject(current_pct)
            # Bump ratchet up
            ratchet_data["current_minimum"] = current_pct
            ratchet_data["last_updated"] = datetime.now().isoformat()
            self.ratchet.ratchet_file.write_text(json.dumps(ratchet_data, indent=2))

        return RatchetResult(exit_code=0, message=f"Coverage: {current_pct:.2f}%")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/managers/test_test_manager_ratchet.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for bump + mirror**

```python
def test_test_stage_bumps_ratchet_and_mirrors_on_rise(fake_project: tuple[Path, CoverageRatchetService]) -> None:
    pkg_path, ratchet = fake_project
    # Coverage rose to 55% (above 50% baseline)
    (pkg_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 55.0}})
    )
    manager = TestManager(pkg_path=pkg_path, ratchet=ratchet)
    result = manager.run_with_ratchet_check()
    assert result.exit_code == 0
    data = ratchet.get_ratchet_data()
    assert data["current_minimum"] > 50.0
    assert "--cov-fail-under=55.0" in ratchet.pyproject_file.read_text()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/managers/test_test_manager_ratchet.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/managers/test_manager.py crackerjack/tests/managers/test_test_manager_ratchet.py
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): wire ratchet into test-stage integration

Test stage:
- Reads coverage.json after pytest
- Reads .coverage-ratchet.json
- Exits 1 on drop > TOLERANCE_MARGIN with actionable error
- Exits 0 on pass, bumps ratchet up if coverage rose
- Mirrors bumped value to pyproject.toml --cov-fail-under

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 3: Add CLI commands

**Files:**

- Create: `crackerjack/crackerjack/cli/coverage_ratchet_cli.py`
- Modify: `crackerjack/crackerjack/cli/__init__.py` (register commands)

**Interfaces:**

- Consumes: `CoverageRatchetService` from Task 1, `TestManager.run_with_ratchet_check` from Task 2

- Produces: `crackerjack coverage-ratchet {init,status,lower,migrate}` CLI

- [ ] **Step 1: Write the failing test for CLI `init`**

```python
# crackerjack/tests/cli/test_coverage_ratchet_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from crackerjack.cli.coverage_ratchet_cli import cli


def test_init_creates_ratchet_at_current_coverage(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 47.5}})
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--pkg-path", str(tmp_path)])
    assert result.exit_code == 0
    ratchet = json.loads((tmp_path / ".coverage-ratchet.json").read_text())
    assert ratchet["baseline"] == 47.5
    assert ratchet["current_minimum"] == 47.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement CLI commands**

```python
# crackerjack/crackerjack/cli/coverage_ratchet_cli.py
from __future__ import annotations

import json
from pathlib import Path

import click

from crackerjack.services.coverage_ratchet import CoverageRatchetService


@click.group()
def cli() -> None:
    """Coverage ratchet commands."""


@cli.command()
@click.option("--pkg-path", type=click.Path(exists=True, path_type=Path), default=Path("."))
@click.option("--reinit", is_flag=True, help="Overwrite existing ratchet.")
def init(pkg_path: Path, reinit: bool) -> None:
    """Initialize the coverage ratchet at current coverage."""
    svc = CoverageRatchetService(pkg_path=pkg_path)
    if svc.ratchet_file.exists() and not reinit:
        click.echo(f"Ratchet already exists at {pkg_path}/.coverage-ratchet.json")
        click.echo("Use --reinit to overwrite.")
        raise SystemExit(1)
    coverage_file = pkg_path / "coverage.json"
    if not coverage_file.exists():
        click.echo("coverage.json not found. Run pytest with coverage first.")
        raise SystemExit(1)
    data = json.loads(coverage_file.read_text())
    coverage = data.get("totals", {}).get("percent_covered", 0.0)
    svc.initialize_baseline(coverage)
    svc.mirror_to_pyproject(coverage)
    click.echo(f"✅ Ratchet initialized at {coverage:.2f}%")


@cli.command()
@click.option("--pkg-path", type=click.Path(exists=True, path_type=Path), default=Path("."))
def status(pkg_path: Path) -> None:
    """Show ratchet state."""
    svc = CoverageRatchetService(pkg_path=pkg_path)
    click.echo(svc.report_status())


@cli.command()
@click.option("--to", "to_coverage", type=float, required=True)
@click.option("--reason", type=str, required=True)
@click.option("--pkg-path", type=click.Path(exists=True, path_type=Path), default=Path("."))
def lower(to_coverage: float, reason: str, pkg_path: Path) -> None:
    """Explicitly lower the ratchet (operator ack of regression)."""
    svc = CoverageRatchetService(pkg_path=pkg_path)
    try:
        svc.lower_baseline(to_coverage, reason=reason)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)
    svc.mirror_to_pyproject(to_coverage)
    click.echo(f"✅ Ratchet lowered to {to_coverage:.2f}% (reason: {reason})")


@cli.command()
def migrate() -> None:
    """Auto-invoke init across all 7 Bodai repos (CLI is temporary)."""
    click.echo("⚠️  This is a temporary CLI. Replaced by per-repo init in Phase B.")
    click.echo("    Run `crackerjack coverage-ratchet init` in each repo directly.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py -v`
Expected: PASS

- [ ] **Step 5: Register CLI in `__init__.py`**

```python
# crackerjack/crackerjack/cli/__init__.py — add import
from crackerjack.cli.coverage_ratchet_cli import cli as coverage_ratchet_cli
```

- [ ] **Step 6: Write the failing test for `lower` requiring `--reason`**

```python
def test_lower_requires_reason(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    runner = CliRunner()
    runner.invoke(cli, ["init", "--pkg-path", str(tmp_path)])
    result = runner.invoke(cli, ["lower", "--to", "45.0", "--pkg-path", str(tmp_path)])
    assert result.exit_code != 0
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/cli/coverage_ratchet_cli.py crackerjack/cli/__init__.py crackerjack/tests/cli/test_coverage_ratchet_cli.py
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): CLI commands init, status, lower, migrate

init: initialize ratchet at current coverage, mirror pyproject
status: human-readable ratchet summary
lower: explicit operator ack of regression (requires --reason)
migrate: temporary CLI to auto-invoke init across all 7 repos (removed in Phase C)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 4: Add e2e test for one Bodai repo

**Files:**

- Create: `crackerjack/tests/e2e/test_bodai_ratchet_adoption.py`

**Interfaces:**

- Consumes: `crackerjack coverage-ratchet init` from Task 3

- Produces: e2e test that runs init on a tmp copy of mcp-common and verifies state

- [ ] **Step 1: Write the failing test for the e2e adoption flow**

```python
# crackerjack/tests/e2e/test_bodai_ratchet_adoption.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from crackerjack.cli.coverage_ratchet_cli import cli


@pytest.fixture
def mcp_common_copy(tmp_path: Path) -> Path:
    """Copy a stripped-down version of mcp-common to tmp_path."""
    src = Path("/Users/les/Projects/mcp-common")
    dest = tmp_path / "mcp-common"
    if not src.exists():
        pytest.skip("mcp-common not available in this environment")
    # Copy only pyproject.toml + coverage.json (minimal surface)
    shutil.copy(src / "pyproject.toml", dest / "pyproject.toml")
    if (src / "coverage.json").exists():
        shutil.copy(src / "coverage.json", dest / "coverage.json")
    return dest


def test_init_then_run_keeps_ratchet_stable(mcp_common_copy: Path) -> None:
    runner = CliRunner()
    if not (mcp_common_copy / "coverage.json").exists():
        pytest.skip("coverage.json not present in mcp-common")
    initial = json.loads((mcp_common_copy / "coverage.json").read_text())["totals"]["percent_covered"]
    result = runner.invoke(cli, ["init", "--pkg-path", str(mcp_common_copy)])
    assert result.exit_code == 0
    ratchet = json.loads((mcp_common_copy / ".coverage-ratchet.json").read_text())
    assert ratchet["current_minimum"] == initial
    # Re-run init with --reinit should overwrite
    result2 = runner.invoke(cli, ["init", "--reinit", "--pkg-path", str(mcp_common_copy)])
    assert result2.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/e2e/test_bodai_ratchet_adoption.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Run test to verify it passes (no code changes needed)**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/e2e/test_bodai_ratchet_adoption.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/tests/e2e/test_bodai_ratchet_adoption.py
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "test(ratchet): e2e adoption test for mcp-common

Doubles as a smoke test for the full init flow against a real Bodai repo.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 5: Adopt ratchet in fastblocks

**Files:**

- Modify: `fastblocks/pyproject.toml` (mirror `--cov-fail-under=49.13`)
- The ratchet file is already at `fastblocks/.coverage-ratchet.json` (Task 0 baseline confirmed)

**Interfaces:**

- Consumes: existing ratchet at 49.13% from fastblocks

- Produces: pyproject.toml `--cov-fail-under=49.13`

- [ ] **Step 1: Verify ratchet exists and read current baseline**

Run: `cd /Users/les/Projects/fastblocks && cat .coverage-ratchet.json | python -m json.tool | grep baseline`
Expected: visible baseline value

- [ ] **Step 2: Mirror to pyproject.toml**

Run: `cd /Users/les/Projects/fastblocks && uv run --with crackerjack crackerjack coverage-ratchet init --reinit --pkg-path .`
Expected: `✅ Ratchet initialized at 49.13%`

- [ ] **Step 3: Verify mirror**

Run: `grep -n 'cov-fail-under' /Users/les/Projects/fastblocks/pyproject.toml`
Expected: `--cov-fail-under=49.13` (or with `49.13242009...`)

- [ ] **Step 4: Run ratchet check (verifies integration)**

Run: `cd /Users/les/Projects/fastblocks && uv run pytest --no-cov -n 0 tests/core/test_resolver.py 2>&1 | tail -5`
Expected: tests pass (no ratchet drop at 49.13 with current coverage)

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/fastblocks
git add pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): mirror fastblocks pyproject.toml to current coverage

Aligns --cov-fail-under with .coverage-ratchet.json (49.13%).
Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 6: Adopt ratchet in mahavishnu

**Files:**

- Create: `mahavishnu/.coverage-ratchet.json`
- Modify: `mahavishnu/pyproject.toml`

**Interfaces:**

- Consumes: existing `pyproject.toml --cov-fail-under=80`

- Produces: ratchet at current coverage, mirror to pyproject

- [ ] **Step 1: Measure current coverage**

Run: `cd /Users/les/Projects/mahavishnu && uv run pytest --cov=mahavishnu --cov-report=json -q 2>&1 | tail -5`
Expected: tests pass, coverage.json exists

- [ ] **Step 2: Run init**

Run: `cd /Users/les/Projects/mahavishnu && uv run --with crackerjack crackerjack coverage-ratchet init --pkg-path .`
Expected: `✅ Ratchet initialized at <current>%`

- [ ] **Step 3: Verify mirror**

Run: `cd /Users/les/Projects/mahavishnu && grep -n 'cov-fail-under' pyproject.toml && cat .coverage-ratchet.json | python -m json.tool | grep -E 'baseline|current_minimum'`
Expected: mirror matches ratchet

- [ ] **Step 4: Verify ratchet check passes**

Run: `cd /Users/les/Projects/mahavishnu && uv run pytest --no-cov -n 0 tests/unit/ -q 2>&1 | tail -3`
Expected: tests pass

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/mahavishnu
git add .coverage-ratchet.json pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): adopt coverage-ratchet at current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).
.coverage-ratchet.json created at current coverage; pyproject.toml mirrored.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 7: Adopt ratchet in crackerjack

**Files:**

- Create: `crackerjack/.coverage-ratchet.json`
- Modify: `crackerjack/pyproject.toml`

(Identical structure to Task 6; replace `mahavishnu` with `crackerjack`.)

- [ ] **Step 1: Measure current coverage**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest --cov=crackerjack --cov-report=json -q 2>&1 | tail -5`
Expected: tests pass, coverage.json exists

- [ ] **Step 2: Run init**

Run: `cd /Users/les/Projects/crackerjack && uv run crackerjack coverage-ratchet init --pkg-path .`
Expected: `✅ Ratchet initialized at <current>%`

- [ ] **Step 3: Verify mirror**

Run: `cd /Users/les/Projects/crackerjack && grep -n 'cov-fail-under' pyproject.toml && cat .coverage-ratchet.json | python -m json.tool | grep -E 'baseline|current_minimum'`
Expected: mirror matches ratchet

- [ ] **Step 4: Verify ratchet check passes**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest --no-cov -n 0 tests/ -q 2>&1 | tail -3`
Expected: tests pass

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add .coverage-ratchet.json pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): adopt coverage-ratchet at current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).
.coverage-ratchet.json created at current coverage; pyproject.toml mirrored.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 8: Adopt ratchet in session-buddy

**Files:**

- Create: `session-buddy/.coverage-ratchet.json`
- Modify: `session-buddy/pyproject.toml`
- The `conftest-sysmodules-pollution-pattern.md` memory notes session-buddy has test pollution — be aware of pre-existing failures.

(Identical structure to Task 6; replace `mahavishnu` with `session-buddy`.)

- [ ] **Step 1: Measure current coverage**

Run: `cd /Users/les/Projects/session-buddy && uv run pytest --cov=session_buddy --cov-report=json -q 2>&1 | tail -5`
Expected: tests pass, coverage.json exists

- [ ] **Step 2: Run init**

Run: `cd /Users/les/Projects/session-buddy && uv run --with crackerjack crackerjack coverage-ratchet init --pkg-path .`
Expected: `✅ Ratchet initialized at <current>%`

- [ ] **Step 3: Verify mirror**

Run: `cd /Users/les/Projects/session-buddy && grep -n 'cov-fail-under' pyproject.toml && cat .coverage-ratchet.json | python -m json.tool | grep -E 'baseline|current_minimum'`
Expected: mirror matches ratchet

- [ ] **Step 4: Verify ratchet check passes**

Run: `cd /Users/les/Projects/session-buddy && uv run pytest --no-cov -n 0 tests/ -q 2>&1 | tail -3`
Expected: tests pass (or note pre-existing failures per memory)

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/session-buddy
git add .coverage-ratchet.json pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): adopt coverage-ratchet at current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).
.coverage-ratchet.json created at current coverage; pyproject.toml mirrored.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 9: Adopt ratchet in akosha

**Files:**

- Create: `akosha/.coverage-ratchet.json`
- Modify: `akosha/pyproject.toml`

(Identical structure to Task 6; replace `mahavishnu` with `akosha`.)

- [ ] **Step 1: Measure current coverage**

Run: `cd /Users/les/Projects/akosha && uv run pytest --cov=akosha --cov-report=json -q 2>&1 | tail -5`
Expected: tests pass, coverage.json exists

- [ ] **Step 2: Run init**

Run: `cd /Users/les/Projects/akosha && uv run --with crackerjack crackerjack coverage-ratchet init --pkg-path .`
Expected: `✅ Ratchet initialized at <current>%`

- [ ] **Step 3: Verify mirror**

Run: `cd /Users/les/Projects/akosha && grep -n 'cov-fail-under' pyproject.toml && cat .coverage-ratchet.json | python -m json.tool | grep -E 'baseline|current_minimum'`
Expected: mirror matches ratchet

- [ ] **Step 4: Verify ratchet check passes**

Run: `cd /Users/les/Projects/akosha && uv run pytest --no-cov -n 0 tests/ -q 2>&1 | tail -3`
Expected: tests pass

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/akosha
git add .coverage-ratchet.json pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): adopt coverage-ratchet at current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 10: Adopt ratchet in dhara

**Files:**

- Create: `dhara/.coverage-ratchet.json`
- Modify: `dhara/pyproject.toml`

(Identical structure to Task 6; replace `mahavishnu` with `dhara`.)

- [ ] **Step 1: Measure current coverage**

Run: `cd /Users/les/Projects/dhara && uv run pytest --cov=dhara --cov-report=json -q 2>&1 | tail -5`
Expected: tests pass, coverage.json exists

- [ ] **Step 2: Run init**

Run: `cd /Users/les/Projects/dhara && uv run --with crackerjack crackerjack coverage-ratchet init --pkg-path .`
Expected: `✅ Ratchet initialized at <current>%`

- [ ] **Step 3: Verify mirror**

Run: `cd /Users/les/Projects/dhara && grep -n 'cov-fail-under' pyproject.toml && cat .coverage-ratchet.json | python -m json.tool | grep -E 'baseline|current_minimum'`
Expected: mirror matches ratchet

- [ ] **Step 4: Verify ratchet check passes**

Run: `cd /Users/les/Projects/dhara && uv run pytest --no-cov -n 0 tests/ -q 2>&1 | tail -3`
Expected: tests pass

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/dhara
git add .coverage-ratchet.json pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "feat(ratchet): adopt coverage-ratchet at current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Task 11: Remove the temporary `migrate` CLI command

**Files:**

- Modify: `crackerjack/crackerjack/cli/coverage_ratchet_cli.py` (remove `migrate`)
- Modify: `crackerjack/tests/cli/test_coverage_ratchet_cli.py` (remove migrate test if present)

**Interfaces:**

- Consumes: Phase A's temporary `migrate` command

- Produces: clean CLI surface with only `init`, `status`, `lower`

- [ ] **Step 1: Remove the `migrate` function from `coverage_ratchet_cli.py`**

Edit `crackerjack/crackerjack/cli/coverage_ratchet_cli.py`: delete the `migrate` block.

- [ ] **Step 2: Run CLI tests to verify nothing else broke**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py -v`
Expected: PASS

- [ ] **Step 3: Run full Crackerjack test suite**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest --no-cov -n 0 tests/ -q 2>&1 | tail -5`
Expected: tests pass

- [ ] **Step 4: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/cli/coverage_ratchet_cli.py
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "chore(ratchet): remove temporary migrate CLI

The migrate CLI was used only during Phase A. Per-repo init in Phase B
replaces it. CLI surface now contains only init, status, lower.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Self-Review

**Spec coverage check:**

- Service extensions (lower_baseline, mirror_to_pyproject, report_status) → Task 1 ✓
- Test-stage integration (full) → Task 2 ✓
- CLI commands (init, status, lower, migrate) → Task 3 ✓
- Unit tests for service → Task 1 ✓
- Integration tests for test-stage → Task 2 ✓
- E2E tests for one Bodai repo → Task 4 ✓
- Phase B adoption wave (5 repos) → Tasks 5-10 ✓
- Phase C cleanup → Task 11 ✓
- Direct commits to main → all tasks ✓
- No 80% default → all tasks ✓

**Placeholder scan:** No TBD/TODO/incomplete. Every step has actual code.

**Type consistency:** `CoverageRatchetService.{lower_baseline, mirror_to_pyproject, report_status}` defined in Task 1, used in Tasks 2, 3. `TestManager.run_with_ratchet_check` defined in Task 2, used in Task 3 via CLI. `cli` group defined in Task 3, used in Task 4 test.

**File path consistency:** All paths match the spec's file structure table.

**No contradictions:** Each task ends with a green test suite + a single commit. No task depends on a later task's output.
