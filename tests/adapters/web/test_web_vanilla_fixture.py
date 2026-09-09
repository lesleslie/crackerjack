"""Web fixture smoke + fixture-reference contract."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from crackerjack.adapters.web import WebAdapter
from crackerjack.adapters.web.hooks import web_hooks

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "web-vanilla"


class TestFixtureDetection:
    def test_fixture_exists(self) -> None:
        assert FIXTURE.is_dir()

    def test_adapter_detects_fixture(self) -> None:
        assert WebAdapter().detect(FIXTURE) is True

    def test_capabilities_exposes_four_hooks(self) -> None:
        caps = WebAdapter().capabilities(FIXTURE)
        assert len(caps.hooks) == 4


@pytest.mark.real_web_smoke
class TestRealCli:
    """Opt-in smoke tests: skipped if npx or the per-tool CLI is unavailable."""

    def test_stylelint_runs_against_fixture(self) -> None:
        if shutil.which("npx") is None:
            pytest.skip("npx not available")
        result = subprocess.run(
            ["npx", "--no", "stylelint", str(FIXTURE / "src" / "style.css")],
            capture_output=True,
            text=True,
            cwd=FIXTURE,
        )
        # stylelint exits 0 (clean) or 2 (issues found). Anything else = crash.
        assert result.returncode in (0, 2), f"stylelint crashed: {result.stderr}"

    def test_tsc_compiles_fixture(self) -> None:
        if shutil.which("npx") is None:
            pytest.skip("npx not available")
        result = subprocess.run(
            ["npx", "--no", "--", "tsc", "--noEmit"],
            capture_output=True,
            text=True,
            cwd=FIXTURE,
        )
        assert result.returncode == 0, f"tsc failed: {result.stderr}"
