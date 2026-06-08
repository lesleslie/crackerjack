"""Tests for ``crackerjack.cli.handlers`` CLI command handlers.

Covers the public handler functions in ``crackerjack/cli/handlers.py``
(also re-exported through the ``crackerjack.cli.handlers`` package as
``crackerjack.cli.handlers.main_handlers``):
- ``setup_ai_agent_env``
- ``handle_interactive_mode``
- ``handle_standard_mode``
- ``handle_config_updates`` and the four dispatch helpers.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.cli import handlers as handlers_pkg
from crackerjack.cli.handlers import (
    handle_config_updates,
    handle_interactive_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)
from crackerjack.cli.handlers.main_handlers import (
    _apply_config_updates_batch,
    _display_available_updates,
    _get_configs_needing_update,
    _handle_apply_updates,
    _handle_check_updates,
    _handle_diff_config,
    _handle_refresh_cache,
    _report_update_results,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshot & restore env vars touched by ``setup_ai_agent_env``."""
    tracked = (
        "CRACKERJACK_DEBUG",
        "AI_AGENT",
        "AI_AGENT_DEBUG",
        "AI_AGENT_VERBOSE",
    )
    original: dict[str, str | None] = {
        name: os.environ.get(name) for name in tracked
    }
    for name in tracked:
        monkeypatch.delenv(name, raising=False)
    yield
    for name, value in original.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


@pytest.fixture
def mock_console() -> MagicMock:
    """MagicMock suitable for any ConsoleInterface consumer."""
    mock = MagicMock()
    mock.print = MagicMock()
    return mock


@pytest.fixture
def options_factory() -> Any:
    """Factory that builds an ``Options`` instance with sensible defaults.

    Returns a callable that accepts kwargs and returns an ``Options`` model.
    """

    def _factory(**overrides: Any) -> Any:
        from crackerjack.cli.options import Options

        base: dict[str, Any] = {
            "check_config_updates": False,
            "apply_config_updates": False,
            "diff_config": None,
            "config_interactive": False,
            "refresh_cache": False,
            "publish": None,
            "cleanup_docs": False,
        }
        base.update(overrides)
        return Options(**base)

    return _factory


# ---------------------------------------------------------------------------
# setup_ai_agent_env
# ---------------------------------------------------------------------------


