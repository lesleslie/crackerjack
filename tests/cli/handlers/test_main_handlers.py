"""Tests for ``crackerjack.cli.handlers.main_handlers``.

The handlers wrap env setup, mode dispatch, and config-template updates.
Subprocess / facade boundaries are mocked at the module level so we
exercise the conditional branches (publish→cleanup_docs flag, four-way
config dispatch, apply-batch counting) without invoking the real
CrackerjackCLIFacade or ConfigTemplateService.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.cli.handlers import main_handlers
from crackerjack.cli.handlers.main_handlers import (
    _apply_config_updates_batch,
    _display_available_updates,
    _get_configs_needing_update,
    _handle_apply_updates,
    _handle_check_updates,
    _handle_diff_config,
    _handle_refresh_cache,
    _report_update_results,
    handle_config_updates,
    handle_interactive_mode,
    handle_standard_mode,
    setup_swarm_env,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip the swarm env vars before each test."""
    for var in (
        "CRACKERJACK_SWARM",
        "CRACKERJACK_SWARM_WORKERS",
        "CRACKERJACK_SWARM_MCP_PORT",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def console() -> MagicMock:
    """Plain MagicMock standing in for the ConsoleInterface protocol."""
    return MagicMock()


# ---------------------------------------------------------------------------
# setup_swarm_env
# ---------------------------------------------------------------------------


def test_setup_swarm_env_swarm_true() -> None:
    setup_swarm_env(swarm=True, workers=4, mcp_port=9000)
    assert os.environ["CRACKERJACK_SWARM"] == "1"
    assert os.environ["CRACKERJACK_SWARM_WORKERS"] == "4"
    assert os.environ["CRACKERJACK_SWARM_MCP_PORT"] == "9000"


def test_setup_swarm_env_swarm_false() -> None:
    setup_swarm_env(swarm=False, workers=2, mcp_port=8676)
    assert os.environ["CRACKERJACK_SWARM"] == "0"


# ---------------------------------------------------------------------------
# handle_interactive_mode
# ---------------------------------------------------------------------------


def test_handle_interactive_mode_launches_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """``handle_interactive_mode`` calls ``launch_interactive_cli`` with the
    package version and the options cast as ``OptionsProtocol``."""
    options = SimpleNamespace(verbose=True)

    captured: dict[str, object] = {}

    def fake_launch(version: str, opts: object) -> None:
        captured["version"] = version
        captured["opts"] = opts

    fake_get_version = lambda: "1.2.3"  # noqa: E731
    monkeypatch.setattr(
        "crackerjack.cli.interactive.launch_interactive_cli", fake_launch
    )
    monkeypatch.setattr(
        "crackerjack.cli.version.get_package_version", fake_get_version
    )
    handle_interactive_mode(options)  # type: ignore[arg-type]
    assert captured["version"] == "1.2.3"
    assert captured["opts"] is options


# ---------------------------------------------------------------------------
# handle_standard_mode
# ---------------------------------------------------------------------------


def test_handle_standard_mode_no_publish_no_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``publish``, the cleanup_docs flag stays untouched."""
    options = SimpleNamespace(publish=False, cleanup_docs=False)

    fake_runner = MagicMock()
    fake_facade = MagicMock(return_value=fake_runner)
    monkeypatch.setattr("crackerjack.cli.facade.CrackerjackCLIFacade", fake_facade)
    handle_standard_mode(options)  # type: ignore[arg-type]
    assert options.cleanup_docs is False
    fake_runner.process.assert_called_once()


def test_handle_standard_mode_publish_sets_cleanup_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``publish=True`` and ``cleanup_docs=False`` but
    ``auto_cleanup_on_publish=True``, the handler flips ``cleanup_docs=True``."""
    options = SimpleNamespace(publish=True, cleanup_docs=False)

    # Patch load_settings to return a settings stub.
    fake_settings = MagicMock()
    fake_settings.documentation.auto_cleanup_on_publish = True

    fake_loader = lambda _cls: fake_settings  # noqa: E731

    fake_runner = MagicMock()
    fake_facade = MagicMock(return_value=fake_runner)

    monkeypatch.setattr("crackerjack.config.load_settings", fake_loader)
    monkeypatch.setattr("crackerjack.cli.facade.CrackerjackCLIFacade", fake_facade)
    handle_standard_mode(options)  # type: ignore[arg-type]
    assert options.cleanup_docs is True
    fake_runner.process.assert_called_once()


def test_handle_standard_mode_publish_existing_cleanup_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``cleanup_docs`` is already True, the handler doesn't touch it."""
    options = SimpleNamespace(publish=True, cleanup_docs=True)

    # No load_settings patch needed — `if options.publish and not options.cleanup_docs:` is False.

    fake_runner = MagicMock()
    fake_facade = MagicMock(return_value=fake_runner)
    monkeypatch.setattr("crackerjack.cli.facade.CrackerjackCLIFacade", fake_facade)
    handle_standard_mode(options)  # type: ignore[arg-type]
    assert options.cleanup_docs is True


def test_handle_standard_mode_publish_no_auto_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``auto_cleanup_on_publish=False``, the flag is NOT flipped."""
    options = SimpleNamespace(publish=True, cleanup_docs=False)

    fake_settings = MagicMock()
    fake_settings.documentation.auto_cleanup_on_publish = False

    fake_runner = MagicMock()
    fake_facade = MagicMock(return_value=fake_runner)

    monkeypatch.setattr(
        "crackerjack.config.load_settings", lambda _cls: fake_settings
    )
    monkeypatch.setattr("crackerjack.cli.facade.CrackerjackCLIFacade", fake_facade)
    handle_standard_mode(options)  # type: ignore[arg-type]
    assert options.cleanup_docs is False


# ---------------------------------------------------------------------------
# handle_config_updates — dispatch
# ---------------------------------------------------------------------------


def _options(
    *,
    check: bool = False,
    apply: bool = False,
    diff: str | None = None,
    refresh: bool = False,
    interactive: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        check_config_updates=check,
        apply_config_updates=apply,
        diff_config=diff,
        refresh_cache=refresh,
        config_interactive=interactive,
    )


def test_handle_config_updates_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    called: dict[str, object] = {}

    def fake_check(service: object, path: object, console: object) -> None:
        called["check"] = (service, path, console)

    monkeypatch.setattr(main_handlers, "_handle_check_updates", fake_check)
    handle_config_updates(_options(check=True))  # type: ignore[arg-type]
    assert "check" in called


def test_handle_config_updates_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}

    def fake_apply(
        service: object, path: object, interactive: bool, console: object
    ) -> None:
        called["apply"] = interactive

    monkeypatch.setattr(main_handlers, "_handle_apply_updates", fake_apply)
    handle_config_updates(_options(apply=True, interactive=True))  # type: ignore[arg-type]
    assert called["apply"] is True


def test_handle_config_updates_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_diff(
        service: object, path: object, config_type: str, console: object
    ) -> None:
        called["diff"] = config_type

    monkeypatch.setattr(main_handlers, "_handle_diff_config", fake_diff)
    handle_config_updates(_options(diff="test-config"))  # type: ignore[arg-type]
    assert called["diff"] == "test-config"


def test_handle_config_updates_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_refresh(service: object, path: object, console: object) -> None:
        called["refresh"] = True

    monkeypatch.setattr(main_handlers, "_handle_refresh_cache", fake_refresh)
    handle_config_updates(_options(refresh=True))  # type: ignore[arg-type]
    assert called.get("refresh") is True


def test_handle_config_updates_no_flags_does_nothing() -> None:
    # No dispatch branch matches → silent no-op.
    handle_config_updates(_options())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _handle_check_updates
# ---------------------------------------------------------------------------


def test_handle_check_updates_no_updates(console: MagicMock) -> None:
    service = MagicMock()
    service.check_updates.return_value = {}
    _handle_check_updates(service, Path("/tmp/pkg"), console)  # type: ignore[arg-type]
    console.print.assert_called()


def test_handle_check_updates_all_up_to_date(console: MagicMock) -> None:
    update = SimpleNamespace(needs_update=False, current_version="1", latest_version="1")
    service = MagicMock()
    service.check_updates.return_value = {"test": update}
    _handle_check_updates(service, Path("/tmp/pkg"), console)  # type: ignore[arg-type]
    console.print.assert_called()


def test_handle_check_updates_has_updates(console: MagicMock) -> None:
    update = SimpleNamespace(needs_update=True, current_version="1", latest_version="2")
    service = MagicMock()
    service.check_updates.return_value = {"test": update}
    _handle_check_updates(service, Path("/tmp/pkg"), console)  # type: ignore[arg-type]
    printed = " ".join(str(c) for c in console.print.call_args_list)
    assert "test" in printed or "1" in printed


# ---------------------------------------------------------------------------
# _handle_apply_updates
# ---------------------------------------------------------------------------


def test_handle_apply_updates_no_templates(console: MagicMock) -> None:
    service = MagicMock()
    service.check_updates.return_value = {}
    _handle_apply_updates(service, Path("/tmp/pkg"), False, console)  # type: ignore[arg-type]
    console.print.assert_called()


def test_handle_apply_updates_all_up_to_date(console: MagicMock) -> None:
    update = SimpleNamespace(needs_update=False, current_version="1", latest_version="1")
    service = MagicMock()
    service.check_updates.return_value = {"test": update}
    _handle_apply_updates(service, Path("/tmp/pkg"), False, console)  # type: ignore[arg-type]
    console.print.assert_called()


def test_handle_apply_updates_runs_batch(console: MagicMock) -> None:
    update_a = SimpleNamespace(needs_update=True)
    update_b = SimpleNamespace(needs_update=True)
    update_c = SimpleNamespace(needs_update=False)
    service = MagicMock()
    service.check_updates.return_value = {"a": update_a, "b": update_b, "c": update_c}
    service.apply_update.side_effect = [True, False]  # a succeeds, b fails
    _handle_apply_updates(service, Path("/tmp/pkg"), True, console)  # type: ignore[arg-type]
    assert service.apply_update.call_count == 2
    printed = " ".join(str(c) for c in console.print.call_args_list)
    assert "1/2" in printed


# ---------------------------------------------------------------------------
# _handle_diff_config
# ---------------------------------------------------------------------------


def test_handle_diff_config(console: MagicMock) -> None:
    service = MagicMock()
    service._generate_diff_preview.return_value = "diff content"
    _handle_diff_config(service, Path("/tmp/pkg"), "test-config", console)  # type: ignore[arg-type]
    service._generate_diff_preview.assert_called_once_with(
        "test-config", Path("/tmp/pkg")
    )
    console.print.assert_called()


# ---------------------------------------------------------------------------
# _handle_refresh_cache
# ---------------------------------------------------------------------------


def test_handle_refresh_cache(console: MagicMock) -> None:
    service = MagicMock()
    _handle_refresh_cache(service, Path("/tmp/pkg"), console)  # type: ignore[arg-type]
    service._invalidate_cache.assert_called_once_with(Path("/tmp/pkg"))


# ---------------------------------------------------------------------------
# _display_available_updates
# ---------------------------------------------------------------------------


def test_display_available_updates_skips_non_needing(console: MagicMock) -> None:
    updates = {
        "a": SimpleNamespace(needs_update=True, current_version="1", latest_version="2"),
        "b": SimpleNamespace(needs_update=False, current_version="2", latest_version="2"),
    }
    _display_available_updates(updates, console)  # type: ignore[arg-type]
    printed = " ".join(str(c) for c in console.print.call_args_list)
    assert "a" in printed
    # The non-needing entry should not be rendered.
    assert "2 → 2" not in printed


# ---------------------------------------------------------------------------
# _get_configs_needing_update
# ---------------------------------------------------------------------------


def test_get_configs_needing_update() -> None:
    updates = {
        "a": SimpleNamespace(needs_update=True),
        "b": SimpleNamespace(needs_update=False),
        "c": SimpleNamespace(needs_update=True),
    }
    assert _get_configs_needing_update(updates) == ["a", "c"]


def test_get_configs_needing_update_empty() -> None:
    assert _get_configs_needing_update({}) == []


# ---------------------------------------------------------------------------
# _apply_config_updates_batch
# ---------------------------------------------------------------------------


def test_apply_config_updates_batch_counts_successes() -> None:
    service = MagicMock()
    service.apply_update.side_effect = [True, False, True]
    count = _apply_config_updates_batch(
        service, ["a", "b", "c"], Path("/tmp/pkg"), interactive=True,
        console=MagicMock(),  # type: ignore[arg-type]
    )
    assert count == 2
    assert service.apply_update.call_count == 3


# ---------------------------------------------------------------------------
# _report_update_results
# ---------------------------------------------------------------------------


def test_report_update_results_all_success(console: MagicMock) -> None:
    _report_update_results(3, 3, console)  # type: ignore[arg-type]
    printed = " ".join(str(c) for c in console.print.call_args_list)
    assert "3" in printed


def test_report_update_results_partial(console: MagicMock) -> None:
    _report_update_results(2, 5, console)  # type: ignore[arg-type]
    printed = " ".join(str(c) for c in console.print.call_args_list)
    assert "2/5" in printed
