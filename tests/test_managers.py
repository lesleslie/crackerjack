import subprocess
from unittest.mock import patch

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.managers.publish_manager import PublishManagerImpl
from crackerjack.managers.test_manager import TestManagementImpl


@pytest.fixture
def console():
    return Console(force_terminal=True)


@pytest.fixture
def temp_project(tmp_path):
    return tmp_path


class MockOptions:
    def __init__(self, **kwargs) -> None:
        self.test = False
        self.benchmark = False
        self.test_workers = 0
        self.test_timeout = 0
        self.verbose = False
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestHookManagerImpl:
    def test_initialization(self, console, temp_project) -> None:
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_run_fast_hooks_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="All hooks passed", stderr=""
        )
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        results = manager.run_fast_hooks()
        assert len(results) > 0
        assert all(result.stage == "fast" for result in results)

    @patch("subprocess.run")
    def test_run_fast_hooks_failure(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Hook failed: E501 line too long"
        )
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        results = manager.run_fast_hooks()
        assert len(results) > 0
        failed_results = [r for r in results if r.status == "failed"]
        assert len(failed_results) > 0

    @patch("subprocess.run")
    def test_run_comprehensive_hooks_success(
        self, mock_run, console, temp_project
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="All hooks passed", stderr=""
        )
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        results = manager.run_comprehensive_hooks()
        assert len(results) > 0
        assert all(result.stage == "comprehensive" for result in results)

    @patch("subprocess.run")
    def test_hook_timeout(self, mock_run, console, temp_project) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("pre-commit", 60)
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        results = manager.run_fast_hooks()
        assert len(results) > 0
        timeout_results = [r for r in results if r.status == "timeout"]
        assert len(timeout_results) > 0

    @patch("subprocess.run")
    def test_install_hooks_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Hooks installed", stderr=""
        )
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        result = manager.install_hooks()
        assert result is True

    @patch("subprocess.run")
    def test_install_hooks_failure(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Installation failed"
        )
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        result = manager.install_hooks()
        assert result is False

    @patch("subprocess.run")
    def test_update_hooks_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Hooks updated", stderr=""
        )
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        result = manager.update_hooks()
        assert result is True

    def test_get_hook_summary_empty(self, console, temp_project) -> None:
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        summary = manager.get_hook_summary([])
        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0

    def test_get_hook_summary_with_results(self, console, temp_project) -> None:
        from crackerjack.models.task import HookResult

        results = [
            HookResult(id="1", name="test1", status="passed", duration=1.0),
            HookResult(id="2", name="test2", status="failed", duration=2.0),
            HookResult(id="3", name="test3", status="passed", duration=1.5),
        ]
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        summary = manager.get_hook_summary(results)
        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["total_duration"] == 4.5
        assert summary["success_rate"] == pytest.approx(66.67, rel=1e-2)


class TestTestManagementImpl:
    def test_initialization(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    def test_get_optimal_workers(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test_workers=4)
        workers = manager._get_optimal_workers(options)
        assert workers == 4
        options = MockOptions(test_workers=0)
        workers = manager._get_optimal_workers(options)
        assert workers >= 1

    def test_get_test_timeout(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test_timeout=600)
        timeout = manager._get_test_timeout(options)
        assert timeout == 600
        options = MockOptions(test_timeout=0)
        timeout = manager._get_test_timeout(options)
        assert timeout >= 300

    @patch("subprocess.run")
    def test_run_tests_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="5 passed", stderr=""
        )
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_run_tests_failure(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="2 failed"
        )
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        result = manager.run_tests(options)
        assert result is False

    @patch("subprocess.run")
    def test_run_tests_benchmark_mode(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Benchmarks passed", stderr=""
        )
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(benchmark=True)
        result = manager.run_tests(options)
        assert result is True
        call_args = mock_run.call_args[0][0]
        assert " -- benchmark - only" in call_args

    @patch("subprocess.run")
    def test_run_tests_timeout(self, mock_run, console, temp_project) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        result = manager.run_tests(options)
        assert result is False

    @patch("subprocess.run")
    def test_get_coverage_success(self, mock_run, console, temp_project) -> None:
        coverage_data = {
            "totals": {"percent_covered": 85.5},
            "files": {"test.py": {"percent_covered": 90.0}},
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=str(coverage_data).replace("'", '"'),
            stderr="",
        )
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        with patch("json.loads", return_value=coverage_data):
            coverage = manager.get_coverage()
            assert coverage["total_coverage"] == 85.5

    def test_validate_test_environment_no_tests_dir(
        self, console, temp_project
    ) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        result = manager.validate_test_environment()
        assert result is False

    def test_validate_test_environment_with_tests(self, console, temp_project) -> None:
        tests_dir = temp_project / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_example.py").write_text("def test_example(): pass")
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="pytest 7.0.0", stderr=""
            )
            result = manager.validate_test_environment()
            assert result is True

    @patch("subprocess.run")
    def test_run_specific_tests(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="2 passed", stderr=""
        )
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        result = manager.run_specific_tests("test_pattern")
        assert result is True
        call_args = mock_run.call_args[0][0]
        assert " - k" in call_args
        assert "test_pattern" in call_args

    def test_get_test_stats_no_tests(self, console, temp_project) -> None:
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        stats = manager.get_test_stats()
        assert stats["test_files"] == 0
        assert stats["total_tests"] == 0

    def test_get_test_stats_with_tests(self, console, temp_project) -> None:
        tests_dir = temp_project / "tests"
        tests_dir.mkdir()
        test_content = """
def test_one():
    pass

def test_two():
    pass
"""
        (tests_dir / "test_example.py").write_text(test_content)

        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        stats = manager.get_test_stats()

        assert stats["test_files"] == 1
        assert stats["total_tests"] == 2
        assert stats["avg_tests_per_file"] == 2.0


