"""Tests for :meth:`FixerRegistry.from_disk` (PR 8's real loader).

The loader walks ``auto_fixers/{signature}.py`` files, imports each
one, and registers the resulting module under its filename stem as
the auto-promoted signature. Tests cover: empty dir, missing dir,
single file, multiple files, broken file (skipped, not fatal),
and the round-trip that the PromotionPipeline depends on.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from crackerjack.ai_fix.fixer_registry import FixerRegistry


# ---------------------------------------------------------------------------
# 1. Empty / missing directories
# ---------------------------------------------------------------------------


class TestEmptyOrMissingDir:
    """``from_disk`` never raises on an empty or missing directory."""

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        registry = FixerRegistry.from_disk(tmp_path / "does_not_exist")
        assert registry.list_signatures() == []
        assert registry.has_mechanical_fixer("ANY") is False

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "auto_fixers"
        empty.mkdir()
        registry = FixerRegistry.from_disk(empty)
        assert registry.list_signatures() == []

    def test_dir_with_only_non_py_files(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        (d / "readme.md").write_text("not a fixer\n")
        (d / "config.json").write_text("{}\n")
        registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []


# ---------------------------------------------------------------------------
# 2. Single fixer
# ---------------------------------------------------------------------------


class TestSingleFixer:
    """A single .py file becomes a registered auto-promoted fixer."""

    def test_loads_one_fixer(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        (d / "sig_abc.py").write_text(
            textwrap.dedent(
                """
                def apply(signature, issue):
                    return {"success": True, "files_modified": []}
                """
            )
        )
        registry = FixerRegistry.from_disk(d)
        assert "sig_abc" in registry.list_signatures()
        # The registered fixer is the module.
        fixer = registry.get_signature("sig_abc")
        assert fixer is not None
        assert callable(getattr(fixer, "apply", None))

    def test_signature_matches_filename_stem(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        # Two fixers with different signatures.
        (d / "type_error_unbound.py").write_text("x = 1\n")
        (d / "import_error_missing.py").write_text("x = 2\n")
        registry = FixerRegistry.from_disk(d)
        assert set(registry.list_signatures()) == {
            "type_error_unbound",
            "import_error_missing",
        }


# ---------------------------------------------------------------------------
# 3. Broken file
# ---------------------------------------------------------------------------


class TestBrokenFile:
    """A broken .py file is logged and skipped, not fatal."""

    def test_syntax_error_is_skipped(self, tmp_path: Path, caplog) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        # Intentionally broken: missing colon.
        (d / "broken.py").write_text("def apply()\n    return {}\n")
        # A valid one to confirm partial loading.
        (d / "good.py").write_text("x = 1\n")

        import logging
        with caplog.at_level(logging.WARNING, logger="crackerjack.ai_fix.fixer_registry"):
            registry = FixerRegistry.from_disk(d)

        assert "good" in registry.list_signatures()
        assert "broken" not in registry.list_signatures()
        # A warning should be logged for the broken file.
        assert any("broken" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 4. Round-trip with PromotionPipeline
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """A file written by :class:`GhPRCreator` can be loaded back by ``from_disk``.

    This is the contract the self-improving loop depends on: a
    successful promotion writes a file, the next run loads it as
    a built-in mechanical fixer. We exercise the write half
    implicitly by writing a fixer-shaped file with the right name
    pattern, then loading.
    """

    def test_signature_round_trip(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        # The filename-safe pattern: alphanumerics, underscores, hyphens.
        for sig in ("abc123", "type_error_42", "import-missing-1", "longSig" * 2):
            (d / f"{sig}.py").write_text("x = 1\n")
        registry = FixerRegistry.from_disk(d)
        # All 4 should be loaded (longSig*2 is 14 chars, under 64 limit).
        assert len(registry.list_signatures()) == 4
