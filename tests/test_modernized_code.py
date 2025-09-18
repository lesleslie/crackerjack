import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.code_cleaner import (
    CleaningErrorHandler,
    CleaningResult,
    CodeCleaner,
    FileProcessor,
)
from crackerjack.interactive import (
    InteractiveCLI,
    InteractiveWorkflowOptions,
    Task,
    TaskDefinition,
    TaskExecutor,
    TaskStatus,
    WorkflowBuilder,
    WorkflowManager,
)
from crackerjack.models.config import WorkflowOptions


class TestCodeCleaner:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def cleaner(self, console):
        return CodeCleaner(console=console)

    def test_initialization(self, cleaner, console) -> None:
        assert cleaner.console == console
        assert cleaner.file_processor is not None
        assert cleaner.error_handler is not None
        assert cleaner.pipeline is not None

    def test_should_process_file_valid(self, cleaner, temp_path) -> None:
        test_file = temp_path / "test_module.py"
        assert cleaner.should_process_file(test_file) is True

    def test_should_process_file_invalid(self, cleaner, temp_path) -> None:
        cache_file = temp_path / "__pycache__" / "test.pyc"
        assert cleaner.should_process_file(cache_file) is False

        txt_file = temp_path / "readme.txt"
        assert cleaner.should_process_file(txt_file) is False

        hidden_file = temp_path / ".hidden.py"
        assert cleaner.should_process_file(hidden_file) is False

    def test_clean_files_empty_directory(self, cleaner, temp_path) -> None:
        results = cleaner.clean_files(temp_path)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_clean_file_basic(self, cleaner, temp_path) -> None:
        test_file = temp_path / "test.py"
        test_file.write_text("print('hello world')")

        result = cleaner.clean_file(test_file)

        assert isinstance(result, CleaningResult)
        assert result.file_path == test_file
        assert result.original_size > 0


class TestFileProcessor:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def processor(self, console):
        return FileProcessor(console=console)

    def test_read_file_safely_success(self, processor, temp_path) -> None:
        test_file = temp_path / "test.py"
        content = "print('hello')"
        test_file.write_text(content)

        result = processor.read_file_safely(test_file)
        assert result == content

    def test_read_file_safely_not_found(self, processor, temp_path) -> None:
        test_file = temp_path / "nonexistent.py"

        with pytest.raises(Exception):
            processor.read_file_safely(test_file)

    def test_write_file_safely_success(self, processor, temp_path) -> None:
        test_file = temp_path / "test.py"
        content = "print('hello')"

        processor.write_file_safely(test_file, content)
        assert test_file.read_text() == content

    def test_backup_file(self, processor, temp_path) -> None:
        test_file = temp_path / "test.py"
        content = "original content"
        test_file.write_text(content)

        backup_path = processor.backup_file(test_file)

        assert backup_path.exists()
        assert backup_path.name == "test.py.backup"
        assert backup_path.read_text() == content


class TestCleaningErrorHandler:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def handler(self, console):
        return CleaningErrorHandler(console=console)

    def test_handle_file_error(self, handler, temp_path) -> None:
        test_file = temp_path / "test.py"
        error = ValueError("Test error")

        handler.handle_file_error(test_file, error, "test_step")

    def test_log_cleaning_result_success(self, handler, temp_path) -> None:
        result = CleaningResult(
            file_path=temp_path / "test.py",
            success=True,
            steps_completed=["step1", "step2"],
            steps_failed=[],
            warnings=[],
            original_size=100,
            cleaned_size=90,
        )

        handler.log_cleaning_result(result)

    def test_log_cleaning_result_failure(self, handler, temp_path) -> None:
        result = CleaningResult(
            file_path=temp_path / "test.py",
            success=False,
            steps_completed=["step1"],
            steps_failed=["step2"],
            warnings=["warning1"],
            original_size=100,
            cleaned_size=100,
        )

        handler.log_cleaning_result(result)


class TestWorkflowBuilder:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def builder(self, console):
        return WorkflowBuilder(console)

    def test_add_task(self, builder) -> None:
        builder.add_task("test_task", "Test Task", "A test task")

        assert "test_task" in builder.tasks
        task_def = builder.tasks["test_task"]
        assert task_def.id == "test_task"
        assert task_def.name == "Test Task"
        assert task_def.description == "A test task"

    def test_add_conditional_task_enabled(self, builder) -> None:
        result = builder.add_conditional_task(
            condition=True,
            task_id="conditional_task",
            name="Conditional Task",
            description="A conditional task",
        )

        assert result == "conditional_task"
        assert "conditional_task" in builder.tasks

    def test_add_conditional_task_disabled(self, builder) -> None:
        result = builder.add_conditional_task(
            condition=False,
            task_id="conditional_task",
            name="Conditional Task",
            description="A conditional task",
            dependencies=["previous_task"],
        )

        assert result == "previous_task"
        assert "conditional_task" not in builder.tasks

    def test_build_valid_workflow(self, builder) -> None:
        builder.add_task("task1", "Task 1", "First task")
        builder.add_task("task2", "Task 2", "Second task", dependencies=["task1"])

        workflow = builder.build()

        assert len(workflow) == 2
        assert "task1" in workflow
        assert "task2" in workflow

    def test_build_invalid_dependency(self, builder) -> None:
        builder.add_task("task1", "Task 1", "First task", dependencies=["nonexistent"])

        with pytest.raises(ValueError, match="depends on unknown task"):
            builder.build()

    def test_build_circular_dependency(self, builder) -> None:
        builder.add_task("task1", "Task 1", "First task", dependencies=["task2"])
        builder.add_task("task2", "Task 2", "Second task", dependencies=["task1"])

        with pytest.raises(ValueError, match="Circular dependency"):
            builder.build()


