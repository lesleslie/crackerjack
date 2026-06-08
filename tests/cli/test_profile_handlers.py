"""Unit tests for crackerjack.cli.profile_handlers.

Covers list, show, compare, apply, validate, and recommendation helpers.
The profile storage layer is mocked at the boundary (get_profile_loader) so
no YAML/JSON I/O is required.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer

from crackerjack.cli import profile_handlers
from crackerjack.cli.profile_handlers import (
    apply_profile_to_options,
    compare_profiles_command,
    get_profile_recommendation,
    list_profiles_command,
    show_profile_command,
    validate_profile_option,
)


def _metadata(
    name: str = "quick",
    description: str = "Quick profile",
    execution_time: str = "<1 min",
) -> MagicMock:
    return MagicMock(
        name=name, description=description, execution_time=execution_time
    )


def _config(
    name: str = "quick",
    description: str = "Quick profile",
    execution_time: str = "<1 min",
    *,
    testing_enabled: bool = True,
    testing_coverage: bool = True,
    testing_timeout: int = 60,
    testing_benchmark: bool = False,
    testing_parallel: bool = True,
    testing_auto_detect: bool = True,
    testing_max_workers: int = 4,
    testing_incremental: bool = True,
    output_verbose: bool = False,
    output_show_progress: bool = True,
    documentation_cleanup: bool = False,
    documentation_backup: bool = False,
    git_commit: bool = False,
    git_create_pr: bool = False,
    enabled_checks: list[str] | None = None,
    disabled_checks: list[str] | None = None,
    fail_on_coverage: bool = False,
    coverage_threshold: int | None = None,
    fail_on_ruff_errors: bool = True,
    fail_on_test_errors: bool = True,
    fail_on_complexity: bool = False,
    performance_parallel: bool = True,
    performance_cache: bool = True,
    performance_timeout: int = 60,
) -> MagicMock:
    metadata = _metadata(name=name, description=description, execution_time=execution_time)
    checks = {
        "enabled": enabled_checks or [],
        "disabled": disabled_checks or [],
    }
    quality_gates = MagicMock(
        fail_on_ruff_errors=fail_on_ruff_errors,
        fail_on_test_errors=fail_on_test_errors,
        fail_on_coverage=fail_on_coverage,
        coverage_threshold=coverage_threshold,
        fail_on_complexity=fail_on_complexity,
    )
    testing = MagicMock(
        enabled=testing_enabled,
        coverage=testing_coverage,
        timeout=testing_timeout,
        benchmark=testing_benchmark,
        parallel=testing_parallel,
        auto_detect_workers=testing_auto_detect,
        max_workers=testing_max_workers,
        incremental=testing_incremental,
    )
    output = MagicMock(
        verbose=output_verbose,
        show_progress=output_show_progress,
    )
    performance = MagicMock(
        parallel_execution=performance_parallel,
        cache_enabled=performance_cache,
        timeout=performance_timeout,
    )
    documentation = {
        "cleanup": documentation_cleanup,
        "backup_before_cleanup": documentation_backup,
    }
    git = {
        "commit": git_commit,
        "create_pr": git_create_pr,
    }
    cfg = MagicMock()
    cfg.profile = metadata
    cfg.checks = checks
    cfg.quality_gates = quality_gates
    cfg.testing = testing
    cfg.output = output
    cfg.performance = performance
    cfg.documentation = documentation
    cfg.git = git
    return cfg


def _loader(
    profiles: list[str] | None = None,
    *,
    metadata_by_name: dict[str, MagicMock] | None = None,
    config_by_name: dict[str, MagicMock] | None = None,
    default_profile: str = "standard",
    profile_exists: dict[str, bool] | None = None,
) -> MagicMock:
    loader = MagicMock()
    loader.list_profiles.return_value = profiles if profiles is not None else []
    loader.get_default_profile.return_value = default_profile
    if metadata_by_name:
        loader.get_profile_metadata.side_effect = lambda name: metadata_by_name[name]
    if config_by_name:
        loader.load_profile.side_effect = lambda name: config_by_name[name]
    if profile_exists:
        loader.profile_exists.side_effect = lambda name: profile_exists.get(name, False)
    return loader


# ---------------------------------------------------------------------------
# list_profiles_command
# ---------------------------------------------------------------------------


class TestListProfilesCommand:
    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_empty_profile_list(self, mock_console, mock_get_loader) -> None:
        mock_get_loader.return_value = _loader(profiles=[])
        with pytest.raises(typer.Exit) as exc_info:
            list_profiles_command()
        assert exc_info.value.exit_code == 0
        mock_console.print.assert_called_once()
        # ensure the message mentions no profiles
        call_args = mock_console.print.call_args.args[0]
        assert "No profiles" in call_args

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_lists_profiles_with_default_marker(self, mock_console, mock_get_loader) -> None:
        profiles = ["quick", "standard", "comprehensive"]
        metadata_by_name = {
            "quick": _metadata("quick", "Fast checks", "<1 min"),
            "standard": _metadata("standard", "Default checks", "~3 min"),
            "comprehensive": _metadata("comprehensive", "Full checks", "~10 min"),
        }
        mock_get_loader.return_value = _loader(
            profiles=profiles,
            metadata_by_name=metadata_by_name,
            default_profile="standard",
        )
        list_profiles_command()
        # The Rich Table is printed via console.print
        assert mock_console.print.called

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_handles_metadata_load_failure(self, mock_console, mock_get_loader) -> None:
        profiles = ["broken"]
        loader = _loader(profiles=profiles)
        loader.get_profile_metadata.side_effect = RuntimeError("boom")
        mock_get_loader.return_value = loader
        list_profiles_command()
        # Warning should be logged and table still printed with error row
        assert mock_console.print.called


# ---------------------------------------------------------------------------
# show_profile_command
# ---------------------------------------------------------------------------


class TestShowProfileCommand:
    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_show_existing_profile(self, mock_console, mock_get_loader) -> None:
        config = _config(
            name="quick",
            description="Quick checks",
            execution_time="<1 min",
            enabled_checks=["ruff", "pytest"],
            disabled_checks=["complexipy"],
            coverage_threshold=85,
        )
        loader = _loader(
            config_by_name={"quick": config},
            profile_exists={"quick": True},
        )
        mock_get_loader.return_value = loader
        show_profile_command("quick")
        # Multiple console.print calls for each section
        assert mock_console.print.call_count >= 5

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_show_profile_not_found(self, mock_console, mock_get_loader) -> None:
        loader = _loader(
            profiles=["standard"],
            profile_exists={"unknown": False},
        )
        mock_get_loader.return_value = loader
        with pytest.raises(typer.Exit) as exc_info:
            show_profile_command("unknown")
        assert exc_info.value.exit_code == 1
        # Two messages: red error + available list
        assert mock_console.print.call_count >= 2

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_show_profile_load_error(self, mock_console, mock_get_loader) -> None:
        loader = _loader(profile_exists={"quick": True})
        loader.load_profile.side_effect = RuntimeError("parse error")
        mock_get_loader.return_value = loader
        with pytest.raises(typer.Exit) as exc_info:
            show_profile_command("quick")
        assert exc_info.value.exit_code == 1

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_show_profile_without_testing_or_coverage_threshold(
        self, mock_console, mock_get_loader
    ) -> None:
        config = _config(
            name="quick",
            testing_enabled=False,
            coverage_threshold=None,
        )
        loader = _loader(
            config_by_name={"quick": config},
            profile_exists={"quick": True},
        )
        mock_get_loader.return_value = loader
        # testing.enabled=False branch: no testing details printed
        show_profile_command("quick")
        assert mock_console.print.called


# ---------------------------------------------------------------------------
# compare_profiles_command
# ---------------------------------------------------------------------------


class TestCompareProfilesCommand:
    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_compare_two_profiles_differences(self, mock_console, mock_get_loader) -> None:
        comparison = {
            "profile1": "quick",
            "profile2": "standard",
            "testing": {
                "enabled": {"quick": False, "standard": True},
                "coverage": {"quick": False, "standard": True},
            },
            "quality_gates": {
                "fail_on_coverage": {"quick": False, "standard": True},
            },
            "performance": {
                "timeout": {"quick": 60, "standard": 300},
            },
        }
        loader = _loader(
            profile_exists={"quick": True, "standard": True},
        )
        loader.compare_profiles.return_value = comparison
        mock_get_loader.return_value = loader
        compare_profiles_command("quick", "standard")
        assert mock_console.print.called

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_compare_first_profile_missing(self, mock_console, mock_get_loader) -> None:
        loader = _loader(
            profile_exists={"missing": False, "standard": True},
        )
        mock_get_loader.return_value = loader
        with pytest.raises(typer.Exit) as exc_info:
            compare_profiles_command("missing", "standard")
        assert exc_info.value.exit_code == 1

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_compare_second_profile_missing(self, mock_console, mock_get_loader) -> None:
        loader = _loader(
            profile_exists={"quick": True, "missing": False},
        )
        mock_get_loader.return_value = loader
        with pytest.raises(typer.Exit) as exc_info:
            compare_profiles_command("quick", "missing")
        assert exc_info.value.exit_code == 1

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_compare_profiles_loader_error(self, mock_console, mock_get_loader) -> None:
        loader = _loader(
            profile_exists={"quick": True, "standard": True},
        )
        loader.compare_profiles.side_effect = RuntimeError("compare failure")
        mock_get_loader.return_value = loader
        with pytest.raises(typer.Exit) as exc_info:
            compare_profiles_command("quick", "standard")
        assert exc_info.value.exit_code == 1

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_compare_profiles_with_identical_values(self, mock_console, mock_get_loader) -> None:
        # When the compared values are identical, no diff lines are printed for those keys
        comparison = {
            "profile1": "a",
            "profile2": "b",
            "testing": {
                "enabled": {"a": True, "b": True},
                "coverage": {"a": True, "b": True},
            },
            "quality_gates": {
                "fail_on_coverage": {"a": True, "b": True},
            },
        }
        loader = _loader(
            profile_exists={"a": True, "b": True},
        )
        loader.compare_profiles.return_value = comparison
        mock_get_loader.return_value = loader
        compare_profiles_command("a", "b")
        # Header lines printed but no per-key diff lines
        assert mock_console.print.called


# ---------------------------------------------------------------------------
# apply_profile_to_options
# ---------------------------------------------------------------------------


class TestApplyProfileToOptions:
    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_applies_testing_and_output_options(self, mock_console, mock_get_loader) -> None:
        config = _config(
            name="quick",
            testing_enabled=True,
            testing_coverage=True,
            testing_timeout=120,
            testing_benchmark=True,
            testing_parallel=True,
            testing_auto_detect=True,
            testing_max_workers=8,
            testing_incremental=True,
            output_verbose=False,
            output_show_progress=True,
        )
        loader = _loader(
            config_by_name={"quick": config},
            profile_exists={"quick": True},
        )
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=None,
            track_progress=None,
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        result = apply_profile_to_options("quick", options)
        assert result is options
        assert result.run_tests is True
        assert result.coverage is True
        assert result.test_timeout == 120
        assert result.benchmark is True
        # auto_detect_workers=True -> test_workers=0
        assert result.test_workers == 0
        assert result.incremental_tests is True
        assert result.verbose is False
        # track_progress was None, so it's set from config
        assert result.track_progress is True

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_applies_explicit_worker_count(self, mock_console, mock_get_loader) -> None:
        config = _config(
            name="standard",
            testing_parallel=True,
            testing_auto_detect=False,
            testing_max_workers=4,
        )
        loader = _loader(
            config_by_name={"standard": config},
            profile_exists={"standard": True},
        )
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=None,
            track_progress=False,
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        result = apply_profile_to_options("standard", options)
        # auto_detect_workers=False -> test_workers=config.testing.max_workers
        assert result.test_workers == 4

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_does_not_override_track_progress(self, mock_console, mock_get_loader) -> None:
        config = _config(name="quick", output_show_progress=True)
        loader = _loader(
            config_by_name={"quick": config},
            profile_exists={"quick": True},
        )
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=None,
            track_progress=False,  # already set explicitly
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        result = apply_profile_to_options("quick", options)
        # Already explicitly set to False, should be left alone
        assert result.track_progress is False

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_verbose_output_prints_applied_message(
        self, mock_console, mock_get_loader
    ) -> None:
        config = _config(name="verbose", output_verbose=True)
        loader = _loader(
            config_by_name={"verbose": config},
            profile_exists={"verbose": True},
        )
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=True,
            track_progress=None,
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        apply_profile_to_options("verbose", options)
        # verbose=True triggers a console.print with the applied message
        assert mock_console.print.called

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_applies_git_and_docs_options(self, mock_console, mock_get_loader) -> None:
        config = _config(
            name="standard",
            documentation_cleanup=True,
            documentation_backup=True,
            git_commit=True,
            git_create_pr=True,
        )
        loader = _loader(
            config_by_name={"standard": config},
            profile_exists={"standard": True},
        )
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=False,
            track_progress=None,
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        result = apply_profile_to_options("standard", options)
        assert result.cleanup_docs is True
        assert result.commit is True
        assert result.create_pr is True

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_apply_profile_not_found(self, mock_console, mock_get_loader) -> None:
        loader = _loader(profiles=["standard"], profile_exists={"unknown": False})
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=None,
            track_progress=None,
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        with pytest.raises(typer.Exit) as exc_info:
            apply_profile_to_options("unknown", options)
        assert exc_info.value.exit_code == 1

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_apply_profile_load_error(self, mock_console, mock_get_loader) -> None:
        loader = _loader(profile_exists={"quick": True})
        loader.load_profile.side_effect = RuntimeError("load failed")
        mock_get_loader.return_value = loader
        options = SimpleNamespace(
            run_tests=None,
            coverage=None,
            test_timeout=None,
            benchmark=None,
            test_workers=None,
            incremental_tests=None,
            verbose=None,
            track_progress=None,
            cleanup_docs=None,
            commit=None,
            create_pr=None,
        )
        with pytest.raises(typer.Exit) as exc_info:
            apply_profile_to_options("quick", options)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# validate_profile_option
# ---------------------------------------------------------------------------


class TestValidateProfileOption:
    def test_none_returns_none(self) -> None:
        # profile_name=None should short-circuit and return None
        assert validate_profile_option(None) is None

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_valid_profile_name_returned(self, mock_console, mock_get_loader) -> None:
        loader = _loader(profiles=["quick", "standard"], profile_exists={"quick": True})
        mock_get_loader.return_value = loader
        assert validate_profile_option("quick") == "quick"

    @patch("crackerjack.cli.profile_handlers.get_profile_loader")
    @patch("crackerjack.cli.profile_handlers.console")
    def test_invalid_profile_name_raises(self, mock_console, mock_get_loader) -> None:
        loader = _loader(profiles=["quick", "standard"], profile_exists={"nope": False})
        mock_get_loader.return_value = loader
        with pytest.raises(typer.Exit) as exc_info:
            validate_profile_option("nope")
        assert exc_info.value.exit_code == 1
        # Three messages: red invalid + available list + usage hint
        assert mock_console.print.call_count >= 3


# ---------------------------------------------------------------------------
# get_profile_recommendation
# ---------------------------------------------------------------------------


class TestGetProfileRecommendation:
    @pytest.mark.parametrize(
        "changed_files,time_constraint,ci_environment,expected",
        [
            (1, "quick", False, "quick"),
            (1, "standard", False, "standard"),
            (0, None, True, "comprehensive"),
            (4, None, False, "quick"),
            (10, None, False, "standard"),
            (50, None, False, "comprehensive"),
            (100, "quick", False, "quick"),
            (100, "standard", True, "standard"),
        ],
    )
    def test_recommendation_branches(
        self,
        changed_files: int,
        time_constraint: str | None,
        ci_environment: bool,
        expected: str,
    ) -> None:
        result = get_profile_recommendation(
            changed_files=changed_files,
            time_constraint=time_constraint,
            ci_environment=ci_environment,
        )
        assert result == expected

    def test_ci_environment_overrides_changed_files(self) -> None:
        # CI flag wins over small changed-files count
        assert get_profile_recommendation(0, ci_environment=True) == "comprehensive"

    def test_time_constraint_quick_wins(self) -> None:
        # Explicit time constraint wins over file count
        assert get_profile_recommendation(50, time_constraint="quick") == "quick"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


class TestModuleSurface:
    def test_all_exports(self) -> None:
        for name in (
            "list_profiles_command",
            "show_profile_command",
            "compare_profiles_command",
            "apply_profile_to_options",
            "validate_profile_option",
            "get_profile_recommendation",
        ):
            assert hasattr(profile_handlers, name)
            assert name in profile_handlers.__all__