class TestSetupAiAgentEnv:
    """Behavioural matrix for ``setup_ai_agent_env``."""

    @pytest.mark.parametrize(
        ("ai_agent", "debug_mode", "expected"),
        [
            (True, True, {
                "CRACKERJACK_DEBUG": "1",
                "AI_AGENT": "1",
                "AI_AGENT_DEBUG": "1",
                "AI_AGENT_VERBOSE": "1",
            }),
            (True, False, {"AI_AGENT": "1"}),
            (False, True, {
                "CRACKERJACK_DEBUG": "1",
                "AI_AGENT_DEBUG": "1",
                "AI_AGENT_VERBOSE": "1",
            }),
            (False, False, {}),
        ],
    )
    def test_environment_variables(
        self,
        isolated_env: None,
        ai_agent: bool,
        debug_mode: bool,
        expected: dict[str, str],
    ) -> None:
        setup_ai_agent_env(ai_agent=ai_agent, debug_mode=debug_mode)

        for name, value in expected.items():
            assert os.environ.get(name) == value
        all_keys = {
            "CRACKERJACK_DEBUG",
            "AI_AGENT",
            "AI_AGENT_DEBUG",
            "AI_AGENT_VERBOSE",
        }
        for name in all_keys - expected.keys():
            assert os.environ.get(name) is None

    def test_uses_injected_console(self, isolated_env: None) -> None:
        console = MagicMock()
        setup_ai_agent_env(ai_agent=True, debug_mode=True, console=console)
        # AI Agent + debug branch prints at least 5 lines.
        assert console.print.call_count >= 4

    def test_no_console_does_not_raise(self, isolated_env: None) -> None:
        # When console=None, the function falls back to the package-level
        # ``console`` exposed by ``crackerjack.cli.handlers``.
        setup_ai_agent_env(ai_agent=True, debug_mode=False, console=None)
        # No banner printed for ai_agent only.
        # Environment vars should still be set.
        assert os.environ.get("AI_AGENT") == "1"

    def test_debug_mode_only_branch_prints(self, isolated_env: None) -> None:
        console = MagicMock()
        setup_ai_agent_env(ai_agent=False, debug_mode=True, console=console)
        assert console.print.call_count >= 2
        text = " ".join(str(c) for c in console.print.call_args_list)
        assert "AI Debug Mode Configuration" in text

    def test_overwrites_existing_values(self, isolated_env: None) -> None:
        os.environ["AI_AGENT"] = "0"
        os.environ["AI_AGENT_DEBUG"] = "0"
        setup_ai_agent_env(ai_agent=True, debug_mode=True)
        assert os.environ["AI_AGENT"] == "1"
        assert os.environ["AI_AGENT_DEBUG"] == "1"

    def test_debug_mode_calls_setup_structured_logging(
        self, isolated_env: None
    ) -> None:
        setup_fn = MagicMock()
        fake_module = MagicMock()
        fake_module.setup_structured_logging = setup_fn
        with patch.dict(
            sys.modules, {"crackerjack.services.logging": fake_module}
        ):
            setup_ai_agent_env(ai_agent=False, debug_mode=True)
        setup_fn.assert_called_once_with(level="DEBUG", json_output=True)

    def test_no_logging_when_debug_off(self, isolated_env: None) -> None:
        setup_fn = MagicMock()
        fake_module = MagicMock()
        fake_module.setup_structured_logging = setup_fn
        with patch.dict(
            sys.modules, {"crackerjack.services.logging": fake_module}
        ):
            setup_ai_agent_env(ai_agent=False, debug_mode=False)
        setup_fn.assert_not_called()

    def test_debug_branch_ai_agent_only_no_prints(
        self, isolated_env: None
    ) -> None:
        """ai_agent=True without debug does not print any banner."""
        console = MagicMock()
        setup_ai_agent_env(ai_agent=True, debug_mode=False, console=console)
        console.print.assert_not_called()


# ---------------------------------------------------------------------------
# handle_interactive_mode
# ---------------------------------------------------------------------------


class TestHandleInteractiveMode:
    def test_launches_interactive_cli_with_version(
        self, options_factory: Any
    ) -> None:
        options = options_factory()
        with patch("crackerjack.cli.interactive.launch_interactive_cli") as launch:
            with patch(
                "crackerjack.cli.version.get_package_version",
                return_value="9.9.9",
            ):
                handle_interactive_mode(options)
        launch.assert_called_once()
        args, _ = launch.call_args
        assert args[0] == "9.9.9"
        assert args[1] is options

    def test_propagates_exception_from_launcher(
        self, options_factory: Any
    ) -> None:
        options = options_factory()
        with patch(
            "crackerjack.cli.interactive.launch_interactive_cli",
            side_effect=RuntimeError("boom"),
        ):
            with patch(
                "crackerjack.cli.version.get_package_version",
                return_value="0.0.1",
            ):
                with pytest.raises(RuntimeError, match="boom"):
                    handle_interactive_mode(options)


# ---------------------------------------------------------------------------
# handle_standard_mode
# ---------------------------------------------------------------------------


