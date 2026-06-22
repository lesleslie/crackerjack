"""Tests for crackerjack docs CLI subcommand (Task 10) — RED first."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner


@pytest.mark.unit
class TestDocsInitCreatesZensicalToml:
    def test_docs_init_creates_zensical_toml(self, tmp_path: Path) -> None:
        """docs init command creates zensical.toml at target repo root."""
        from crackerjack.cli.docs_cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["init", "--path", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "zensical.toml").exists()


@pytest.mark.unit
class TestDocsBuildCallsZensicalBuild:
    def test_docs_build_calls_zensical_build(self, tmp_path: Path) -> None:
        """docs build command invokes zensical build subprocess."""
        from crackerjack.cli.docs_cli import app

        (tmp_path / "zensical.toml").write_text("[project]\nsite_name = 'Test'\n")

        runner = CliRunner()
        with patch("crackerjack.cli.docs_cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(app, ["build", "--path", str(tmp_path)])

        assert result.exit_code == 0, result.output
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "zensical" in cmd
        assert "build" in cmd


@pytest.mark.unit
class TestDocsServeCallsZensicalServe:
    def test_docs_serve_calls_zensical_serve(self, tmp_path: Path) -> None:
        """docs serve command invokes zensical serve subprocess."""
        from crackerjack.cli.docs_cli import app

        (tmp_path / "zensical.toml").write_text("[project]\nsite_name = 'Test'\n")

        runner = CliRunner()
        with patch("crackerjack.cli.docs_cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(app, ["serve", "--path", str(tmp_path)])

        assert result.exit_code == 0, result.output
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "zensical" in cmd
        assert "serve" in cmd


@pytest.mark.unit
class TestDocsAiFixInvokesEnricher:
    def test_docs_ai_fix_invokes_enricher(self, tmp_path: Path) -> None:
        """docs ai-fix command creates DocstringEnricher and calls enrich()."""
        from crackerjack.cli.docs_cli import app

        src = tmp_path / "module.py"
        src.write_text("def foo(x: int) -> int:\n    return x\n")

        runner = CliRunner()
        with patch("crackerjack.cli.docs_cli.DocstringEnricher") as MockEnricher:
            mock_instance = MagicMock()
            mock_instance.enrich = AsyncMock(
                return_value=MagicMock(enriched=1, skipped=0, report_only=[])
            )
            MockEnricher.return_value = mock_instance

            result = runner.invoke(app, ["ai-fix", "--path", str(tmp_path)])

        assert result.exit_code == 0, result.output
        MockEnricher.assert_called_once()
        mock_instance.enrich.assert_called()
