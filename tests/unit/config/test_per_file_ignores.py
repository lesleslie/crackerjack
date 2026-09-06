"""Tests for the universal per-file-ignores starter pack mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.config.per_file_ignores import (
    UNIVERSAL_PER_FILE_IGNORES,
    build_inline_per_file_ignores,
)


class TestUniversalPerFileIgnores:
    """The starter pack should contain exactly the rules we agreed on."""

    def test_scripts_starter_pack_has_universal_rules(self) -> None:
        scripts_rules = UNIVERSAL_PER_FILE_IGNORES["scripts/**/*.py"]
        expected = {
            "EXE001",
            "BLE001",
            "F541",
            "C901",
            "SIM102",
            "SIM103",
            "SIM114",
            "S110",
            "PLW1510",
        }
        assert set(scripts_rules) == expected

    def test_examples_starter_pack_inherits_and_extends(self) -> None:
        examples_rules = UNIVERSAL_PER_FILE_IGNORES["examples/**/*.py"]
        scripts_rules = UNIVERSAL_PER_FILE_IGNORES["scripts/**/*.py"]
        for rule in scripts_rules:
            assert rule in examples_rules, f"missing {rule} in examples"
        assert "N999" in examples_rules
        assert "RUF100" in examples_rules
        assert "FURB162" in examples_rules

    def test_no_tc003_in_starter_pack(self) -> None:
        """TC003 catches real runtime bugs. Must NOT be silenced."""
        for rules in UNIVERSAL_PER_FILE_IGNORES.values():
            assert "TC003" not in rules

    def test_underscore_prefixed_scripts_get_n999(self) -> None:
        assert UNIVERSAL_PER_FILE_IGNORES["scripts/_*.py"] == ["N999"]

    def test_backup_files_get_all_silenced(self) -> None:
        assert UNIVERSAL_PER_FILE_IGNORES["**/*.bak[0-9]"] == ["ALL"]


class TestBuildInlinePerFileIgnores:
    """The inline TOML string: returns the right shape and rules."""

    def test_returns_inline_table_string(self) -> None:
        result = build_inline_per_file_ignores()
        assert result.startswith("{")
        assert result.endswith("}")

    def test_contains_all_four_patterns(self) -> None:
        result = build_inline_per_file_ignores()
        assert '"scripts/**/*.py"' in result
        assert '"examples/**/*.py"' in result
        assert '"scripts/_*.py"' in result
        assert '"**/*.bak[0-9]"' in result

    def test_contains_universal_rules(self) -> None:
        result = build_inline_per_file_ignores()
        for rule in [
            "EXE001",
            "BLE001",
            "F541",
            "C901",
            "SIM102",
            "SIM103",
            "SIM114",
            "S110",
            "PLW1510",
        ]:
            assert f'"{rule}"' in result

    def test_examples_includes_three_extra_rules(self) -> None:
        result = build_inline_per_file_ignores()
        assert '"N999"' in result
        assert '"RUF100"' in result
        assert '"FURB162"' in result

    def test_optional_writes_debug_file_when_repo_root_given(
        self, tmp_path: Path
    ) -> None:
        """If repo_root is provided, also write a debug copy."""
        result = build_inline_per_file_ignores(tmp_path)
        debug = (
            tmp_path / ".crackerjack_cache" / "scripts_examples_per_file_ignores.toml"
        )
        assert debug.exists()
        # The debug file is the inline expression wrapped in [lint] section.
        content = debug.read_text()
        assert "[lint]" in content
        assert "extend-per-file-ignores = " in content
        assert result in content

    def test_no_repo_root_does_not_create_files(self, tmp_path: Path) -> None:
        """If repo_root is None, do NOT touch the filesystem."""
        # Run from a tmp cwd; ensure no .crackerjack_cache appears.
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            build_inline_per_file_ignores()
            assert not (tmp_path / ".crackerjack_cache").exists()
        finally:
            os.chdir(original_cwd)


@pytest.mark.integration
class TestRuffAcceptsInlineConfig:
    """Verify ruff actually parses our inline TOML correctly AND preserves
    consumer auto-discovery."""

    def test_ruff_check_with_inline_config_silences_shebang(
        self, tmp_path: Path
    ) -> None:
        """The inline config silences EXE001 on a shebang file."""
        import subprocess

        inline = build_inline_per_file_ignores()
        sample_dir = tmp_path / "scripts"
        sample_dir.mkdir()
        sample = sample_dir / "sample.py"
        sample.write_text("#!/usr/bin/env python3\nprint('hello')\n")
        result = subprocess.run(
            [
                "ruff",
                "check",
                "--no-fix",
                "--select",
                "EXE001",
                "--config",
                f"lint.extend-per-file-ignores = {inline}",
                str(sample_dir),
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        assert result.returncode == 0, (
            f"ruff rejected our inline config:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_inline_config_preserves_consumer_pyproject(self, tmp_path: Path) -> None:
        """The inline config must NOT replace consumer pyproject.toml."""
        import subprocess

        # Consumer pyproject.toml silences B007 in scripts/.
        (tmp_path / "pyproject.toml").write_text(
            '[tool.ruff.lint.per-file-ignores]\n"scripts/**/*.py" = ["B007"]\n'
        )
        # Crackerjack's starter pack does NOT include B007.
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "loop.py").write_text("for i in range(10): pass\n")
        inline = build_inline_per_file_ignores()
        result = subprocess.run(
            [
                "ruff",
                "check",
                "--no-fix",
                "--select",
                "B007",
                "--config",
                f"lint.extend-per-file-ignores = {inline}",
                str(scripts_dir),
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        # If auto-discovery is preserved, B007 (from consumer) stays silenced;
        # ruff returns 0. If --config replaced auto-discovery, B007 would fire
        # and return non-zero.
        assert result.returncode == 0, (
            f"inline --config replaced consumer auto-discovery:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