class TestHandleStandardMode:
    def test_runs_facade_process(self, options_factory: Any) -> None:
        options = options_factory()
        facade = MagicMock()
        with patch("crackerjack.cli.facade.CrackerjackCLIFacade", return_value=facade):
            handle_standard_mode(options)
        facade.process.assert_called_once_with(options)

    def test_sets_cleanup_docs_when_publishing(
        self, options_factory: Any
    ) -> None:
        from crackerjack.cli.options import BumpOption

        options = options_factory(publish=BumpOption.patch)
        facade = MagicMock()
        fake_settings = MagicMock()
        fake_settings.documentation.auto_cleanup_on_publish = True
        with patch(
            "crackerjack.cli.facade.CrackerjackCLIFacade", return_value=facade
        ):
            with patch("crackerjack.config.load_settings", return_value=fake_settings):
                handle_standard_mode(options)
        assert options.cleanup_docs is True
        facade.process.assert_called_once_with(options)

    def test_publish_without_auto_cleanup_leaves_flag(
        self, options_factory: Any
    ) -> None:
        from crackerjack.cli.options import BumpOption

        options = options_factory(publish=BumpOption.patch, cleanup_docs=False)
        facade = MagicMock()
        fake_settings = MagicMock()
        fake_settings.documentation.auto_cleanup_on_publish = False
        with patch(
            "crackerjack.cli.facade.CrackerjackCLIFacade", return_value=facade
        ):
            with patch("crackerjack.config.load_settings", return_value=fake_settings):
                handle_standard_mode(options)
        assert options.cleanup_docs is False

    def test_no_publish_skips_settings_load(
        self, options_factory: Any
    ) -> None:
        options = options_factory(publish=None)
        facade = MagicMock()
        with patch("crackerjack.cli.facade.CrackerjackCLIFacade", return_value=facade):
            with patch("crackerjack.config.load_settings") as load:
                handle_standard_mode(options)
        load.assert_not_called()
        facade.process.assert_called_once_with(options)

    def test_accepts_job_id_arg(self, options_factory: Any) -> None:
        options = options_factory()
        facade = MagicMock()
        with patch("crackerjack.cli.facade.CrackerjackCLIFacade", return_value=facade):
            # job_id is accepted but currently unused.
            handle_standard_mode(options, job_id="job-123")
        facade.process.assert_called_once_with(options)

    def test_publish_with_cleanup_docs_already_true_skips(
        self, options_factory: Any
    ) -> None:
        from crackerjack.cli.options import BumpOption

        options = options_factory(publish=BumpOption.patch, cleanup_docs=True)
        facade = MagicMock()
        # If cleanup_docs already True, the gate `not options.cleanup_docs`
        # prevents re-entering the settings block.
        with patch("crackerjack.cli.facade.CrackerjackCLIFacade", return_value=facade):
            with patch("crackerjack.config.load_settings") as load:
                handle_standard_mode(options)
        load.assert_not_called()
        assert options.cleanup_docs is True


# ---------------------------------------------------------------------------
# handle_config_updates + dispatch helpers
# ---------------------------------------------------------------------------


def _make_service(updates: dict[str, Any] | None = None) -> MagicMock:
    """Return a MagicMock standing in for ``ConfigTemplateService``."""
    if updates is None:
        updates = {}
    svc = MagicMock()
    svc.check_updates = MagicMock(return_value=updates)
    svc._generate_diff_preview = MagicMock(return_value="--- diff ---")
    svc._invalidate_cache = MagicMock(return_value=None)
    svc.apply_update = MagicMock(return_value=True)
    return svc


