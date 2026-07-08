"""Tests for :meth:`FixerRegistry.from_disk` (PR 8's real loader).

The loader walks ``auto_fixers/{signature}.py`` files, imports each
one, and registers the resulting module under its filename stem as
the auto-promoted signature. Security: every file must be in the
manifest (``auto_fixers/manifest.json``) AND pass AST validation.
Tests cover: empty dir, missing dir, valid loads, broken files,
manifest mismatches, banned imports, dunder access, and the
round-trip that the PromotionPipeline depends on.
"""

from __future__ import annotations

import datetime
import logging
import textwrap
from pathlib import Path

from crackerjack.ai_fix.auto_fixers_manifest import (
    Manifest,
    ManifestEntry,
    sha256_of_file,
    write_manifest,
)
from crackerjack.ai_fix.fixer_registry import FixerRegistry


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_trusted_fixer(
    auto_fixers_dir: Path, signature: str, source: str | None = None
) -> Path:
    """Write a fixer file *and* add it to the manifest.

    Mirrors what :class:`GhPRCreator` does in production. Without
    the manifest entry the loader refuses the file, so a plain
    ``write_text`` here is no longer enough.
    """
    auto_fixers_dir.mkdir(parents=True, exist_ok=True)
    fixer_path = auto_fixers_dir / f"{signature}.py"
    fixer_path.write_text(
        source if source is not None else "def apply(signature, issue):\n    return {}\n",
        encoding="utf-8",
    )
    manifest_path = auto_fixers_dir / "manifest.json"
    if manifest_path.exists():
        manifest = __import__(
            "crackerjack.ai_fix.auto_fixers_manifest",
            fromlist=["load_manifest"],
        ).load_manifest(manifest_path)
    else:
        manifest = Manifest(version=1, fixers={})
    manifest.fixers[signature] = ManifestEntry(
        signature=signature,
        sha256=sha256_of_file(fixer_path),
        promoted_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
    write_manifest(manifest, manifest_path)
    return fixer_path


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
# 2. Trusted single fixer (manifest + AST both pass)
# ---------------------------------------------------------------------------


class TestSingleFixer:
    """A trusted .py file becomes a registered auto-promoted fixer."""

    def test_loads_one_fixer(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        _write_trusted_fixer(
            d,
            "sig_abc",
            textwrap.dedent(
                """
                def apply(signature, issue):
                    return {"success": True, "files_modified": []}
                """
            ),
        )
        registry = FixerRegistry.from_disk(d)
        assert "sig_abc" in registry.list_signatures()
        fixer = registry.get_signature("sig_abc")
        assert fixer is not None
        assert callable(getattr(fixer, "apply", None))

    def test_signature_matches_filename_stem(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        _write_trusted_fixer(d, "type_error_unbound", "x = 1\n")
        _write_trusted_fixer(d, "import_error_missing", "x = 2\n")
        registry = FixerRegistry.from_disk(d)
        assert set(registry.list_signatures()) == {
            "type_error_unbound",
            "import_error_missing",
        }


# ---------------------------------------------------------------------------
# 3. Broken / untrusted files are refused
# ---------------------------------------------------------------------------


class TestBrokenFile:
    """A file without a manifest entry, or with a broken import, is refused."""

    def test_no_manifest_entry_refused(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        # File is present, manifest is NOT — this is the untrusted-file scenario.
        (d / "untrusted.py").write_text("x = 1\n")
        registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []

    def test_manifest_hash_mismatch_refused(
        self, tmp_path: Path, caplog
    ) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        _write_trusted_fixer(d, "good", "x = 1\n")
        # Now mutate the file after the manifest was written. Hash
        # no longer matches → refused.
        (d / "good.py").write_text("x = 999\n")

        with caplog.at_level(
            logging.WARNING, logger="crackerjack.ai_fix.fixer_registry"
        ):
            registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []
        assert any("hash mismatch" in r.message for r in caplog.records)

    def test_syntax_error_is_skipped(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        # Manually write a file with valid manifest but broken syntax.
        (d / "broken.py").write_text("def apply()\n    return {}\n")
        # The manifest entry is created from the broken file (the test
        # is a "passes the AST gate, fails at import" scenario). Write
        # a sibling that IS valid and add both to the manifest.
        (d / "good.py").write_text("x = 1\n")
        from crackerjack.ai_fix.auto_fixers_manifest import load_manifest

        m = Manifest(version=1, fixers={})
        for sig in ("broken", "good"):
            m.fixers[sig] = ManifestEntry(
                signature=sig,
                sha256=sha256_of_file(d / f"{sig}.py"),
                promoted_at=datetime.datetime.now(datetime.UTC).isoformat(),
            )
        write_manifest(m, d / "manifest.json")

        registry = FixerRegistry.from_disk(d)
        # The valid one loads, the broken one is refused.
        assert "good" in registry.list_signatures()
        assert "broken" not in registry.list_signatures()


# ---------------------------------------------------------------------------
# 4. Banned imports and dunder access (AST gate)
# ---------------------------------------------------------------------------


class TestASTGate:
    """A trusted file with a banned import or dunder access is refused."""

    def test_banned_import_os_refused(self, tmp_path: Path, caplog) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        _write_trusted_fixer(d, "evil", "import os\n")
        with caplog.at_level(
            logging.WARNING, logger="crackerjack.ai_fix.fixer_registry"
        ):
            registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []
        assert any("banned imports: os" in r.message for r in caplog.records)

    def test_banned_import_subprocess_refused(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        _write_trusted_fixer(d, "evil", "from subprocess import run\n")
        registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []

    def test_banned_dunder_refused(self, tmp_path: Path, caplog) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        _write_trusted_fixer(d, "evil", "x = __import__('os').system('rm -rf /')\n")
        with caplog.at_level(
            logging.WARNING, logger="crackerjack.ai_fix.fixer_registry"
        ):
            registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []

    def test_getattr_with_banned_dunder_refused(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        _write_trusted_fixer(d, "evil", "x = getattr(object, '__subclasses__')()\n")
        registry = FixerRegistry.from_disk(d)
        assert registry.list_signatures() == []

    def test_allowed_dunder_passes(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        d.mkdir()
        _write_trusted_fixer(
            d,
            "ok",
            "__all__ = ['apply']\ndef apply(signature, issue):\n    return {}\n",
        )
        registry = FixerRegistry.from_disk(d)
        assert "ok" in registry.list_signatures()


# ---------------------------------------------------------------------------
# 5. Round-trip with PromotionPipeline
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """A file written by :class:`GhPRCreator` can be loaded back by ``from_disk``.

    This is the contract the self-improving loop depends on: a
    successful promotion writes a file *and* a manifest entry, the
    next run loads it as a built-in mechanical fixer.
    """

    def test_signature_round_trip(self, tmp_path: Path) -> None:
        d = tmp_path / "auto_fixers"
        for sig in ("abc123", "type_error_42", "import-missing-1"):
            _write_trusted_fixer(d, sig, "x = 1\n")
        registry = FixerRegistry.from_disk(d)
        assert set(registry.list_signatures()) == {
            "abc123",
            "type_error_42",
            "import-missing-1",
        }
