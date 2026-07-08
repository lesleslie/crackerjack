"""Unit tests for :mod:`crackerjack.ai_fix.auto_fixers_manifest`.

The manifest is the trust boundary for the auto_fixers/
directory. Tests cover:

* Read/write round-trip of the manifest
* Hash verification (file hash must match the manifest entry)
* AST validation (banned imports, banned builtins, dunder access)
* Missing / corrupt manifest handling
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from crackerjack.ai_fix.auto_fixers_manifest import (
    ALLOWED_DUNDER_ATTRS,
    BANNED_BUILTIN_CALLS,
    BANNED_IMPORTS,
    MANIFEST_VERSION,
    Manifest,
    ManifestEntry,
    ast_validate_fixer_source,
    empty_manifest,
    load_manifest,
    sha256_of_file,
    verify_against_manifest,
    write_manifest,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstantContract:
    """The values are part of the public contract; renaming is a breaking change."""

    def test_manifest_version_is_1(self) -> None:
        assert MANIFEST_VERSION == 1

    def test_banned_imports_includes_dangerous_modules(self) -> None:
        for module in ("os", "subprocess", "socket", "urllib", "importlib", "ctypes"):
            assert module in BANNED_IMPORTS, f"{module!r} should be in BANNED_IMPORTS"

    def test_banned_builtins_includes_escape_hatches(self) -> None:
        for name in ("__import__", "eval", "exec", "compile", "globals", "locals"):
            assert name in BANNED_BUILTIN_CALLS

    def test_allowed_dunder_is_minimal(self) -> None:
        # If you're tempted to add to this, think twice: each
        # entry is a privilege the auto-promoted fixer gets.
        assert ALLOWED_DUNDER_ATTRS == frozenset(
            {"__name__", "__doc__", "__file__", "__all__"}
        )


# ---------------------------------------------------------------------------
# Empty / manifest round-trip
# ---------------------------------------------------------------------------


class TestEmptyManifest:
    def test_empty_manifest_is_trust_nothing(self) -> None:
        m = empty_manifest()
        assert m.version == MANIFEST_VERSION
        assert m.fixers == {}
        assert m.get("any") is None

    def test_write_then_load_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        manifest = Manifest(
            version=1,
            fixers={
                "abc": ManifestEntry(
                    signature="abc", sha256="deadbeef", promoted_at="2026-07-07T00:00:00Z"
                )
            },
        )
        write_manifest(manifest, path)
        loaded = load_manifest(path)
        assert loaded.version == 1
        assert "abc" in loaded.fixers
        assert loaded.fixers["abc"].sha256 == "deadbeef"
        assert loaded.fixers["abc"].promoted_at == "2026-07-07T00:00:00Z"

    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        m = load_manifest(tmp_path / "does_not_exist.json")
        assert m == empty_manifest()

    def test_load_corrupt_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("not valid json {{{\n", encoding="utf-8")
        m = load_manifest(path)
        assert m == empty_manifest()

    def test_load_wrong_version_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({"version": 99, "fixers": {}}), encoding="utf-8")
        m = load_manifest(path)
        assert m == empty_manifest()

    def test_atomic_write_uses_tmp_and_rename(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        write_manifest(empty_manifest(), path)
        # The .tmp file should not be left behind on a successful write.
        assert list(tmp_path.glob("*.tmp")) == []
        assert path.exists()

    def test_get_returns_entry(self) -> None:
        m = Manifest(
            version=1,
            fixers={"abc": ManifestEntry("abc", "h", "t")},
        )
        assert m.get("abc") is not None
        assert m.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Hash verification
# ---------------------------------------------------------------------------


class TestVerifyAgainstManifest:
    """``verify_against_manifest`` is the gate the loader uses."""

    def test_matching_hash_verifies(self, tmp_path: Path) -> None:
        fixer = tmp_path / "abc.py"
        fixer.write_text("x = 1\n", encoding="utf-8")
        manifest = Manifest(
            version=1,
            fixers={
                "abc": ManifestEntry(
                    signature="abc",
                    sha256=sha256_of_file(fixer),
                    promoted_at="t",
                )
            },
        )
        ok, reason = verify_against_manifest(fixer, manifest)
        assert ok is True
        assert reason == "ok"

    def test_missing_entry_denied(self, tmp_path: Path) -> None:
        fixer = tmp_path / "abc.py"
        fixer.write_text("x = 1\n", encoding="utf-8")
        ok, reason = verify_against_manifest(fixer, empty_manifest())
        assert ok is False
        assert "no manifest entry" in reason

    def test_hash_mismatch_denied(self, tmp_path: Path) -> None:
        fixer = tmp_path / "abc.py"
        fixer.write_text("x = 1\n", encoding="utf-8")
        manifest = Manifest(
            version=1,
            fixers={
                "abc": ManifestEntry(
                    signature="abc",
                    sha256="0" * 64,  # bogus hash
                    promoted_at="t",
                )
            },
        )
        ok, reason = verify_against_manifest(fixer, manifest)
        assert ok is False
        assert "hash mismatch" in reason

    def test_sha256_is_deterministic(self, tmp_path: Path) -> None:
        path = tmp_path / "f.py"
        path.write_text("hello\n", encoding="utf-8")
        first = sha256_of_file(path)
        # Re-read; should be identical.
        second = sha256_of_file(path)
        assert first == second
        # 64 hex chars (sha256 = 32 bytes).
        assert len(first) == 64


# ---------------------------------------------------------------------------
# AST validation
# ---------------------------------------------------------------------------


class TestASTValidateFixerSource:
    """The static-validator is the defense-in-depth gate after the manifest hash."""

    def test_valid_source_passes(self) -> None:
        source = textwrap.dedent(
            """
            def apply(signature, issue):
                return {"success": True, "files_modified": []}
            """
        )
        ok, reason = ast_validate_fixer_source(source)
        assert ok is True
        assert reason == "ok"

    def test_syntax_error_fails(self) -> None:
        ok, reason = ast_validate_fixer_source("def apply(:\n")
        assert ok is False
        assert "syntax error" in reason

    @pytest.mark.parametrize("module", sorted(BANNED_IMPORTS))
    def test_banned_top_level_import(self, module: str) -> None:
        # The validator matches the *top-level* name (e.g. "urllib" for
        # "urllib.parse"). Submodule suffixes don't get a separate
        # entry — the parent module is the gate.
        top_level = module.split(".")[0]
        ok, reason = ast_validate_fixer_source(f"import {module}\n")
        assert ok is False
        assert f"banned imports: {top_level}" in reason

    @pytest.mark.parametrize("name", sorted(BANNED_BUILTIN_CALLS))
    def test_banned_builtin_call_direct(self, name: str) -> None:
        ok, reason = ast_validate_fixer_source(f"x = {name}(None)\n")
        assert ok is False
        assert f"banned builtin calls: {name}" in reason

    def test_banned_builtin_call_attribute(self) -> None:
        """``os.__import__(...)`` is also caught (attribute-form)."""
        ok, reason = ast_validate_fixer_source(
            "import os\nx = os.__import__('sys')\n"
        )
        assert ok is False

    def test_banned_dunder_attr_via_attribute(self) -> None:
        ok, reason = ast_validate_fixer_source("x = object.__subclasses__()\n")
        assert ok is False
        assert "banned dunder attribute access" in reason

    def test_banned_dunder_via_getattr_string(self) -> None:
        ok, reason = ast_validate_fixer_source(
            "x = getattr(object, '__subclasses__')()\n"
        )
        assert ok is False
        assert "banned dunder attribute access" in reason

    @pytest.mark.parametrize("dunder", sorted(ALLOWED_DUNDER_ATTRS))
    def test_allowed_dunders_pass(self, dunder: str) -> None:
        """The 4 allowlisted dunder attributes are used legitimately in fixer code."""
        ok, reason = ast_validate_fixer_source(
            f"__all__ = ['apply']\nNAME = {dunder!r}\n"
        )
        # Some allowlisted dunders may be import-only (e.g. __file__);
        # the AST still parses, so we just assert no *banned* error.
        assert ok is True, f"dunder {dunder} was rejected: {reason}"

    def test_safe_imports_pass(self) -> None:
        """Common stdlib imports a fixer might legitimately need."""
        ok, reason = ast_validate_fixer_source(
            textwrap.dedent(
                """
                import ast
                import re
                from typing import Any
                def apply(signature, issue):
                    return {"success": True, "files_modified": []}
                """
            )
        )
        assert ok is True, f"expected ok, got: {reason}"

    def test_from_import_banned_module(self) -> None:
        ok, reason = ast_validate_fixer_source("from os import path\n")
        assert ok is False
        assert "banned imports: os" in reason

    def test_short_circuits_on_syntax_error(self) -> None:
        """A syntax error short-circuits — we don't try to AST-walk broken code."""
        ok, reason = ast_validate_fixer_source("def apply(:\nimport os\n")
        assert ok is False
        assert "syntax error" in reason
        assert "banned imports" not in reason

    def test_non_literal_getattr_arg_rejected(self) -> None:
        """A ``getattr`` whose second arg is a non-literal expression is rejected.

        Security review finding HIGH-1: a fixer that built the dunder
        name dynamically (``getattr(builtins, ''.join([...]))``) used to
        slip past the AST gate. The validator now flags any
        ``getattr``-family call whose second arg is not an
        ``ast.Constant``.
        """
        # The exact exploit from the security review.
        bypass = (
            "import builtins\n"
            "__import__ = getattr(\n"
            "    builtins,\n"
            "    ''.join(chr(c) for c in [95, 95] + [ord(c) for c in 'import'] + [95, 95])\n"
            ")\n"
            "def apply(signature, issue): return {}\n"
        )
        ok, reason = ast_validate_fixer_source(bypass)
        assert ok is False
        # The error mentions the non-literal arg, a banned import
        # (builtins is on the metaclass list), or a banned-dunder.
        assert (
            "non_literal_arg" in reason
            or "banned imports: builtins" in reason
            or "metaclass primitives: builtins" in reason
            or "banned dunder" in reason
        )

    def test_metaclass_primitives_banned(self) -> None:
        """``type``/``object``/``super``/``builtins`` are banned imports.

        Security review finding: banning only ``os``/``subprocess``/etc.
        is not enough; the standard jailbreak combo is
        ``type(obj).__mro__[-1].__subclasses__()`` and a fixer that
        imports ``type`` is halfway there.
        """
        from crackerjack.ai_fix.auto_fixers_manifest import (
            BANNED_METACLASS_PRIMITIVES,
        )

        for name in ("type", "object", "super", "builtins"):
            assert name in BANNED_METACLASS_PRIMITIVES
            ok, reason = ast_validate_fixer_source(f"import {name}\n")
            assert ok is False
            assert "metaclass primitives" in reason or "banned imports" in reason

    def test_computed_callable_rejected(self) -> None:
        """A ``Call`` whose ``func`` is computed (not a literal Name) is rejected.

        Security review finding: a fixer that used
        ``globals()['__import__']('os')`` would slip past the
        ``func.id`` check because ``func`` is a Call, not a Name.
        The validator now flags computed callables.
        """
        bypass = (
            "x = globals()['__import__']('os')\n"
            "def apply(signature, issue): return {}\n"
        )
        ok, reason = ast_validate_fixer_source(bypass)
        assert ok is False
        # Either the computed-callable guard or the banned builtins
        # guard must catch this.
        assert "computed_callable" in reason or "banned builtin" in reason