class TestHandleConfigUpdatesDispatch:
    def test_check_dispatches_to_check_helper(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(check_config_updates=True)
        svc = _make_service()
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=svc,
            ):
                with patch(
                    "crackerjack.cli.handlers.main_handlers._handle_check_updates"
                ) as check:
                    handle_config_updates(opts)
        check.assert_called_once()

    def test_apply_dispatches_to_apply_helper(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(apply_config_updates=True)
        svc = _make_service()
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=svc,
            ):
                with patch(
                    "crackerjack.cli.handlers.main_handlers._handle_apply_updates"
                ) as apply_h:
                    handle_config_updates(opts)
        apply_h.assert_called_once()
        # Helper is called positionally: (config_service, pkg_path, interactive, console).
        args = apply_h.call_args.args
        assert args[2] is False  # interactive flag

    def test_apply_with_interactive_propagates(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(apply_config_updates=True, config_interactive=True)
        svc = _make_service()
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=svc,
            ):
                with patch(
                    "crackerjack.cli.handlers.main_handlers._handle_apply_updates"
                ) as apply_h:
                    handle_config_updates(opts)
        args = apply_h.call_args.args
        assert args[2] is True  # interactive flag

    def test_diff_dispatches_to_diff_helper(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(diff_config="pyproject")
        svc = _make_service()
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=svc,
            ):
                with patch(
                    "crackerjack.cli.handlers.main_handlers._handle_diff_config"
                ) as diff:
                    handle_config_updates(opts)
        diff.assert_called_once()
        # Helper is called positionally: (config_service, pkg_path, config_type, console).
        args = diff.call_args.args
        assert args[2] == "pyproject"

    def test_refresh_dispatches_to_refresh_helper(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(refresh_cache=True)
        svc = _make_service()
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=svc,
            ):
                with patch(
                    "crackerjack.cli.handlers.main_handlers._handle_refresh_cache"
                ) as refresh:
                    handle_config_updates(opts)
        refresh.assert_called_once()

    def test_no_action_is_noop(
        self, options_factory: Any
    ) -> None:
        opts = options_factory()
        svc = _make_service()
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=svc,
            ):
                handle_config_updates(opts)
        # None of the helpers should be called.
        svc.check_updates.assert_not_called()
        svc._invalidate_cache.assert_not_called()

    def test_check_takes_precedence_over_apply(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(
            check_config_updates=True, apply_config_updates=True
        )
        captured_console = MagicMock()
        with patch(
            "crackerjack.core.console.CrackerjackConsole", return_value=captured_console
        ):
            with patch(
                "crackerjack.services.config_template.ConfigTemplateService",
                return_value=_make_service(),
            ):
                with patch(
                    "crackerjack.cli.handlers.main_handlers._handle_check_updates"
                ) as check:
                    with patch(
                        "crackerjack.cli.handlers.main_handlers._handle_apply_updates"
                    ) as apply_h:
                        handle_config_updates(opts)
        check.assert_called_once()
        apply_h.assert_not_called()

    def test_uses_cwd_for_pkg_path(
        self, options_factory: Any
    ) -> None:
        opts = options_factory(check_config_updates=True)
        svc = _make_service()
        captured_console = MagicMock()
        with patch("pathlib.Path.cwd", return_value=Path("/tmp/proj")):
            with patch(
                "crackerjack.core.console.CrackerjackConsole",
                return_value=captured_console,
            ):
                with patch(
                    "crackerjack.services.config_template.ConfigTemplateService",
                    return_value=svc,
                ):
                    with patch(
                        "crackerjack.cli.handlers.main_handlers._handle_check_updates"
                    ) as check:
                        handle_config_updates(opts)
        # First positional arg is the service, second is the pkg_path.
        _, args, _ = check.mock_calls[0]
        assert args[1] == Path("/tmp/proj")


class TestHandleCheckUpdates:
    def test_no_updates(self, mock_console: MagicMock) -> None:
        svc = _make_service(updates={})
        _handle_check_updates(svc, Path("/tmp/pkg"), mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "No configuration templates available" in rendered

    def test_all_up_to_date(self, mock_console: MagicMock) -> None:
        info = MagicMock(needs_update=False)
        svc = _make_service(updates={"pyproject": info})
        _handle_check_updates(svc, Path("/tmp/pkg"), mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "All configurations are up to date" in rendered

    def test_needs_update_prints_list(
        self, mock_console: MagicMock
    ) -> None:
        info = MagicMock(
            needs_update=True, current_version="1.0", latest_version="2.0"
        )
        svc = _make_service(updates={"pyproject": info})
        _handle_check_updates(svc, Path("/tmp/pkg"), mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Available updates" in rendered
        assert "1.0" in rendered and "2.0" in rendered
        assert "--apply-config-updates" in rendered

    def test_mixed_updates_only_shows_pending(
        self, mock_console: MagicMock
    ) -> None:
        good = MagicMock(needs_update=False, current_version="1", latest_version="1")
        bad = MagicMock(needs_update=True, current_version="1", latest_version="2")
        svc = _make_service(updates={"pyproject": good, "ruff": bad})
        _handle_check_updates(svc, Path("/tmp/pkg"), mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "ruff" in rendered
        assert "All configurations are up to date" not in rendered


class TestHandleApplyUpdates:
    def test_no_updates_prints_warning(self, mock_console: MagicMock) -> None:
        svc = _make_service(updates={})
        _handle_apply_updates(svc, Path("/tmp/pkg"), False, mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "No configuration templates available" in rendered

    def test_all_already_current(self, mock_console: MagicMock) -> None:
        info = MagicMock(needs_update=False)
        svc = _make_service(updates={"pyproject": info})
        _handle_apply_updates(svc, Path("/tmp/pkg"), False, mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "already up to date" in rendered

    def test_successful_batch_reports_all_updated(
        self, mock_console: MagicMock
    ) -> None:
        a = MagicMock(needs_update=True)
        b = MagicMock(needs_update=True)
        svc = _make_service(updates={"a": a, "b": b})
        svc.apply_update = MagicMock(return_value=True)
        _handle_apply_updates(svc, Path("/tmp/pkg"), True, mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Successfully updated 2 configurations" in rendered

    def test_partial_success_reports_fraction(
        self, mock_console: MagicMock
    ) -> None:
        a = MagicMock(needs_update=True)
        b = MagicMock(needs_update=True)
        svc = _make_service(updates={"a": a, "b": b})

        def _apply(name: str, *_args: Any, **_kwargs: Any) -> bool:
            return name == "a"

        svc.apply_update.side_effect = _apply
        _handle_apply_updates(svc, Path("/tmp/pkg"), False, mock_console)
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Updated 1/2 configurations" in rendered


class TestHandleDiffConfig:
    def test_prints_diff(self, mock_console: MagicMock) -> None:
        svc = _make_service()
        svc._generate_diff_preview = MagicMock(return_value="hello diff")
        _handle_diff_config(svc, Path("/tmp/pkg"), "pyproject", mock_console)
        svc._generate_diff_preview.assert_called_once_with(
            "pyproject", Path("/tmp/pkg")
        )
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Showing diff for pyproject" in rendered
        assert "hello diff" in rendered

    def test_propagates_service_error(self, mock_console: MagicMock) -> None:
        svc = _make_service()
        svc._generate_diff_preview = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            _handle_diff_config(svc, Path("/tmp/pkg"), "pyproject", mock_console)


class TestHandleRefreshCache:
    def test_invalidates_and_reports(self, mock_console: MagicMock) -> None:
        svc = _make_service()
        _handle_refresh_cache(svc, Path("/tmp/pkg"), mock_console)
        svc._invalidate_cache.assert_called_once_with(Path("/tmp/pkg"))
        rendered = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Refreshing cache" in rendered
        assert "Cache refreshed" in rendered


# ---------------------------------------------------------------------------
# _display_available_updates, _get_configs_needing_update,
# _apply_config_updates_batch, _report_update_results
# ---------------------------------------------------------------------------


class TestDisplayAvailableUpdates:
    def test_prints_only_pending(self) -> None:
        good = MagicMock(needs_update=False, current_version="1", latest_version="1")
        bad = MagicMock(needs_update=True, current_version="1", latest_version="2")
        console = MagicMock()
        _display_available_updates({"pyproject": good, "ruff": bad}, console)
        rendered = " ".join(str(c) for c in console.print.call_args_list)
        assert "ruff" in rendered
        assert "1" in rendered and "2" in rendered
        # The "good" entry should not be printed in the loop.
        assert "pyproject: 1 → 1" not in rendered

    def test_empty_dict(self) -> None:
        console = MagicMock()
        _display_available_updates({}, console)
        # Just the header should be printed.
        assert console.print.call_count == 1


class TestGetConfigsNeedingUpdate:
    def test_filters_correctly(self) -> None:
        a = MagicMock(needs_update=True)
        b = MagicMock(needs_update=False)
        c = MagicMock(needs_update=True)
        result = _get_configs_needing_update({"a": a, "b": b, "c": c})
        assert sorted(result) == ["a", "c"]

    def test_empty(self) -> None:
        assert _get_configs_needing_update({}) == []

    def test_all_pending(self) -> None:
        a = MagicMock(needs_update=True)
        b = MagicMock(needs_update=True)
        assert _get_configs_needing_update({"a": a, "b": b}) == ["a", "b"]


class TestApplyConfigUpdatesBatch:
    def test_counts_successful_applications(self) -> None:
        svc = MagicMock()
        svc.apply_update = MagicMock(return_value=True)
        result = _apply_config_updates_batch(
            svc, ["a", "b", "c"], Path("/tmp/pkg"), True, MagicMock()
        )
        assert result == 3
        assert svc.apply_update.call_count == 3

    def test_counts_only_successful(self) -> None:
        svc = MagicMock()

        def _apply(name: str, *_args: Any, **_kwargs: Any) -> bool:
            return name != "b"

        svc.apply_update.side_effect = _apply
        result = _apply_config_updates_batch(
            svc, ["a", "b", "c"], Path("/tmp/pkg"), False, MagicMock()
        )
        assert result == 2

    def test_empty_configs_returns_zero(self) -> None:
        svc = MagicMock()
        result = _apply_config_updates_batch(
            svc, [], Path("/tmp/pkg"), False, MagicMock()
        )
        assert result == 0
        svc.apply_update.assert_not_called()

    def test_propagates_interactive_flag(self) -> None:
        svc = MagicMock()
        svc.apply_update = MagicMock(return_value=True)
        _apply_config_updates_batch(
            svc, ["a"], Path("/tmp/pkg"), True, MagicMock()
        )
        _, kwargs = svc.apply_update.call_args
        assert kwargs["interactive"] is True


class TestReportUpdateResults:
    def test_all_success(self) -> None:
        console = MagicMock()
        _report_update_results(3, 3, console)
        rendered = " ".join(str(c) for c in console.print.call_args_list)
        assert "Successfully updated 3 configurations" in rendered

    def test_partial_success(self) -> None:
        console = MagicMock()
        _report_update_results(1, 3, console)
        rendered = " ".join(str(c) for c in console.print.call_args_list)
        assert "Updated 1/3 configurations" in rendered

    def test_zero_success(self) -> None:
        console = MagicMock()
        _report_update_results(0, 2, console)
        rendered = " ".join(str(c) for c in console.print.call_args_list)
        # Zero == total is not satisfied when total > 0.
        assert "Updated 0/2 configurations" in rendered

    def test_zero_total_renders_success(self) -> None:
        console = MagicMock()
        _report_update_results(0, 0, console)
        rendered = " ".join(str(c) for c in console.print.call_args_list)
        assert "Successfully updated 0 configurations" in rendered


# ---------------------------------------------------------------------------
# Module-level: logger + console exposure
# ---------------------------------------------------------------------------


class TestModuleSurface:
    def test_logger_is_module_logger(self) -> None:
        assert isinstance(handlers_pkg.logger, logging.Logger)
        assert handlers_pkg.logger.name == "crackerjack.cli.handlers"

    def test_console_is_rich_console(self) -> None:
        from rich.console import Console

        assert isinstance(handlers_pkg.console, Console)
