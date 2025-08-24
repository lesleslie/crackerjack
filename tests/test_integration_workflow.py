import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator


class MockOptions:
    def __init__(self, **kwargs) -> None:
        self.commit = False
        self.interactive = False
        self.no_config_updates = False
        self.verbose = False
        self.update_docs = False
        self.clean = False
        self.test = False
        self.benchmark = False
        self.test_workers = 0
        self.test_timeout = 0
        self.publish = None
        self.bump = None
        self.all = None
        self.ai_agent = False
        self.autofix = False
        self.ai_agent_autofix = False
        self.start_mcp_server = False
        self.create_pr = False
        self.skip_hooks = False
        self.update_precommit = False
        self.async_mode = False
        self.track_progress = False
        self.progress_file = None
        self.experimental_hooks = False
        self.enable_pyrefly = False
        self.enable_ty = False
        self.no_git_tags = False
        self.skip_version_check = False
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        (project_path / "src").mkdir()
        (project_path / "tests").mkdir()
        python_file = project_path / "src" / "example.py"
        python_file.write_text('''"""Example module."""

def hello_world():
    print("Hello, world ! ")
if __name__ == "__main__":
    hello_world()
''')

        test_file = project_path / "tests" / "test_example.py"
        test_file.write_text('''"""Test example module."""

def test_hello_world():
    from src.example import hello_world
    hello_world()
''')

        pyproject_file = project_path / "pyproject.toml"
        pyproject_file.write_text("""[build - system]
requires = ["hatchling"]
build - backend = "hatchling.build"

[project]
name = "test - project"
version = "0.1.0"
description = "Test project for integration tests"
""")

        yield project_path


@pytest.fixture
def console():
    return Console(force_terminal=True)


