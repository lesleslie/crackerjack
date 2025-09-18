from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.code_cleaner import CodeCleaner
from crackerjack.interactive import (
    InteractiveCLI,
    Task,
    TaskDefinition,
    TaskStatus,
)
from crackerjack.models.config import WorkflowOptions


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path():
    return Path("/ test / path")


class TestCodeCleaner:
    @pytest.fixture
    def code_cleaner(self, console):
        return CodeCleaner(console=console)

    def test_init(self, code_cleaner, console) -> None:
        assert code_cleaner.console == console
        assert hasattr(code_cleaner, "clean_files")

    def test_clean_files_method_exists(self, code_cleaner) -> None:
        assert hasattr(code_cleaner, "clean_files")
        assert callable(code_cleaner.clean_files)

    def test_legacy_clean_method_exists(self, code_cleaner) -> None:
        assert hasattr(code_cleaner, "clean_files")
        assert callable(code_cleaner.clean_files)


class TestInteractiveModules:
    def test_task_status_enum(self) -> None:
        assert TaskStatus.PENDING is not None
        assert TaskStatus.RUNNING is not None
        assert TaskStatus.SUCCESS is not None
        assert TaskStatus.FAILED is not None
        assert TaskStatus.SKIPPED is not None

    def test_workflow_options_defaults(self) -> None:
        options = WorkflowOptions()

        assert options.clean is False
        assert options.test is False
        assert options.publish is None
        assert options.bump is None
        assert options.commit is False
        assert options.interactive is True
        assert options.dry_run is False

    def test_workflow_options_with_values(self) -> None:
        options = WorkflowOptions(
            clean=True,
            test=True,
            publish="patch",
            bump="minor",
            commit=True,
            dry_run=True,
        )

        assert options.clean is True
        assert options.test is True
        assert options.publish == "patch"
        assert options.bump == "minor"
        assert options.commit is True
        assert options.dry_run is True

    def test_workflow_options_from_args(self) -> None:
        mock_args = Mock()
        mock_args.clean = True
        mock_args.test = False
        mock_args.publish = "patch"
        mock_args.bump = None

        options = WorkflowOptions.from_args(mock_args)

        assert options.clean is True
        assert options.test is False
        assert options.publish == "patch"
        assert options.bump is None

    def test_task_creation(self) -> None:
        definition = TaskDefinition(
            id="test_task",
            name="Test Task",
            description="Test task description",
            dependencies=[],
        )
        task = Task(definition)

        assert task.definition.id == "test_task"
        assert task.definition.name == "Test Task"
        assert task.definition.description == "Test task description"
        assert task.status == TaskStatus.PENDING

    def test_task_status_transitions(self) -> None:
        definition = TaskDefinition(
            id="test_task",
            name="Test Task",
            description="Test task",
            dependencies=[],
        )
        task = Task(definition)

        task.start()
        assert task.status == TaskStatus.RUNNING

        task.complete(success=True)
        assert task.status == TaskStatus.SUCCESS

    def test_task_failure_handling(self) -> None:
        definition = TaskDefinition(
            id="failing_task",
            name="Failing Task",
            description="Failing task",
            dependencies=[],
        )
        task = Task(definition)

        task.start()
        task.complete(success=False)
        assert task.status == TaskStatus.FAILED


class TestModernInteractiveCLI:
    @pytest.fixture
    def interactive_cli(self, console):
        return InteractiveCLI(console)

    def test_init(self, interactive_cli, console) -> None:
        assert interactive_cli.console == console
