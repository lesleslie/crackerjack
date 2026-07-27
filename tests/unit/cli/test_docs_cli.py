"""Tests for crackerjack docs CLI subcommand (Task 10) — RED first."""

from __future__ import annotations

import json
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


@pytest.mark.unit
class TestDocsValidateNewFlags:
    """Task 5: docs validate now uses --repo-root + --allow-nonstandard/--strict-frontmatter."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    @pytest.fixture
    def repo_with_passing_doc(self, tmp_path: Path) -> Path:
        """Create a temp repo with one valid doc."""
        (tmp_path / "docs" / "plans").mkdir(parents=True)
        (tmp_path / "docs" / "plans" / "ok.md").write_text(
            (
                "---\n"
                "status: draft\n"
                "role: canonical\n"
                "date: 2026-07-26\n"
                "last_reviewed: 2026-07-26\n"
                "topic: lifecycle\n"
                "---\n"
                "# Hi\n"
            ),
            encoding="utf-8",
        )
        return tmp_path

    def test_validate_repo_root_flag_accepted(
        self, runner: CliRunner, repo_with_passing_doc: Path
    ) -> None:
        """`docs validate --repo-root PATH` accepts the new flag."""
        from crackerjack.cli.docs_cli import app

        result = runner.invoke(
            app,
            ["validate", "--repo-root", str(repo_with_passing_doc), "--json"],
        )
        assert result.exit_code == 0, result.output

    def test_validate_auto_detects_repo_root(
        self,
        runner: CliRunner,
        repo_with_passing_doc: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without --repo-root, the CLI walks up to find .git."""
        from crackerjack.cli.docs_cli import app

        (repo_with_passing_doc / ".git").mkdir()
        monkeypatch.chdir(repo_with_passing_doc)
        result = runner.invoke(app, ["validate", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["files_scanned"] >= 1

    def test_validate_outside_git_repo_errors_when_no_repo_root(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --repo-root and outside a git repo, the CLI errors out."""
        from crackerjack.cli.docs_cli import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["validate"])
        # Should fail because not in a git repo (no .git above tmp_path).
        assert result.exit_code != 0

    def test_validate_repo_root_must_be_directory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """A non-existent --repo-root errors out."""
        from crackerjack.cli.docs_cli import app

        result = runner.invoke(
            app,
            ["validate", "--repo-root", "/nonexistent/path/that/does/not/exist"],
        )
        assert result.exit_code != 0

    def test_validate_strict_frontmatter_exits_one_on_missing(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--strict-frontmatter rejects missing-frontmatter files."""
        from crackerjack.cli.docs_cli import app

        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "legacy.md").write_text("# No frontmatter\n", encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "validate",
                "--repo-root",
                str(tmp_path),
                "--strict-frontmatter",
                "--json",
            ],
        )
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert payload["error_count"] >= 1
        codes = {e["code"] for e in payload["errors"]}
        assert "MISSING_FRONTMATTER" in codes

    def test_validate_allow_nonstandard_passes_with_missing_frontmatter(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Default --allow-nonstandard tolerates missing-frontmatter (the bug-fix)."""
        from crackerjack.cli.docs_cli import app

        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "legacy.md").write_text("# No frontmatter\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["validate", "--repo-root", str(tmp_path), "--json"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["files_scanned"] == 1

    def test_validate_strict_promotes_warnings_to_exit_one(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """`--strict` causes exit 1 when warnings are present."""
        from crackerjack.cli.docs_cli import app

        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "warny.md").write_text(
            (
                "---\n"
                "status: draft\n"
                "role: canonical\n"
                "date: 2026-07-26\n"
                "last_reviewed: 2026-07-26\n"
                "topic: lifecycle\n"
                "---\n"
                "# Hi\n"
            ),
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["validate", "--repo-root", str(tmp_path), "--strict", "--json"],
        )
        # If warnings were produced, exit 1; otherwise exit 0.
        payload = json.loads(result.output)
        if payload["warning_count"] > 0:
            assert result.exit_code == 1
        else:
            assert result.exit_code == 0

    def test_validate_json_output_schema(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """The --json output has stable, documented keys."""
        from crackerjack.cli.docs_cli import app

        result = runner.invoke(
            app, ["validate", "--repo-root", str(tmp_path), "--json"]
        )
        payload = json.loads(result.output)
        expected_keys = {"success", "files_scanned", "errors", "warnings", "duration_ms"}
        assert expected_keys.issubset(set(payload.keys()))
        assert isinstance(payload["errors"], list)
        assert isinstance(payload["warnings"], list)