class TestWorkflowIntegration:
    def test_basic_workflow_orchestrator(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions()
        result = orchestrator.run_configuration_phase(options)
        assert result is True

    def test_cleaning_phase_integration(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(clean=True)
        result = orchestrator.run_cleaning_phase(options)
        assert result is True

    def test_hooks_phase_with_mocked_commands(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(skip_hooks=False)
        with patch.object(
            orchestrator.phases.hook_manager, "run_fast_hooks",
        ) as mock_fast, patch.object(
            orchestrator.phases.hook_manager, "run_comprehensive_hooks",
        ) as mock_comp, patch.object(
            orchestrator.phases.hook_manager, "get_hook_summary",
        ) as mock_summary:
            mock_fast.return_value = []
            mock_comp.return_value = []
            mock_summary.return_value = {
                "failed": 0,
                "errors": 0,
                "passed": 5,
                "total": 5,
            }
            result = orchestrator.run_hooks_phase(options)
            assert result is True

    def test_testing_phase_with_mocked_pytest(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(test=True)
        with patch.object(
            orchestrator.phases.test_manager, "validate_test_environment",
        ) as mock_validate, patch.object(
            orchestrator.phases.test_manager, "run_tests",
        ) as mock_run, patch.object(
            orchestrator.phases.test_manager, "get_coverage",
        ) as mock_coverage:
            mock_validate.return_value = True
            mock_run.return_value = True
            mock_coverage.return_value = {"total_coverage": 85.0}
            result = orchestrator.run_testing_phase(options)
            assert result is True

    def test_publishing_phase_version_bump(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(bump="patch")
        with patch.object(
            orchestrator.phases.publish_manager, "bump_version",
        ) as mock_bump:
            mock_bump.return_value = "0.1.1"
            result = orchestrator.run_publishing_phase(options)
            assert result is True
            mock_bump.assert_called_once_with("patch")

    def test_commit_phase_no_changes(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(commit=True)
        with patch.object(
            orchestrator.phases.git_service, "get_changed_files",
        ) as mock_changes:
            mock_changes.return_value = []
            result = orchestrator.run_commit_phase(options)
            assert result is True


class TestCLIFacadeIntegration:
    def test_cli_facade_basic_workflow(self, temp_project, console) -> None:
        WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        with patch.object(
            facade.orchestrator, "run_complete_workflow",
        ) as mock_workflow:
            mock_workflow.return_value = True
            facade.process(options)
            mock_workflow.assert_called_once_with(options)

    def test_cli_facade_with_cleaning(self, temp_project, console) -> None:
        WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(clean=True, verbose=True)
        with patch.object(
            facade.orchestrator, "run_complete_workflow",
        ) as mock_workflow:
            mock_workflow.return_value = True
            facade.process(options)
            mock_workflow.assert_called_once_with(options)

    def test_cli_facade_with_testing(self, temp_project, console) -> None:
        WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        with patch.object(
            facade.orchestrator, "run_complete_workflow",
        ) as mock_workflow:
            mock_workflow.return_value = True
            facade.process(options)
            mock_workflow.assert_called_once_with(options)

    def test_cli_facade_error_handling(self, temp_project, console) -> None:
        WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        with patch.object(
            facade.orchestrator, "run_complete_workflow",
        ) as mock_workflow:
            mock_workflow.side_effect = Exception("Test error")
            with pytest.raises(SystemExit) as exc_info:
                facade.process(options)
            assert exc_info.value.code == 1

    def test_cli_facade_keyboard_interrupt(self, temp_project, console) -> None:
        WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        with patch.object(
            facade.orchestrator, "run_complete_workflow",
        ) as mock_workflow:
            mock_workflow.side_effect = KeyboardInterrupt()
            with pytest.raises(SystemExit) as exc_info:
                facade.process(options)
            assert exc_info.value.code == 130


class TestCompleteWorkflowIntegration:
    def test_complete_workflow_minimal_options(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions()
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_cleaning_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_hooks_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_testing_phase", return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_publishing_phase",
            return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_commit_phase",
            return_value=True,
        ):
            result = orchestrator.run_complete_workflow(options)
            assert result is True

    def test_complete_workflow_all_features(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(
            clean=True, test=True, commit=True, bump="patch", track_progress=True,
        )
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_cleaning_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_fast_hooks_only", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_testing_phase", return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_comprehensive_hooks_only",
            return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_publishing_phase",
            return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_commit_phase",
            return_value=True,
        ):
            result = orchestrator.run_complete_workflow(options)
            assert result is True

    def test_complete_workflow_failure_propagation(self, temp_project, console) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions()
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_cleaning_phase", return_value=False,
        ):
            result = orchestrator.run_complete_workflow(options)
            assert result is False

    def test_complete_workflow_autofix_continues_on_failure(
        self, temp_project, console,
    ) -> None:
        orchestrator = WorkflowOrchestrator(
            console=console, pkg_path=temp_project, dry_run=True,
        )
        options = MockOptions(autofix=True)
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_cleaning_phase", return_value=False,
        ), patch.object(
            orchestrator.phases, "run_hooks_phase", return_value=True,
        ), patch.object(
            orchestrator.phases, "run_testing_phase", return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_publishing_phase",
            return_value=True,
        ), patch.object(
            orchestrator.phases,
            "run_commit_phase",
            return_value=True,
        ):
            result = orchestrator.run_complete_workflow(options)
            assert result is False


class TestServiceIntegration:
    def test_filesystem_service_integration(self, temp_project) -> None:
        from crackerjack.services.filesystem import FileSystemService

        fs_service = FileSystemService()
        test_file = temp_project / "test.txt"
        test_content = "Hello, world ! "
        fs_service.write_file(test_file, test_content)
        assert fs_service.exists(test_file)
        read_content = fs_service.read_file(test_file)
        assert read_content == test_content
        python_files = fs_service.rglob(" * .py", temp_project)
        assert len(python_files) > 0

    def test_git_service_integration(self, temp_project, console) -> None:
        from crackerjack.services.git import GitService

        git_service = GitService(console=console, pkg_path=temp_project)
        is_repo = git_service.is_git_repo()
        assert is_repo is False
        test_files = ["test.py", "README.md"]
        suggestions = git_service.get_commit_message_suggestions(test_files)
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_config_service_integration(self, temp_project, console) -> None:
        from crackerjack.services.config import ConfigurationService

        config_service = ConfigurationService(console=console, pkg_path=temp_project)
        info = config_service.get_config_info()
        assert info["exists"] is False
        options = MockOptions()
        result = config_service.update_pyproject_config(options)
        assert result is True