class TestWorkflowManager:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def manager(self, console):
        return WorkflowManager(console)

    @pytest.fixture
    def sample_workflow(self):
        return {
            "task1": TaskDefinition("task1", "Task 1", "First task", []),
            "task2": TaskDefinition("task2", "Task 2", "Second task", ["task1"]),
        }

    def test_load_workflow(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        assert len(manager.tasks) == 2
        assert "task1" in manager.tasks
        assert "task2" in manager.tasks

    def test_get_next_task(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        next_task = manager.get_next_task()
        assert next_task is not None
        assert next_task.definition.id == "task1"

    def test_set_task_executor(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        executor = Mock(return_value=True)
        manager.set_task_executor("task1", executor)

        assert manager.tasks["task1"].executor == executor

    def test_run_task_success(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        executor = Mock(return_value=True)
        task = manager.tasks["task1"]
        task.executor = executor

        result = manager.run_task(task)

        assert result is True
        assert task.status == TaskStatus.SUCCESS
        executor.assert_called_once()

    def test_run_task_failure(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        executor = Mock(return_value=False)
        task = manager.tasks["task1"]
        task.executor = executor

        result = manager.run_task(task)

        assert result is False
        assert task.status == TaskStatus.FAILED

    def test_run_task_no_executor(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        task = manager.tasks["task1"]

        result = manager.run_task(task)

        assert result is True
        assert task.status == TaskStatus.SKIPPED

    def test_all_tasks_completed_false(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        assert manager.all_tasks_completed() is False

    def test_all_tasks_completed_true(self, manager, sample_workflow) -> None:
        manager.load_workflow(sample_workflow)

        for task in manager.tasks.values():
            task.status = TaskStatus.SUCCESS

        assert manager.all_tasks_completed() is True


class TestWorkflowOptions:
    def test_default_values(self) -> None:
        options = WorkflowOptions()

        assert options.clean is False
        assert options.test is False
        assert options.publish is None
        assert options.bump is None
        assert options.commit is False
        assert options.create_pr is False
        assert options.interactive is True
        assert options.dry_run is False

    def test_from_args_with_attributes(self) -> None:
        class MockArgs:
            clean = True
            test = True
            publish = "pypi"
            bump = "patch"
            commit = True
            create_pr = False
            interactive = False
            dry_run = True

        args = MockArgs()
        options = WorkflowOptions.from_args(args)

        assert options.clean is True
        assert options.test is True
        assert options.publish == "pypi"
        assert options.bump == "patch"
        assert options.commit is True
        assert options.create_pr is False
        assert options.interactive is False
        assert options.dry_run is True

    def test_from_args_missing_attributes(self) -> None:
        class MockArgs:
            clean = True

        args = MockArgs()
        options = WorkflowOptions.from_args(args)

        assert options.clean is True

        assert options.test is False
        assert options.publish is None


class TestInteractiveCLI:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def cli(self, console):
        return InteractiveCLI(console)

    def test_initialization(self, cli, console) -> None:
        assert cli.console == console
        assert isinstance(cli.workflow, WorkflowManager)

    def test_create_dynamic_workflow_minimal(self, cli) -> None:
        options = WorkflowOptions()
        cli.create_dynamic_workflow(options)

        assert len(cli.workflow.tasks) >= 3
        assert "setup" in cli.workflow.tasks
        assert "config" in cli.workflow.tasks
        assert "fast_hooks" in cli.workflow.tasks
        assert "comprehensive_hooks" in cli.workflow.tasks

    def test_create_dynamic_workflow_full(self, cli) -> None:
        options = WorkflowOptions(
            clean=True,
            test=True,
            publish="pypi",
            bump="patch",
            commit=True,
            create_pr=True,
        )
        cli.create_dynamic_workflow(options)

        expected_tasks = [
            "setup",
            "config",
            "clean",
            "fast_hooks",
            "test",
            "comprehensive_hooks",
            "version",
            "publish",
            "commit",
            "pr",
        ]

        for task_id in expected_tasks:
            assert task_id in cli.workflow.tasks
