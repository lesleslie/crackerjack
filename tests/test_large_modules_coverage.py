"""
Tests for large modules to boost coverage significantly.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from crackerjack.code_cleaner import CodeCleaner
from crackerjack.interactive import (
    TaskStatus,
    WorkflowOptions,
    Task,
    TaskDefinition,
    ModernInteractiveCLI,
)


@pytest.fixture
def console():
    """Create a console instance."""
    return Console()


@pytest.fixture
def pkg_path():
    """Create a package path."""
    return Path("/test/path")


class TestCodeCleaner:
    """Test CodeCleaner functionality."""

    @pytest.fixture
    def code_cleaner(self, console):
        """Create a CodeCleaner instance."""
        return CodeCleaner(console)

    def test_init(self, code_cleaner, console):
        """Test CodeCleaner initialization."""
        assert code_cleaner.console == console
        assert hasattr(code_cleaner, 'clean_files')

    def test_clean_files_method_exists(self, code_cleaner):
        """Test that clean_files method exists."""
        assert hasattr(code_cleaner, 'clean_files')
        assert callable(code_cleaner.clean_files)
        
    def test_legacy_clean_method_exists(self, code_cleaner):
        """Test that legacy clean method exists.""" 
        assert hasattr(code_cleaner, 'clean')
        assert callable(code_cleaner.clean)


class TestInteractiveModules:
    """Test interactive module components."""

    def test_task_status_enum(self):
        """Test TaskStatus enum."""
        assert TaskStatus.PENDING is not None
        assert TaskStatus.RUNNING is not None
        assert TaskStatus.SUCCESS is not None
        assert TaskStatus.FAILED is not None
        assert TaskStatus.SKIPPED is not None

    def test_workflow_options_defaults(self):
        """Test WorkflowOptions default values."""
        options = WorkflowOptions()
        
        assert options.clean is False
        assert options.test is False
        assert options.publish is None
        assert options.bump is None
        assert options.commit is False
        assert options.interactive is True
        assert options.dry_run is False

    def test_workflow_options_with_values(self):
        """Test WorkflowOptions with explicit values."""
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

    def test_workflow_options_from_args(self):
        """Test creating WorkflowOptions from args."""
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

    def test_task_creation(self):
        """Test Task creation."""
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

    def test_task_status_transitions(self):
        """Test Task status transitions."""
        definition = TaskDefinition(
            id="test_task",
            name="Test Task",
            description="Test task",
            dependencies=[],
        )
        task = Task(definition)
        
        # Start task
        task.start()
        assert task.status == TaskStatus.RUNNING
        
        # Complete task successfully
        task.complete(success=True)
        assert task.status == TaskStatus.SUCCESS

    def test_task_failure_handling(self):
        """Test Task failure handling."""
        definition = TaskDefinition(
            id="failing_task",
            name="Failing Task", 
            description="Failing task",
            dependencies=[],
        )
        task = Task(definition)
        
        # Start and fail task
        task.start()
        task.complete(success=False)
        assert task.status == TaskStatus.FAILED


class TestModernInteractiveCLI:
    """Test ModernInteractiveCLI functionality."""

    @pytest.fixture
    def interactive_cli(self, console):
        """Create a ModernInteractiveCLI instance."""
        return ModernInteractiveCLI(console)

    def test_init(self, interactive_cli, console):
        """Test ModernInteractiveCLI initialization."""
        assert interactive_cli.console == console