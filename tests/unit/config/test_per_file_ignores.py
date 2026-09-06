"""Tests for the universal per-file-ignores starter pack mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.config.per_file_ignores import (
    UNIVERSAL_PER_FILE_IGNORES,
    ensure_per_file_ignores_file,
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


class TestEnsurePerFileIgnoresFile:
    """The file lifecycle: create, idempotent, valid TOML."""

    def test_creates_file_with_correct_path(self, tmp_path: Path) -> None:
        result = ensure_per_file_ignores_file(tmp_path)
        assert (
            result
            == tmp_path
            / ".crackerjack_cache"
            / "scripts_examples_per_file_ignores.toml"
        )
        assert result.exists()

    def test_creates_cache_dir_if_missing(self, tmp_path: Path) -> None:
        assert not (tmp_path / ".crackerjack_cache").exists()
        ensure_per_file_ignores_file(tmp_path)
        assert (tmp_path / ".crackerjack_cache").exists()

    def test_idempotent_on_repeat_calls(self, tmp_path: Path) -> None:
        first = ensure_per_file_ignores_file(tmp_path)
        first_mtime = first.stat().st_mtime_ns
        second = ensure_per_file_ignores_file(tmp_path)
        assert first == second
        assert second.stat().st_mtime_ns == first_mtime

    def test_generated_toml_parses_with_tomllib(self, tmp_path: Path) -> None:
        import tomllib

        result = ensure_per_file_ignores_file(tmp_path)
        content = result.read_text()
        parsed = tomllib.loads(content)
        # New format: [lint].extend-per-file-ignores = { ... }
        assert "lint" in parsed
        assert "extend-per-file-ignores" in parsed["lint"]
        mapping = parsed["lint"]["extend-per-file-ignores"]
        assert "scripts/**/*.py" in mapping
        assert "examples/**/*.py" in mapping
        assert "scripts/_*.py" in mapping
        assert "**/*.bak[0-9]" in mapping

    def test_generated_toml_has_ruff_compatible_format(self, tmp_path: Path) -> None:
        """Ruff parses --config files as TOML with a [lint.*] section."""
        result = ensure_per_file_ignores_file(tmp_path)
        content = result.read_text()
        # First non-blank line must be a [lint.*] section header.
        first = next(line for line in content.splitlines() if line.strip())
        assert first.startswith("[lint"), (
            f"expected TOML header under [lint.*], got: {first!r}"
        )
        # Must use the additive extend-per-file-ignores key.
        assert "extend-per-file-ignores" in content
        # Must NOT use the replacing per-file-ignores key.
        assert "\nper-file-ignores" not in content


@pytest.mark.integration
class TestRuffAcceptsGeneratedFile:
    """Verify ruff actually parses our generated file correctly."""

    def test_ruff_check_with_generated_ignores_does_not_error(
        self, tmp_path: Path
    ) -> None:
        """If ruff rejects our generated TOML, the hook would fail loudly."""
        import subprocess

        per_file_ignores = ensure_per_file_ignores_file(tmp_path)
        sample_dir = tmp_path / "scripts"
        sample_dir.mkdir()
        sample = sample_dir / "sample.py"
        sample.write_text("#!/usr/bin/env python3\nprint('hello')\n")
        result = subprocess.run(
            [
                "ruff",
                "check",
                "--config",
                str(per_file_ignores),
                "--no-fix",
                str(sample_dir),
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        assert result.returncode == 0, (
            f"ruff rejected our config file:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
