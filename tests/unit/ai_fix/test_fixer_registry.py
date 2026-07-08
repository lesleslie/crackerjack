"""Tests for the :class:`FixerRegistry` — built-in + auto-promoted fixer lookup.

PR 5 of the 2026-07-07 ai-fix design introduces :class:`FixerRegistry`, which
replaces ``FixerCoordinator.fixers: dict[str, Agent]``. Two namespaces coexist:

- **built-in fixers** keyed by issue type (``"TYPE_ERROR"``, ``"COMPLEXITY"`` …)
- **auto-promoted fixers** keyed by a signature string (PR 8 supplies the
  actual loader via :meth:`FixerRegistry.from_disk`; this PR ships a stub that
  returns an empty registry).

These tests pin the public contract so PR 6 (FixRouter) can rely on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.ai_fix.fixer_registry import Fixer, FixerRegistry

# ---------------------------------------------------------------------------
# Test doubles — every fixer is duck-typed (no inheritance), so a bare
# class with the right method is enough.
# ---------------------------------------------------------------------------


class _FakeFixer:
    """Minimal Fixer — exposes ``analyze_and_fix`` like the existing agents."""

    def __init__(self, name: str = "Fake") -> None:
        self.name = name
        self.invocations: int = 0

    async def analyze_and_fix(self, issue):  # type: ignore[no-untyped-def]
        self.invocations += 1
        return None


class _PlanFixer:
    """Alternative interface — exposes ``execute_fix_plan`` instead."""

    async def execute_fix_plan(self, plan):  # type: ignore[no-untyped-def]
        return None


class _ProtocolOnly:
    """Bare object with the structural ``execute(plan)`` method."""

    async def execute(self, plan):  # type: ignore[no-untyped-def]
        return None


# ---------------------------------------------------------------------------
# Built-in registration
# ---------------------------------------------------------------------------


class TestRegisterBuiltin:
    def test_register_builtin_stores_fixer(self) -> None:
        registry = FixerRegistry()
        fixer = _FakeFixer()

        registry.register_builtin("TYPE_ERROR", fixer)

        assert registry.get("TYPE_ERROR") is fixer

    def test_register_builtin_overrides_previous(self) -> None:
        """Last write wins — the second registration replaces the first."""
        registry = FixerRegistry()
        first = _FakeFixer(name="first")
        second = _FakeFixer(name="second")

        registry.register_builtin("COMPLEXITY", first)
        registry.register_builtin("COMPLEXITY", second)

        assert registry.get("COMPLEXITY") is second

    def test_register_multiple_distinct_types(self) -> None:
        registry = FixerRegistry()
        type_fixer = _FakeFixer()
        complexity_fixer = _FakeFixer()

        registry.register_builtin("TYPE_ERROR", type_fixer)
        registry.register_builtin("COMPLEXITY", complexity_fixer)

        assert registry.get("TYPE_ERROR") is type_fixer
        assert registry.get("COMPLEXITY") is complexity_fixer

    def test_register_builtin_accepts_protocol_only_fixer(self) -> None:
        """A bare object with ``execute(plan)`` is a valid Fixer."""
        registry = FixerRegistry()
        fixer = _ProtocolOnly()

        registry.register_builtin("REFURB", fixer)

        assert registry.get("REFURB") is fixer

    def test_register_builtin_accepts_plan_fixer(self) -> None:
        """An object with ``execute_fix_plan`` is also a valid Fixer."""
        registry = FixerRegistry()
        fixer = _PlanFixer()

        registry.register_builtin("REFURB", fixer)

        assert registry.get("REFURB") is fixer

    def test_register_builtin_returns_none(self) -> None:
        """Returns nothing — registration is via mutation, not chaining."""
        registry = FixerRegistry()

        result = registry.register_builtin("TYPE_ERROR", _FakeFixer())

        assert result is None

    def test_register_builtin_is_case_sensitive(self) -> None:
        """Keys are matched exactly — case differences are distinct entries."""
        registry = FixerRegistry()
        upper = _FakeFixer()
        lower = _FakeFixer()

        registry.register_builtin("TYPE_ERROR", upper)
        registry.register_builtin("type_error", lower)

        assert registry.get("TYPE_ERROR") is upper
        assert registry.get("type_error") is lower


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class TestGet:
    def test_get_missing_returns_none(self) -> None:
        registry = FixerRegistry()

        assert registry.get("UNREGISTERED") is None

    def test_get_empty_registry_returns_none(self) -> None:
        registry = FixerRegistry()

        assert registry.get("TYPE_ERROR") is None

    def test_get_does_not_match_auto_promoted_signatures(self) -> None:
        """``get(issue_type)`` only sees built-ins, not auto-promoted."""
        registry = FixerRegistry()
        promoted = _FakeFixer()

        registry.register_auto_promoted("refurb:FURB136", promoted)

        assert registry.get("refurb:FURB136") is None


class TestHasMechanicalFixer:
    def test_true_when_builtin_registered(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())

        assert registry.has_mechanical_fixer("TYPE_ERROR") is True

    def test_false_when_missing(self) -> None:
        registry = FixerRegistry()

        assert registry.has_mechanical_fixer("UNREGISTERED") is False

    def test_false_for_auto_promoted_signature(self) -> None:
        """``has_mechanical_fixer`` only inspects the built-in namespace."""
        registry = FixerRegistry()
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())

        assert registry.has_mechanical_fixer("refurb:FURB136") is False

    def test_false_on_empty_registry(self) -> None:
        registry = FixerRegistry()

        assert registry.has_mechanical_fixer("TYPE_ERROR") is False

    def test_true_for_distinct_types_independently(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())

        assert registry.has_mechanical_fixer("TYPE_ERROR") is True
        assert registry.has_mechanical_fixer("COMPLEXITY") is False


# ---------------------------------------------------------------------------
# Auto-promoted registration
# ---------------------------------------------------------------------------


class TestRegisterAutoPromoted:
    def test_register_auto_promoted_stores_fixer(self) -> None:
        registry = FixerRegistry()
        fixer = _FakeFixer()

        registry.register_auto_promoted("refurb:FURB136", fixer)

        assert registry.get_signature("refurb:FURB136") is fixer

    def test_register_auto_promoted_does_not_register_as_builtin(self) -> None:
        """Auto-promoted fixers are kept in a separate namespace from built-ins."""
        registry = FixerRegistry()
        fixer = _FakeFixer()

        registry.register_auto_promoted("refurb:FURB136", fixer)

        assert registry.has_mechanical_fixer("refurb:FURB136") is False
        assert registry.get("refurb:FURB136") is None

    def test_register_auto_promoted_accepts_protocol_only_fixer(self) -> None:
        registry = FixerRegistry()
        fixer = _ProtocolOnly()

        registry.register_auto_promoted("refurb:FURB136", fixer)

        assert registry.get_signature("refurb:FURB136") is fixer

    def test_register_auto_promoted_overrides_previous(self) -> None:
        """Last write wins — useful when reloading from disk."""
        registry = FixerRegistry()
        first = _FakeFixer()
        second = _FakeFixer()

        registry.register_auto_promoted("refurb:FURB136", first)
        registry.register_auto_promoted("refurb:FURB136", second)

        assert registry.get_signature("refurb:FURB136") is second

    def test_register_auto_promoted_distinct_signatures(self) -> None:
        registry = FixerRegistry()
        a = _FakeFixer()
        b = _FakeFixer()

        registry.register_auto_promoted("refurb:FURB136", a)
        registry.register_auto_promoted("refurb:FURB188", b)

        assert registry.get_signature("refurb:FURB136") is a
        assert registry.get_signature("refurb:FURB188") is b


# ---------------------------------------------------------------------------
# list_signatures
# ---------------------------------------------------------------------------


class TestListSignatures:
    def test_empty_registry_returns_empty_list(self) -> None:
        registry = FixerRegistry()

        assert registry.list_signatures() == []

    def test_returns_all_registered_signatures(self) -> None:
        registry = FixerRegistry()
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())
        registry.register_auto_promoted("refurb:FURB188", _FakeFixer())
        registry.register_auto_promoted("ty:invalid-assignment", _FakeFixer())

        signatures = registry.list_signatures()

        assert sorted(signatures) == sorted(
            ["refurb:FURB136", "refurb:FURB188", "ty:invalid-assignment"]
        )

    def test_signatures_independent_of_built_ins(self) -> None:
        """Built-in registrations should not appear in ``list_signatures()``."""
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())

        signatures = registry.list_signatures()

        assert "TYPE_ERROR" not in signatures
        assert signatures == ["refurb:FURB136"]


# ---------------------------------------------------------------------------
# from_disk (PR 5 ships a stub — PR 8 fills in the real loader)
# ---------------------------------------------------------------------------


class TestFromDiskRealLoader:
    """The from_disk loader shipped in PR 8: walks auto_fixers/*.py, imports each.

    The PR 5 stub (``test_from_disk_returns_empty_registry``) was
    intentionally weak so PR 6/7 could compile against the API. PR
    8 makes the loader real; these tests pin the contract the
    PromotionPipeline depends on.
    """

    def test_from_disk_loads_present_fixer(self, tmp_path: Path) -> None:
        from crackerjack.ai_fix.auto_fixers_manifest import (
            Manifest,
            ManifestEntry,
            sha256_of_file,
            write_manifest,
        )
        import datetime

        auto_fixers_dir = tmp_path / "auto_fixers"
        auto_fixers_dir.mkdir()
        fixer_path = auto_fixers_dir / "refurb_FURB136.py"
        fixer_path.write_text("x = 1\n", encoding="utf-8")
        # PR 8's security model: the file must be in the manifest.
        manifest = Manifest(
            version=1,
            fixers={
                "refurb_FURB136": ManifestEntry(
                    signature="refurb_FURB136",
                    sha256=sha256_of_file(fixer_path),
                    promoted_at=datetime.datetime.now(datetime.UTC).isoformat(),
                )
            },
        )
        write_manifest(manifest, auto_fixers_dir / "manifest.json")

        registry = FixerRegistry.from_disk(auto_fixers_dir)

        # PR 8's real loader: the file becomes a registered auto-promoted
        # fixer under its filename stem.
        assert "refurb_FURB136" in registry.list_signatures()
        assert registry.has_mechanical_fixer("ANY_TYPE") is False  # still no built-ins

    def test_from_disk_refuses_file_without_manifest(self, tmp_path: Path) -> None:
        """A file in auto_fixers/ but NOT in the manifest is refused.

        This is the trust-boundary contract: a file the GhPRCreator
        didn't write can't be executed by the loader.
        """
        auto_fixers_dir = tmp_path / "auto_fixers"
        auto_fixers_dir.mkdir()
        # File present, no manifest.
        (auto_fixers_dir / "untrusted.py").write_text("x = 1\n")

        registry = FixerRegistry.from_disk(auto_fixers_dir)
        assert "untrusted" not in registry.list_signatures()

    def test_from_disk_with_missing_directory(self, tmp_path: Path) -> None:
        """Even when the directory does not exist, the loader returns an empty
        registry rather than raising — callers don't have to check first.
        """
        missing = tmp_path / "does_not_exist"

        registry = FixerRegistry.from_disk(missing)

        assert registry.list_signatures() == []

    def test_from_disk_built_ins_independent(self, tmp_path: Path) -> None:
        """A registry built from disk is still a usable FixerRegistry —
        built-ins can be registered after construction.
        """
        registry = FixerRegistry.from_disk(tmp_path)
        registry.register_builtin("TYPE_ERROR", _FakeFixer())

        assert registry.has_mechanical_fixer("TYPE_ERROR") is True
        assert registry.list_signatures() == []


# ---------------------------------------------------------------------------
# Integration with existing FixerCoordinator-style usage
# ---------------------------------------------------------------------------


class TestCoordinatorSubstitution:
    """The design replaces ``FixerCoordinator.fixers: dict[str, Agent]`` with a
    :class:`FixerRegistry`. These tests verify the registry is a drop-in
    for the ``dict[issue_type, fixer]`` access pattern the coordinator relies on.
    """

    def test_iterates_built_in_fixers(self) -> None:
        registry = FixerRegistry()
        type_fixer = _FakeFixer()
        complexity_fixer = _FakeFixer()
        security_fixer = _FakeFixer()

        registry.register_builtin("TYPE_ERROR", type_fixer)
        registry.register_builtin("COMPLEXITY", complexity_fixer)
        registry.register_builtin("SECURITY", security_fixer)

        # Mimic FixerCoordinator's "for issue_type, fixer in self.fixers.items()"
        collected: dict[str, object] = dict(registry.iter_builtins())

        assert collected == {
            "TYPE_ERROR": type_fixer,
            "COMPLEXITY": complexity_fixer,
            "SECURITY": security_fixer,
        }

    def test_iter_builtins_does_not_include_auto_promoted(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())

        keys = [key for key, _ in registry.iter_builtins()]

        assert keys == ["TYPE_ERROR"]

    def test_registry_does_not_break_with_duplicate_register(self) -> None:
        """Registering the same issue_type twice must not raise — it overrides."""
        registry = FixerRegistry()
        fixer = _FakeFixer()

        registry.register_builtin("TYPE_ERROR", fixer)
        registry.register_builtin("TYPE_ERROR", fixer)

        assert registry.get("TYPE_ERROR") is fixer


class TestDictLikeShim:
    """The registry must be a drop-in for the old
    ``FixerCoordinator.fixers: dict[str, Agent]`` field so that PR 5 can
    swap the field type without breaking any of the existing call sites
    (``coordinator.fixers["TYPE_ERROR"]``,
    ``coordinator.fixers.get(issue_type)``,
    ``for k, v in coordinator.fixers.items()``,
    ``len(coordinator.fixers)``).
    """

    def test_subscript_returns_fixer(self) -> None:
        registry = FixerRegistry()
        fixer = _FakeFixer()
        registry.register_builtin("TYPE_ERROR", fixer)

        assert registry["TYPE_ERROR"] is fixer

    def test_subscript_missing_raises_key_error(self) -> None:
        registry = FixerRegistry()

        with pytest.raises(KeyError):
            registry["UNREGISTERED"]

    def test_subscript_assignment_registers_builtin(self) -> None:
        """``registry[issue_type] = fixer`` mirrors dict assignment and
        registers a built-in — used by ``_try_register_fixer``.
        """
        registry = FixerRegistry()
        fixer = _FakeFixer()

        registry["COMPLEXITY"] = fixer

        assert registry.has_mechanical_fixer("COMPLEXITY") is True
        assert registry.get("COMPLEXITY") is fixer

    def test_len_returns_builtin_count(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())
        registry.register_builtin("COMPLEXITY", _FakeFixer())

        assert len(registry) == 2

    def test_len_unaffected_by_auto_promoted(self) -> None:
        """``len(registry)`` is the built-in count, matching dict semantics."""
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())

        assert len(registry) == 1

    def test_contains_returns_true_for_builtin(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())

        assert "TYPE_ERROR" in registry

    def test_contains_returns_false_for_auto_promoted(self) -> None:
        """The dict-like ``in`` operator only inspects built-ins, matching
        the lookup semantics of ``get`` and ``has_mechanical_fixer``.
        """
        registry = FixerRegistry()
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())

        assert "refurb:FURB136" not in registry

    def test_iter_yields_builtin_keys(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _FakeFixer())
        registry.register_builtin("COMPLEXITY", _FakeFixer())

        assert sorted(iter(registry)) == ["COMPLEXITY", "TYPE_ERROR"]

    def test_keys_values_items_match_builtins(self) -> None:
        registry = FixerRegistry()
        type_fixer = _FakeFixer()
        complexity_fixer = _FakeFixer()
        registry.register_builtin("TYPE_ERROR", type_fixer)
        registry.register_builtin("COMPLEXITY", complexity_fixer)
        registry.register_auto_promoted("refurb:FURB136", _FakeFixer())

        assert sorted(registry.keys()) == ["COMPLEXITY", "TYPE_ERROR"]
        assert set(registry.values()) == {type_fixer, complexity_fixer}
        assert dict(registry.items()) == {
            "TYPE_ERROR": type_fixer,
            "COMPLEXITY": complexity_fixer,
        }


class TestFixerProtocol:
    """The :class:`Fixer` alias must be a valid static-typing anchor that
    accepts the existing agent shapes (analyze_and_fix / execute_fix_plan /
    execute). PR 6 will use it to type FixRouter parameters.
    """

    def test_fixer_alias_accepts_analyze_and_fix_agent(self) -> None:
        fixer: Fixer = _FakeFixer()

        assert fixer is not None

    def test_fixer_alias_accepts_execute_fix_plan_agent(self) -> None:
        fixer: Fixer = _PlanFixer()

        assert fixer is not None

    def test_fixer_alias_accepts_protocol_only(self) -> None:
        fixer: Fixer = _ProtocolOnly()

        assert fixer is not None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