class TestPublishManagerImpl:
    def test_initialization(self, console, temp_project) -> None:
        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=True
        )
        assert manager.console is console
        assert manager.pkg_path == temp_project
        assert manager.dry_run is True

    def test_get_current_version_no_file(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        version = manager._get_current_version()
        assert version is None

    def test_get_current_version_with_file(self, console, temp_project) -> None:
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
"""
        (temp_project / "pyproject.toml").write_text(pyproject_content)

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        version = manager._get_current_version()
        assert version == "1.0.0"

    def test_calculate_next_version(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        next_version = manager._calculate_next_version("1.2.3", "patch")
        assert next_version == "1.2.4"
        next_version = manager._calculate_next_version("1.2.3", "minor")
        assert next_version == "1.3.0"
        next_version = manager._calculate_next_version("1.2.3", "major")
        assert next_version == "2.0.0"

    def test_calculate_next_version_invalid(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        with pytest.raises(ValueError):
            manager._calculate_next_version("invalid", "patch")
        with pytest.raises(ValueError):
            manager._calculate_next_version("1.0.0", "invalid")

    def test_bump_version_dry_run(self, console, temp_project) -> None:
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
"""
        (temp_project / "pyproject.toml").write_text(pyproject_content)

        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=True
        )
        new_version = manager.bump_version("patch")

        assert new_version == "1.0.1"
        content = (temp_project / "pyproject.toml").read_text()
        assert 'version = "1.0.0"' in content

    def test_bump_version_real(self, console, temp_project) -> None:
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
"""
        (temp_project / "pyproject.toml").write_text(pyproject_content)

        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=False
        )
        new_version = manager.bump_version("patch")

        assert new_version == "1.0.1"
        content = (temp_project / "pyproject.toml").read_text()
        assert 'version = "1.0.1"' in content

    @patch.dict("os.environ", {"UV_PUBLISH_TOKEN": "test - token"})
    def test_validate_auth_env_token(self, console, temp_project) -> None:
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        result = manager.validate_auth()
        assert result is True

    @patch.dict("os.environ", {}, clear=True)
    @patch("subprocess.run")
    def test_validate_auth_keyring(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="token", stderr=""
        )
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        result = manager.validate_auth()
        assert result is True

    @patch.dict("os.environ", {}, clear=True)
    @patch("subprocess.run")
    def test_validate_auth_none(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="not found"
        )
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        result = manager.validate_auth()
        assert result is False

    @patch("subprocess.run")
    def test_build_package_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Build successful", stderr=""
        )
        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=False
        )
        result = manager.build_package()
        assert result is True

    def test_build_package_dry_run(self, console, temp_project) -> None:
        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=True
        )
        result = manager.build_package()
        assert result is True

    def test_get_package_info(self, console, temp_project) -> None:
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
description = "A test package"
authors = [
    {name = "Test Author", email = "test@example.com"}
]
"""
        (temp_project / "pyproject.toml").write_text(pyproject_content)

        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        info = manager.get_package_info()

        assert info["name"] == "test-package"
        assert info["version"] == "1.0.0"
        assert info["description"] == "A test package"
        assert len(info["authors"]) == 1

    @patch("subprocess.run")
    def test_create_git_tag_success(self, mock_run, console, temp_project) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=False
        )
        result = manager.create_git_tag("1.0.1")
        assert result is True
        assert mock_run.call_count == 2

    def test_create_git_tag_dry_run(self, console, temp_project) -> None:
        manager = PublishManagerImpl(
            console=console, pkg_path=temp_project, dry_run=True
        )
        result = manager.create_git_tag("1.0.1")
        assert result is True
