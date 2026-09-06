"""Comprehensive unit tests for ``crackerjack.config.hooks``.

Coverage targets:
- ``HookStage``, ``RetryPolicy``, ``SecurityLevel`` enums
- ``HookDefinition`` defaults and ``get_command`` / ``build_command`` paths
- ``HookStrategy`` defaults
- ``FAST_HOOKS`` / ``COMPREHENSIVE_HOOKS`` invariants
- ``_build_opt_in_type_hooks`` (every settings branch)
- ``_build_comprehensive_hooks`` filtering
- ``_update_hook_timeouts_from_settings``
- ``HookConfigLoader.load_strategy`` (fast / comprehensive / unknown)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.config import hooks as hooks_module
from crackerjack.config.hooks import (
    COMPREHENSIVE_HOOKS,
    COMPREHENSIVE_STRATEGY,
    FAST_HOOKS,
    FAST_STRATEGY,
    HookConfigLoader,
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
    SecurityLevel,
    _build_comprehensive_hooks,
    _build_opt_in_type_hooks,
    _update_hook_timeouts_from_settings,
)


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnums:
    def test_hook_stage_values(self) -> None:
        assert HookStage.FAST.value == "fast"
        assert HookStage.COMPREHENSIVE.value == "comprehensive"
        assert set(HookStage) == {HookStage.FAST, HookStage.COMPREHENSIVE}

    def test_retry_policy_values(self) -> None:
        assert RetryPolicy.NONE.value == "none"
        assert RetryPolicy.FORMATTING_ONLY.value == "formatting_only"
        assert RetryPolicy.ALL_HOOKS.value == "all_hooks"

    def test_security_level_values(self) -> None:
        assert SecurityLevel.CRITICAL.value == "critical"
        assert SecurityLevel.HIGH.value == "high"
        assert SecurityLevel.MEDIUM.value == "medium"
        assert SecurityLevel.LOW.value == "low"


# ---------------------------------------------------------------------------
# HookDefinition defaults / dataclass behaviour
# ---------------------------------------------------------------------------


class TestHookDefinitionDefaults:
    def test_minimal_construction_uses_defaults(self) -> None:
        hook = HookDefinition(name="custom-tool")
        assert hook.name == "custom-tool"
        assert hook.command == []
        assert hook.timeout == 60
        assert hook.stage is HookStage.FAST
        assert hook.description is None
        assert hook.retry_on_failure is False
        assert hook.is_formatting is False
        assert hook.auto_run is True
        assert hook.config_path is None
        assert hook.security_level is SecurityLevel.MEDIUM
        assert hook.accepts_file_paths is False
        assert hook.disabled is False
        assert hook.run_schedule is None
        assert hook.allow_unsafe_fixes is False
        assert hook._direct_cmd_cache is None

    def test_explicit_field_override(self) -> None:
        hook = HookDefinition(
            name="custom-tool",
            command=["custom", "run"],
            timeout=300,
            stage=HookStage.COMPREHENSIVE,
            description="custom description",
            retry_on_failure=True,
            is_formatting=True,
            auto_run=False,
            config_path=Path("/tmp/x"),
            security_level=SecurityLevel.CRITICAL,
            accepts_file_paths=True,
            disabled=True,
            run_schedule="daily",
            allow_unsafe_fixes=True,
        )
        assert hook.command == ["custom", "run"]
        assert hook.timeout == 300
        assert hook.stage is HookStage.COMPREHENSIVE
        assert hook.description == "custom description"
        assert hook.retry_on_failure is True
        assert hook.is_formatting is True
        assert hook.auto_run is False
        assert hook.config_path == Path("/tmp/x")
        assert hook.security_level is SecurityLevel.CRITICAL
        assert hook.accepts_file_paths is True
        assert hook.disabled is True
        assert hook.run_schedule == "daily"
        assert hook.allow_unsafe_fixes is True

    def test_direct_cmd_cache_is_excluded_from_repr(self) -> None:
        # Cache field is private and excluded from repr to avoid stale dumps.
        hook = HookDefinition(name="custom-tool")
        assert "_direct_cmd_cache" not in repr(hook)


# ---------------------------------------------------------------------------
# HookDefinition.get_command / build_command paths
# ---------------------------------------------------------------------------


class TestHookDefinitionGetCommand:
    def test_returns_explicit_command_without_lookup(self) -> None:
        hook = HookDefinition(
            name="ruff-check",
            command=["echo", "hello"],
        )
        with patch.object(
            hooks_module, "get_tool_command", wraps=hooks_module.get_tool_command
        ) as spy:
            assert hook.get_command() == ["echo", "hello"]
        # Explicit command path: no call into tool_commands.get_tool_command.
        assert not spy.called

    def test_resolves_via_tool_commands_when_command_empty(self) -> None:
        hook = HookDefinition(name="ruff-check", command=[])
        cmd = hook.get_command()
        # tool_commands resolves to a real shell entry; just assert it's a list
        # whose first element is executable and contains "ruff".
        assert isinstance(cmd, list)
        assert cmd, "expected non-empty resolved command"
        assert any("ruff" in part for part in cmd)

    def test_caches_resolved_command(self) -> None:
        hook = HookDefinition(name="ruff-check", command=[])
        first = hook.get_command()
        second = hook.get_command()
        assert first is second  # identical list reference from cache
        assert hook._direct_cmd_cache is not None

    def test_unknown_hook_raises_value_error(self) -> None:
        hook = HookDefinition(name="this-hook-does-not-exist-xyz123", command=[])
        with pytest.raises(ValueError, match="not registered for direct execution"):
            hook.get_command()

    def test_keyerror_translated_to_value_error(self) -> None:
        hook = HookDefinition(name="badname", command=[])

        def fake_get_tool_command(name: str, **_: object) -> list[str]:
            raise KeyError(name)

        with patch.object(hooks_module, "get_tool_command", side_effect=fake_get_tool_command):
            with pytest.raises(ValueError) as exc:
                hook.get_command()
        assert "badname" in str(exc.value)
        # Original KeyError chained as __cause__
        assert isinstance(exc.value.__cause__, KeyError)


class TestHookDefinitionBuildCommand:
    def test_build_command_with_no_files_appends_crackerjack_dir(self) -> None:
        hook = HookDefinition(name="ruff-check", command=["ruff", "check"])
        cmd = hook.build_command()
        assert cmd == ["ruff", "check", "crackerjack/"]

    def test_build_command_with_files_and_accept_flag(self) -> None:
        hook = HookDefinition(
            name="ruff-check",
            command=["ruff", "check"],
            accepts_file_paths=True,
        )
        cmd = hook.build_command(files=[Path("a.py"), Path("b.py")])
        assert cmd == ["ruff", "check", "a.py", "b.py"]

    def test_build_command_with_files_but_no_accept_flag_uses_crackerjack_dir(
        self,
    ) -> None:
        # Without ``accepts_file_paths=True``, files are ignored and the
        # default ``crackerjack/`` directory is appended.
        hook = HookDefinition(
            name="ruff-check",
            command=["ruff", "check"],
            accepts_file_paths=False,
        )
        cmd = hook.build_command(files=[Path("a.py")])
        assert cmd == ["ruff", "check", "crackerjack/"]

    def test_build_command_with_empty_files_list_appends_crackerjack_dir(self) -> None:
        hook = HookDefinition(name="ruff-check", command=["ruff", "check"])
        cmd = hook.build_command(files=[])
        assert cmd == ["ruff", "check", "crackerjack/"]

    def test_build_command_with_none_files_appends_crackerjack_dir(self) -> None:
        hook = HookDefinition(name="ruff-check", command=["ruff", "check"])
        cmd = hook.build_command(files=None)
        assert cmd == ["ruff", "check", "crackerjack/"]


# ---------------------------------------------------------------------------
# HookStrategy defaults
# ---------------------------------------------------------------------------


class TestHookStrategy:
    def test_defaults(self) -> None:
        strategy = HookStrategy(name="custom", hooks=[])
        assert strategy.name == "custom"
        assert strategy.hooks == []
        assert strategy.timeout == 300
        assert strategy.retry_policy is RetryPolicy.NONE
        assert strategy.parallel is False
        assert strategy.max_workers == 3

    def test_overrides(self) -> None:
        strategy = HookStrategy(
            name="custom",
            hooks=[],
            timeout=600,
            retry_policy=RetryPolicy.ALL_HOOKS,
            parallel=True,
            max_workers=8,
        )
        assert strategy.timeout == 600
        assert strategy.retry_policy is RetryPolicy.ALL_HOOKS
        assert strategy.parallel is True
        assert strategy.max_workers == 8


# ---------------------------------------------------------------------------
# Module-level hook lists
# ---------------------------------------------------------------------------


class TestFastHookInvariants:
    def test_fast_hooks_is_non_empty(self) -> None:
        assert len(FAST_HOOKS) > 0

    def test_fast_hook_names_unique(self) -> None:
        names = [h.name for h in FAST_HOOKS]
        assert len(names) == len(set(names)), f"duplicate hook names: {names}"

    def test_fast_hooks_have_positive_timeout(self) -> None:
        for hook in FAST_HOOKS:
            assert hook.timeout > 0, hook.name

    def test_fast_strategy_uses_fast_hooks(self) -> None:
        assert FAST_STRATEGY.name == "fast"
        assert FAST_STRATEGY.hooks is FAST_HOOKS
        assert FAST_STRATEGY.timeout == 300
        assert FAST_STRATEGY.parallel is True
        assert FAST_STRATEGY.max_workers == 6
        assert FAST_STRATEGY.retry_policy is RetryPolicy.NONE

    def test_fast_hooks_have_explicit_command_empty(self) -> None:
        # Empty command list triggers runtime resolution via get_tool_command.
        for hook in FAST_HOOKS:
            assert hook.command == [], hook.name

    def test_fast_hooks_default_to_fast_stage(self) -> None:
        # Convention check: builtin entries in FAST_HOOKS use HookStage.FAST
        # (the field is documentary for builtins).
        for hook in FAST_HOOKS:
            assert hook.stage is HookStage.FAST, hook.name


class TestComprehensiveHookInvariants:
    def test_comprehensive_hooks_is_non_empty(self) -> None:
        assert len(COMPREHENSIVE_HOOKS) > 0

    def test_comprehensive_hook_names_unique(self) -> None:
        names = [h.name for h in COMPREHENSIVE_HOOKS]
        assert len(names) == len(set(names)), f"duplicate hook names: {names}"

    def test_comprehensive_hooks_have_positive_timeout(self) -> None:
        for hook in COMPREHENSIVE_HOOKS:
            assert hook.timeout > 0, hook.name

    def test_comprehensive_strategy_filters_disabled_and_inactive(self) -> None:
        # COMPREHENSIVE_STRATEGY.hooks reflects the static filter applied at
        # module load (auto_run=True and not disabled).
        names = {h.name for h in COMPREHENSIVE_STRATEGY.hooks}
        # gitleaks / skylos / complexipy are explicitly disabled in the
        # COMPREHENSIVE_HOOKS list — they should NOT be in the active strategy.
        assert "gitleaks" not in names
        assert "skylos" not in names
        assert "complexipy" not in names
        # semgrep is enabled and should appear.
        assert "semgrep" in names

    def test_comprehensive_strategy_metadata(self) -> None:
        assert COMPREHENSIVE_STRATEGY.name == "comprehensive"
        assert COMPREHENSIVE_STRATEGY.timeout == 1800
        assert COMPREHENSIVE_STRATEGY.parallel is True
        assert COMPREHENSIVE_STRATEGY.max_workers == 6
        assert COMPREHENSIVE_STRATEGY.retry_policy is RetryPolicy.NONE

    def test_comprehensive_strategy_excludes_ty_and_zuban(self) -> None:
        # ty and zuban are opt-in via _build_opt_in_type_hooks(), so they
        # should not appear in COMPREHENSIVE_STRATEGY (which is built from
        # COMPREHENSIVE_HOOKS only).
        names = {h.name for h in COMPREHENSIVE_STRATEGY.hooks}
        assert "ty" not in names
        assert "zuban" not in names
        assert "pyrefly" not in names


# ---------------------------------------------------------------------------
# _build_opt_in_type_hooks — every settings branch
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_load_settings():
    """Allow tests to inject a custom HookSettings into the loader."""
    import crackerjack.config as cfg_pkg
    from crackerjack.config import CrackerjackSettings
    from crackerjack.config.settings import HookSettings

    real_load = cfg_pkg.load_settings
    state = {"settings": real_load(CrackerjackSettings)}

    def fake_load(cls):  # noqa: ARG001
        return state["settings"]

    cfg_pkg.load_settings = fake_load
    try:
        yield state
    finally:
        cfg_pkg.load_settings = real_load


class TestBuildOptInTypeHooks:
    def test_returns_empty_when_no_flags_enabled(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={
                "hooks": HookSettings(
                    enable_pyrefly=False,
                    enable_ty=False,
                    enable_zuban=False,
                    enable_ty_ignore_syntax=False,
                )
            }
        )
        hooks = _build_opt_in_type_hooks()
        assert hooks == []

    def test_pyrefly_branch(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_pyrefly=True)}
        )
        hooks = _build_opt_in_type_hooks()
        names = [h.name for h in hooks]
        assert "pyrefly" in names
        pyrefly = next(h for h in hooks if h.name == "pyrefly")
        assert pyrefly.timeout == 120  # default pyrefly_timeout
        assert pyrefly.stage is HookStage.COMPREHENSIVE
        assert pyrefly.auto_run is True
        assert pyrefly.accepts_file_paths is True
        assert pyrefly.security_level is SecurityLevel.HIGH

    def test_pyrefly_branch_uses_configured_timeout(self, patched_load_settings) -> None:
        from crackerjack.config.settings import AdapterTimeouts, HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={
                "hooks": HookSettings(enable_pyrefly=True),
                "adapter_timeouts": AdapterTimeouts(pyrefly_timeout=999),
            }
        )
        hooks = _build_opt_in_type_hooks()
        pyrefly = next(h for h in hooks if h.name == "pyrefly")
        assert pyrefly.timeout == 999

    def test_zuban_branch(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_zuban=True)}
        )
        hooks = _build_opt_in_type_hooks()
        names = [h.name for h in hooks]
        assert "zuban" in names
        zuban = next(h for h in hooks if h.name == "zuban")
        assert zuban.timeout == 60  # default zuban_timeout
        assert zuban.stage is HookStage.COMPREHENSIVE
        assert zuban.auto_run is True
        assert zuban.accepts_file_paths is True
        assert zuban.security_level is SecurityLevel.HIGH

    def test_zuban_branch_uses_configured_timeout(self, patched_load_settings) -> None:
        from crackerjack.config.settings import AdapterTimeouts, HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={
                "hooks": HookSettings(enable_zuban=True),
                "adapter_timeouts": AdapterTimeouts(zuban_timeout=42),
            }
        )
        hooks = _build_opt_in_type_hooks()
        zuban = next(h for h in hooks if h.name == "zuban")
        assert zuban.timeout == 42

    def test_ty_branch(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_ty=True)}
        )
        hooks = _build_opt_in_type_hooks()
        names = [h.name for h in hooks]
        assert "ty" in names
        ty_hook = next(h for h in hooks if h.name == "ty")
        assert ty_hook.timeout == 120  # default ty_timeout
        assert ty_hook.stage is HookStage.COMPREHENSIVE
        assert ty_hook.auto_run is True
        assert ty_hook.accepts_file_paths is True
        assert ty_hook.security_level is SecurityLevel.HIGH

    def test_ty_branch_uses_configured_timeout(self, patched_load_settings) -> None:
        from crackerjack.config.settings import AdapterTimeouts, HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={
                "hooks": HookSettings(enable_ty=True),
                "adapter_timeouts": AdapterTimeouts(ty_timeout=321),
            }
        )
        hooks = _build_opt_in_type_hooks()
        ty_hook = next(h for h in hooks if h.name == "ty")
        assert ty_hook.timeout == 321

    def test_ty_ignore_syntax_branch(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_ty_ignore_syntax=True)}
        )
        hooks = _build_opt_in_type_hooks()
        names = [h.name for h in hooks]
        assert "ty-ignore-syntax" in names
        tis = next(h for h in hooks if h.name == "ty-ignore-syntax")
        # ty-ignore-syntax uses a hard-coded 60s timeout.
        assert tis.timeout == 60
        assert tis.stage is HookStage.COMPREHENSIVE
        assert tis.auto_run is True
        assert tis.accepts_file_paths is False
        assert tis.security_level is SecurityLevel.MEDIUM

    def test_all_flags_enabled(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={
                "hooks": HookSettings(
                    enable_pyrefly=True,
                    enable_ty=True,
                    enable_zuban=True,
                    enable_ty_ignore_syntax=True,
                )
            }
        )
        hooks = _build_opt_in_type_hooks()
        names = {h.name for h in hooks}
        assert {"pyrefly", "ty", "zuban", "ty-ignore-syntax"} <= names
        assert len(hooks) == 4

    def test_suppress_swallows_load_failure(self) -> None:
        # ``with suppress(Exception)`` around the load_settings call — if the
        # loader raises, the function returns an empty list.
        import crackerjack.config as cfg_pkg

        def boom(cls):  # noqa: ARG001
            raise RuntimeError("settings unavailable")

        with patch.object(cfg_pkg, "load_settings", side_effect=boom):
            hooks = _build_opt_in_type_hooks()
        assert hooks == []

    def test_returns_list_type_always(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_ty=True)}
        )
        result = _build_opt_in_type_hooks()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _build_comprehensive_hooks
# ---------------------------------------------------------------------------


class TestBuildComprehensiveHooks:
    def test_includes_active_comprehensive_hooks(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_ty=True)}
        )
        hooks = _build_comprehensive_hooks()
        names = {h.name for h in hooks}
        # semgrep / pyscn / check-jsonschema are auto-run, not disabled.
        assert "semgrep" in names
        assert "pyscn" in names
        assert "check-jsonschema" in names
        # disabled entries stay out.
        assert "gitleaks" not in names
        assert "skylos" not in names
        assert "complexipy" not in names
        # Opt-in ty shows up because settings enable it.
        assert "ty" in names

    def test_excludes_auto_run_false(self, patched_load_settings) -> None:
        from crackerjack.config.settings import HookSettings

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={"hooks": HookSettings(enable_ty=False)}
        )
        hooks = _build_comprehensive_hooks()
        # ``ty`` is auto_run=False in COMPREHENSIVE_HOOKS and the opt-in
        # factory produces nothing when the flag is off, so ``ty`` must not
        # be in the result.
        names = {h.name for h in hooks}
        assert "ty" not in names

    def test_excludes_disabled_hooks(self) -> None:
        # Even with no opt-ins enabled, the factory still filters out
        # disabled entries (gitleaks / skylos / complexipy).
        hooks = _build_comprehensive_hooks()
        names = {h.name for h in hooks}
        assert "gitleaks" not in names
        assert "skylos" not in names
        assert "complexipy" not in names


# ---------------------------------------------------------------------------
# _update_hook_timeouts_from_settings
# ---------------------------------------------------------------------------


class TestUpdateHookTimeoutsFromSettings:
    def test_mutates_known_hook_timeouts(self, patched_load_settings) -> None:
        from crackerjack.config.settings import AdapterTimeouts

        patched_load_settings["settings"] = patched_load_settings["settings"].model_copy(
            update={
                "adapter_timeouts": AdapterTimeouts(
                    semgrep_timeout=111,
                    creosote_timeout=222,
                )
            }
        )
        target = [
            HookDefinition(name="semgrep", command=[], timeout=60),
            HookDefinition(name="creosote", command=[], timeout=60),
            HookDefinition(name="unrelated-tool", command=[], timeout=60),
        ]
        _update_hook_timeouts_from_settings(target)
        assert target[0].timeout == 111
        assert target[1].timeout == 222
        # Hooks without a matching adapter_timeouts attribute stay put.
        assert target[2].timeout == 60

    def test_swallows_load_failure_without_mutating(self) -> None:
        import crackerjack.config as cfg_pkg

        target = [
            HookDefinition(name="ruff-check", command=[], timeout=42),
        ]

        def boom(cls):  # noqa: ARG001
            raise RuntimeError("settings unavailable")

        with patch.object(cfg_pkg, "load_settings", side_effect=boom):
            _update_hook_timeouts_from_settings(target)
        # Timeout unchanged because the loader raised and the suppress caught.
        assert target[0].timeout == 42

    def test_empty_list_is_a_noop(self, patched_load_settings) -> None:
        # No exception, no mutation needed.
        _update_hook_timeouts_from_settings([])


# ---------------------------------------------------------------------------
# HookConfigLoader.load_strategy
# ---------------------------------------------------------------------------


class TestHookConfigLoaderLoadStrategy:
    def test_fast_strategy(self) -> None:
        strategy = HookConfigLoader.load_strategy("fast")
        assert isinstance(strategy, HookStrategy)
        assert strategy.name == "fast"
        assert strategy.hooks is FAST_HOOKS
        assert strategy.timeout == 300
        assert strategy.parallel is True
        assert strategy.max_workers == 6

    def test_comprehensive_strategy_applies_settings_timeouts(self) -> None:
        # ``semgrep`` is in COMPREHENSIVE_HOOKS and its timeout is mirrored
        # in ``AdapterTimeouts`` as ``semgrep_timeout`` — this exercises
        # the ``_update_hook_timeouts_from_settings`` path inside the
        # comprehensive branch of ``load_strategy``.
        import crackerjack.config as cfg_pkg
        from crackerjack.config import CrackerjackSettings
        from crackerjack.config.settings import AdapterTimeouts

        real_load = cfg_pkg.load_settings

        def patched(cls):  # noqa: ARG001
            s = real_load(CrackerjackSettings)
            return s.model_copy(
                update={
                    "adapter_timeouts": AdapterTimeouts(semgrep_timeout=999)
                }
            )

        cfg_pkg.load_settings = patched
        try:
            strategy = HookConfigLoader.load_strategy("comprehensive")
        finally:
            cfg_pkg.load_settings = real_load
        semgrep_hook = next(h for h in strategy.hooks if h.name == "semgrep")
        assert semgrep_hook.timeout == 999

    def test_comprehensive_strategy_metadata(self) -> None:
        strategy = HookConfigLoader.load_strategy("comprehensive")
        assert isinstance(strategy, HookStrategy)
        assert strategy.name == "comprehensive"
        assert strategy.timeout == 1800
        assert strategy.parallel is True
        assert strategy.max_workers == 6
        assert strategy.retry_policy is RetryPolicy.NONE

    def test_comprehensive_strategy_hooks_are_fresh_list(self) -> None:
        # ``load_strategy`` builds a new HookStrategy with a fresh list —
        # NOT the same list as COMPREHENSIVE_HOOKS or COMPREHENSIVE_STRATEGY.
        strategy = HookConfigLoader.load_strategy("comprehensive")
        assert strategy.hooks is not COMPREHENSIVE_HOOKS
        assert strategy.hooks is not COMPREHENSIVE_STRATEGY.hooks

    def test_comprehensive_strategy_excludes_disabled(self) -> None:
        strategy = HookConfigLoader.load_strategy("comprehensive")
        names = {h.name for h in strategy.hooks}
        assert "gitleaks" not in names
        assert "skylos" not in names
        assert "complexipy" not in names

    def test_unknown_strategy_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown hook strategy"):
            HookConfigLoader.load_strategy("nope-not-a-real-strategy")

    def test_unknown_strategy_error_message_includes_name(self) -> None:
        with pytest.raises(ValueError) as exc:
            HookConfigLoader.load_strategy("bogus-xyz")
        assert "bogus-xyz" in str(exc.value)


# ---------------------------------------------------------------------------
# Cross-references between module-level strategies
# ---------------------------------------------------------------------------


class TestStrategyCrossReferences:
    def test_fast_strategy_hooks_match_fast_hooks_constant(self) -> None:
        # FAST_STRATEGY holds the FAST_HOOKS list reference directly.
        assert FAST_STRATEGY.hooks is FAST_HOOKS

    def test_comprehensive_strategy_hooks_filter_disabled(self) -> None:
        # COMPREHENSIVE_STRATEGY.hooks is a filtered copy (not a reference).
        assert COMPREHENSIVE_STRATEGY.hooks is not COMPREHENSIVE_HOOKS
        # Every entry satisfies auto_run=True and not disabled.
        for hook in COMPREHENSIVE_STRATEGY.hooks:
            assert hook.auto_run is True
            assert hook.disabled is False
