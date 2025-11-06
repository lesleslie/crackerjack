import asyncio
import typing as t
from dataclasses import dataclass
from pathlib import Path

from acb.console import Console
from acb.depends import depends

from .code_cleaner import CleaningResult, CodeCleaner, PackageCleaningResult
from .core.workflow_orchestrator import WorkflowOrchestrator
from .errors import CrackerjackError, ErrorCode
from .interactive import InteractiveCLI, InteractiveWorkflowOptions
from .models.config import WorkflowOptions
from .services.regex_patterns import SAFE_PATTERNS


@dataclass
class QualityCheckResult:
    success: bool
    fast_hooks_passed: bool
    comprehensive_hooks_passed: bool
    errors: list[str]
    warnings: list[str]
    duration: float


@dataclass
class TestResult:
    success: bool
    passed_count: int
    failed_count: int
    coverage_percentage: float
    duration: float
    errors: list[str]


@dataclass
class PublishResult:
    success: bool
    version: str
    published_to: list[str]
    errors: list[str]


class CrackerjackAPI:
    def __init__(
        self,
        project_path: Path | None = None,
        console: Console | None = None,
        verbose: bool = False,
    ) -> None:
        self.project_path = project_path or Path.cwd()
        self.console = console or depends.get_sync(Console)
        self.verbose = verbose

        self.orchestrator = WorkflowOrchestrator(
            pkg_path=self.project_path,
            verbose=self.verbose,
        )

        self.container = t.cast(t.Any, getattr(self.orchestrator, "container", None))

        self._code_cleaner: CodeCleaner | None = None
        self._interactive_cli: InteractiveCLI | None = None

        import logging

        self.logger = logging.getLogger("crackerjack.api")

    @property
    def code_cleaner(self) -> CodeCleaner:
        if self._code_cleaner is None:
            self._code_cleaner = CodeCleaner(
                console=self.console, base_directory=self.project_path
            )
        return self._code_cleaner

    @property
    def interactive_cli(self) -> InteractiveCLI:
        if self._interactive_cli is None:
            self._interactive_cli = InteractiveCLI(console=self.console)
        return self._interactive_cli

    def run_quality_checks(
        self,
        fast_only: bool = False,
        autofix: bool = True,
    ) -> QualityCheckResult:
        import asyncio
        import time

        start_time = time.time()

        try:
            self.logger.info("Starting quality checks")

            options = self._create_options(autofix=autofix, skip_hooks=False)

            success = asyncio.run(
                self.orchestrator.pipeline.run_complete_workflow(options),
            )

            duration = time.time() - start_time

            return QualityCheckResult(
                success=success,
                fast_hooks_passed=success,
                comprehensive_hooks_passed=success if not fast_only else True,
                errors=[] if success else ["Quality checks failed"],
                warnings=[],
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.logger.exception(f"Quality checks failed: {e}")

            return QualityCheckResult(
                success=False,
                fast_hooks_passed=False,
                comprehensive_hooks_passed=False,
                errors=[str(e)],
                warnings=[],
                duration=duration,
            )

    def clean_code(
        self,
        target_dir: Path | None = None,
        backup: bool = True,
        safe_mode: bool = True,
    ) -> list[CleaningResult] | PackageCleaningResult:
        target_dir = target_dir or self._get_package_root()
        self.logger.info(f"Cleaning code in {target_dir} (safe_mode={safe_mode})")

        self._validate_code_before_cleaning(target_dir)

        if safe_mode:
            self.console.print(
                "[green]🛡️ Using safe mode with comprehensive backup protection[/green]"
            )
            return self._execute_safe_code_cleaning(target_dir)
        else:
            self.console.print(
                "[yellow]⚠️ Legacy mode - backup protection still enabled for safety[/yellow]"
            )
            self._notify_backup_status(backup)
            return self._execute_code_cleaning(target_dir)

    def _validate_code_before_cleaning(self, target_dir: Path) -> None:
        todos_found = self._check_for_todos(target_dir)
        if todos_found:
            self._handle_todos_found(todos_found, target_dir)

    def _handle_todos_found(
        self,
        todos_found: list[tuple[Path, int, str]],
        target_dir: Path,
    ) -> None:
        todo_count = len(todos_found)
        self.console.print(f"[red]❌ Found {todo_count} TODO(s) in codebase[/ red]")
        self.console.print(
            "[yellow]Please resolve all TODOs before running code cleaning (-x)[/ yellow]",
        )

        self._display_todo_summary(todos_found, target_dir, todo_count)

        raise CrackerjackError(
            message=f"Found {todo_count} TODO(s) in codebase. Resolve them before cleaning.",
            error_code=ErrorCode.VALIDATION_ERROR,
        )

    def _display_todo_summary(
        self,
        todos_found: list[tuple[Path, int, str]],
        target_dir: Path,
        todo_count: int,
    ) -> None:
        for _i, (file_path, line_no, content) in enumerate(todos_found[:5]):
            relative_path = file_path.relative_to(target_dir)
            self.console.print(f" {relative_path}: {line_no}: {content.strip()}")

        if todo_count > 5:
            self.console.print(f" ... and {todo_count - 5} more")

    def _notify_backup_status(self, backup: bool) -> None:
        if backup:
            self.console.print("[yellow]Note: Backup files will be created[/ yellow]")

    def _execute_safe_code_cleaning(self, target_dir: Path) -> PackageCleaningResult:
        try:
            result = self.code_cleaner.clean_files_with_backup(target_dir)
            self._report_safe_cleaning_results(result)
            return result
        except Exception as e:
            self._handle_cleaning_error(e)

    def _execute_code_cleaning(self, target_dir: Path) -> list[CleaningResult]:
        try:
            results = self.code_cleaner.clean_files(target_dir, use_backup=True)

            if isinstance(results, list):
                self._report_cleaning_results(results)
            else:
                self._report_safe_cleaning_results(results)
                results = results.file_results

            return results
        except Exception as e:
            self._handle_cleaning_error(e)

    def _report_safe_cleaning_results(self, result: PackageCleaningResult) -> None:
        if result.overall_success:
            self.console.print(
                f"[green]🎉 Package cleaning completed successfully![/green] "
                f"({result.successful_files}/{result.total_files} files cleaned)"
            )
        else:
            self.console.print(
                f"[red]❌ Package cleaning failed![/red] "
                f"({result.failed_files}/{result.total_files} files failed)"
            )

            if result.backup_restored:
                self.console.print(
                    "[yellow]⚠️ Files were automatically restored from backup[/yellow]"
                )

            if result.backup_metadata:
                self.console.print(
                    f"[blue]📦 Backup available at: {result.backup_metadata.backup_directory}[/blue]"
                )

    def _report_cleaning_results(self, results: list[CleaningResult]) -> None:
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        if successful > 0:
            self.console.print(
                f"[green]✅ Successfully cleaned {successful} files[/ green]",
            )
        if failed > 0:
            self.console.print(f"[red]❌ Failed to clean {failed} files[/ red]")

    def _handle_cleaning_error(self, error: Exception) -> t.NoReturn:
        self.logger.error(f"Code cleaning failed: {error}")
        raise CrackerjackError(
            message=f"Code cleaning failed: {error}",
            error_code=ErrorCode.CODE_CLEANING_ERROR,
        ) from error

    def run_tests(
        self,
        coverage: bool = False,
        workers: int | None = None,
        timeout: int | None = None,
    ) -> TestResult:
        import time

        start_time = time.time()

        try:
            self.logger.info("Running tests")

            options = self._create_options(
                test=True,
                test_workers=workers or 0,
                test_timeout=timeout or 0,
            )

            success = asyncio.run(
                self.orchestrator.pipeline.run_complete_workflow(options),
            )

            duration = time.time() - start_time

            return TestResult(
                success=success,
                passed_count=self._extract_test_passed_count(),
                failed_count=self._extract_test_failed_count(),
                coverage_percentage=self._extract_coverage_percentage(),
                duration=duration,
                errors=[] if success else ["Test execution failed"],
            )

        except Exception as e:
            duration = time.time() - start_time
            self.logger.exception(f"Test execution failed: {e}")

            return TestResult(
                success=False,
                passed_count=0,
                failed_count=0,
                coverage_percentage=0.0,
                duration=duration,
                errors=[str(e)],
            )

    def publish_package(
        self,
        version_bump: str | None = None,
        dry_run: bool = False,
    ) -> PublishResult:
        try:
            self.logger.info(
                f"Publishing package (version_bump={version_bump}, dry_run={dry_run})",
            )

            options = self._create_options(
                bump=version_bump,
                publish="pypi" if not dry_run else None,
            )

            success = asyncio.run(
                self.orchestrator.pipeline.run_complete_workflow(options),
            )

            return PublishResult(
                success=success,
                version=self._extract_current_version(),
                published_to=["pypi"] if success and not dry_run else [],
                errors=[] if success else ["Publishing failed"],
            )

        except Exception as e:
            self.logger.exception(f"Package publishing failed: {e}")

            return PublishResult(
                success=False,
                version="",
                published_to=[],
                errors=[str(e)],
            )

    def run_interactive_workflow(
        self,
        options: InteractiveWorkflowOptions | None = None,
    ) -> bool:
        options = options or InteractiveWorkflowOptions()

        self.logger.info("Starting interactive workflow")

        try:
            return self.interactive_cli.run_interactive_workflow(options)
        except Exception as e:
            self.logger.exception(f"Interactive workflow failed: {e}")
            self.console.print(f"[red]❌ Interactive workflow failed: {e}[/ red]")
            return False

    def create_workflow_options(
        self,
        clean: bool = False,
        test: bool = False,
        publish: str | None = None,
        bump: str | None = None,
        commit: bool = False,
        create_pr: bool = False,
        **kwargs: t.Any,
    ) -> WorkflowOptions:
        from .models.config import (
            CleaningConfig,
            ExecutionConfig,
            GitConfig,
            PublishConfig,
            TestConfig,
        )
        from .models.config import (
            WorkflowOptions as ModelsWorkflowOptions,
        )

        verbose = kwargs.pop("verbose", False)

        options = ModelsWorkflowOptions()

        if clean:
            options.cleaning = CleaningConfig(clean=True)
        if test:
            options.testing = TestConfig(test=True)
        if publish or bump:
            options.publishing = PublishConfig(publish=publish, bump=bump)
        if commit or create_pr:
            options.git = GitConfig(commit=commit, create_pr=create_pr)
        if verbose:
            options.execution = ExecutionConfig(verbose=True)

        for key, value in kwargs.items():
            if not hasattr(options, key):
                setattr(options, key, value)

        return options

    def get_project_info(self) -> dict[str, t.Any]:
        try:
            pyproject_path = self.project_path / "pyproject.toml"
            setup_py_path = self.project_path / "setup.py"

            is_python_project = pyproject_path.exists() or setup_py_path.exists()

            git_dir = self.project_path / ".git"
            is_git_repo = git_dir.exists()

            python_files = list[t.Any](self.project_path.rglob("*.py"))

            return {
                "project_path": str(self.project_path),
                "is_python_project": is_python_project,
                "is_git_repo": is_git_repo,
                "python_files_count": len(python_files),
                "has_pyproject_toml": pyproject_path.exists(),
                "has_setup_py": setup_py_path.exists(),
                "has_requirements_txt": (
                    self.project_path / "requirements.txt"
                ).exists(),
                "has_tests": any(self.project_path.rglob("test *.py")),
            }

        except Exception as e:
            self.logger.exception(f"Failed to get project info: {e}")
            return {"error": str(e)}

    def _create_options(self, **kwargs: t.Any) -> t.Any:
        class Options:
            def __init__(self, **kwargs: t.Any) -> None:
                self.commit = False
                self.interactive = False
                self.no_config_updates = False
                self.verbose = False
                self.clean = False
                self.test = False
                self.autofix = True
                self.publish = None
                self.bump = None
                self.test_workers = 0
                self.test_timeout = 0

                for key, value in kwargs.items():
                    setattr(self, key, value)

        return Options(**kwargs)

    def _extract_test_passed_count(self) -> int:
        try:
            test_manager = self.orchestrator.phases.test_manager
            if hasattr(test_manager, "get_test_results"):
                results = t.cast(t.Any, test_manager).get_test_results()
                return getattr(results, "passed_count", 0)
            return 0
        except Exception:
            return 0

    def _extract_test_failed_count(self) -> int:
        try:
            test_manager = self.orchestrator.phases.test_manager
            if hasattr(test_manager, "get_test_results"):
                results = t.cast(t.Any, test_manager).get_test_results()
                return getattr(results, "failed_count", 0)
            return 0
        except Exception:
            return 0

    def _extract_coverage_percentage(self) -> float:
        try:
            test_manager = self.orchestrator.phases.test_manager
            if hasattr(test_manager, "get_test_results"):
                results = t.cast(t.Any, test_manager).get_test_results()
                return getattr(results, "coverage_percentage", 0.0)
            return 0.0
        except Exception:
            return 0.0

    def _extract_current_version(self) -> str:
        try:
            pyproject_path = self.project_path / "pyproject.toml"
            if pyproject_path.exists():
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "version" in data["project"]:
                    return str(data["project"]["version"])
                if (
                    "tool" in data
                    and "poetry" in data["tool"]
                    and "version" in data["tool"]["poetry"]
                ):
                    return str(data["tool"]["poetry"]["version"])

            import importlib.metadata

            try:
                return importlib.metadata.version("crackerjack")
            except importlib.metadata.PackageNotFoundError:
                pass

            return "unknown"
        except Exception:
            return "unknown"

    def _check_for_todos(self, target_dir: Path) -> list[tuple[Path, int, str]]:
        task_pattern = SAFE_PATTERNS["todo_pattern"]
        python_files = self._get_python_files_for_todo_check(target_dir)
        return self._scan_files_for_todos(python_files, task_pattern)

    def _get_python_files_for_todo_check(self, target_dir: Path) -> list[Path]:
        python_files: list[Path] = []
        ignore_patterns = self._get_ignore_patterns()

        for py_file in target_dir.rglob("*.py"):
            if not self._should_skip_file(py_file, ignore_patterns):
                python_files.append(py_file)

        return python_files

    def _get_ignore_patterns(self) -> set[str]:
        return {
            "__pycache__",
            ".git",
            ".venv",
            "site-packages",
            ".pytest_cache",
            "build",
            "dist",
            "tests",
            "test",
            "examples",
            "example",
        }

    def _should_skip_file(self, py_file: Path, ignore_patterns: set[str]) -> bool:
        if py_file.name.startswith("."):
            return True

        return any(parent.name in ignore_patterns for parent in py_file.parents)

    def _scan_files_for_todos(
        self,
        python_files: list[Path],
        todo_pattern: t.Any,
    ) -> list[tuple[Path, int, str]]:
        todos_found: list[tuple[Path, int, str]] = []

        for file_path in python_files:
            file_todos = self._scan_single_file_for_todos(file_path, todo_pattern)
            todos_found.extend(file_todos)

        return todos_found

    def _scan_single_file_for_todos(
        self,
        file_path: Path,
        todo_pattern: t.Any,
    ) -> list[tuple[Path, int, str]]:
        todos: list[tuple[Path, int, str]] = []
        from contextlib import suppress

        with suppress(UnicodeDecodeError, PermissionError):
            with file_path.open() as f:
                for line_no, line in enumerate(f, 1):
                    original = line.strip()
                    processed = todo_pattern.apply(original)

                    if "todo" in original.lower() and original == processed:
                        todos.append((file_path, line_no, line))

        return todos

    def _get_package_root(self) -> Path:
        package_name = self._read_package_name_from_pyproject()
        if package_name:
            package_dir = self._find_package_directory_by_name(package_name)
            if package_dir:
                return package_dir

        fallback_dir = self._find_fallback_package_directory()
        return fallback_dir or self.project_path

    def _read_package_name_from_pyproject(self) -> str | None:
        pyproject_path = self.project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        from contextlib import suppress

        with suppress(Exception):
            import tomllib

            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            if "project" in data and "name" in data["project"]:
                return str(data["project"]["name"])

        return None

    def _find_package_directory_by_name(self, package_name: str) -> Path | None:
        package_dir = self.project_path / package_name
        if package_dir.exists() and package_dir.is_dir():
            return package_dir
        return None

    def _find_fallback_package_directory(self) -> Path | None:
        package_dir = self.project_path / self.project_path.name
        if self._is_valid_python_package_directory(package_dir):
            return package_dir
        return None

    def _is_valid_python_package_directory(self, directory: Path) -> bool:
        if not (directory.exists() and directory.is_dir()):
            return False
        return any(directory.glob("*.py"))


def run_quality_checks(
    project_path: Path | None = None,
    fast_only: bool = False,
    autofix: bool = True,
) -> QualityCheckResult:
    return CrackerjackAPI(project_path=project_path).run_quality_checks(
        fast_only=fast_only,
        autofix=autofix,
    )


def clean_code(
    project_path: Path | None = None,
    backup: bool = True,
    safe_mode: bool = True,
) -> list[CleaningResult] | PackageCleaningResult:
    return CrackerjackAPI(project_path=project_path).clean_code(
        backup=backup, safe_mode=safe_mode
    )


def run_tests(project_path: Path | None = None, coverage: bool = False) -> TestResult:
    return CrackerjackAPI(project_path=project_path).run_tests(coverage=coverage)


def publish_package(
    project_path: Path | None = None,
    version_bump: str | None = None,
    dry_run: bool = False,
) -> PublishResult:
    return CrackerjackAPI(project_path=project_path).publish_package(
        version_bump=version_bump,
        dry_run=dry_run,
    )
