import io
import os
import platform
import re
import subprocess
import time
import tokenize
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run as execute
from token import STRING
from tomllib import loads

from rich.console import Console
from tomli_w import dumps

config_files = (".gitignore", ".pre-commit-config.yaml", ".libcst.codemod.yaml")
interactive_hooks = ("refurb", "bandit", "pyright")
default_python_version = "3.13"


@t.runtime_checkable
class CommandRunner(t.Protocol):
    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]: ...


@t.runtime_checkable
class OptionsProtocol(t.Protocol):
    commit: bool
    interactive: bool
    doc: bool
    no_config_updates: bool
    verbose: bool
    update_precommit: bool
    clean: bool
    test: bool
    benchmark: bool
    benchmark_regression: bool
    benchmark_regression_threshold: float
    publish: t.Any | None
    bump: t.Any | None
    all: t.Any | None
    ai_agent: bool = False
    create_pr: bool = False
    skip_hooks: bool = False


@dataclass
class CodeCleaner:
    console: Console

    def clean_files(self, pkg_dir: Path | None) -> None:
        if pkg_dir is None:
            return
        for file_path in pkg_dir.rglob("*.py"):
            if not str(file_path.parent).startswith("__"):
                self.clean_file(file_path)

    def clean_file(self, file_path: Path) -> None:
        from .errors import CleaningError, ErrorCode, FileError, handle_error

        try:
            if file_path.resolve() == Path(__file__).resolve():
                self.console.print(f"Skipping cleaning of {file_path} (self file).")
                return
        except Exception as e:
            error = FileError(
                message="Error comparing file paths",
                error_code=ErrorCode.FILE_READ_ERROR,
                details=f"Failed to compare {file_path} with the current file: {e}",
                recovery="This is likely a file system permission issue. Check file permissions.",
                exit_code=0,  # Non-fatal error
            )
            handle_error(error, self.console, verbose=True, exit_on_error=False)
            return

        try:
            # Check if file exists and is readable
            if not file_path.exists():
                error = FileError(
                    message="File not found",
                    error_code=ErrorCode.FILE_NOT_FOUND,
                    details=f"The file {file_path} does not exist.",
                    recovery="Check the file path and ensure the file exists.",
                    exit_code=0,  # Non-fatal error
                )
                handle_error(error, self.console, verbose=True, exit_on_error=False)
                return

            try:
                code = file_path.read_text()
            except Exception as e:
                error = FileError(
                    message="Error reading file",
                    error_code=ErrorCode.FILE_READ_ERROR,
                    details=f"Failed to read {file_path}: {e}",
                    recovery="Check file permissions and ensure the file is not locked by another process.",
                    exit_code=0,  # Non-fatal error
                )
                handle_error(error, self.console, verbose=True, exit_on_error=False)
                return

            # Process the file content
            code = self.remove_docstrings(code)
            code = self.remove_line_comments(code)
            code = self.remove_extra_whitespace(code)
            code = self.reformat_code(code)

            try:
                file_path.write_text(code)  # type: ignore
                self.console.print(f"Cleaned: {file_path}")
            except Exception as e:
                error = FileError(
                    message="Error writing file",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                    details=f"Failed to write to {file_path}: {e}",
                    recovery="Check file permissions and ensure the file is not locked by another process.",
                    exit_code=0,  # Non-fatal error
                )
                handle_error(error, self.console, verbose=True, exit_on_error=False)

        except Exception as e:
            error = CleaningError(
                message="Error cleaning file",
                error_code=ErrorCode.CODE_CLEANING_ERROR,
                details=f"Failed to clean {file_path}: {e}",
                recovery="This could be due to syntax errors in the file. Try manually checking the file for syntax errors.",
                exit_code=0,  # Non-fatal error
            )
            handle_error(error, self.console, verbose=True, exit_on_error=False)

    def remove_line_comments(self, code: str) -> str:
        new_lines = []
        for line in code.splitlines():
            if "#" not in line or line.endswith("# skip"):
                new_lines.append(line)
                continue
            if re.search(r"#\s", line):
                idx = line.find("#")
                code_part = line[:idx].rstrip()
                comment_part = line[idx:]
                if (
                    " type: ignore" in comment_part
                    or " noqa" in comment_part
                    or " nosec" in comment_part
                    or " codespell:ignore" in comment_part
                ):
                    new_lines.append(line)
                else:
                    if code_part:
                        new_lines.append(code_part)
            else:
                new_lines.append(line)
        return "\n".join(new_lines)

    def _is_triple_quoted(self, token_string: str) -> bool:
        triple_quote_patterns = [
            ('"""', '"""'),
            ("'''", "'''"),
            ('r"""', '"""'),
            ("r'''", "'''"),
        ]
        return any(
            token_string.startswith(start) and token_string.endswith(end)
            for start, end in triple_quote_patterns
        )

    def _is_module_docstring(
        self, tokens: list[tokenize.TokenInfo], i: int, indent_level: int
    ) -> bool:
        if i <= 0 or indent_level != 0:
            return False
        preceding_tokens = tokens[:i]
        return not preceding_tokens

    def _is_function_or_class_docstring(
        self,
        tokens: list[tokenize.TokenInfo],
        i: int,
        last_token_type: t.Any,
        last_token_string: str,
    ) -> bool:
        if last_token_type != tokenize.OP or last_token_string != ":":  # nosec B105
            return False
        for prev_idx in range(i - 1, max(0, i - 20), -1):
            prev_token = tokens[prev_idx]
            if prev_token[1] in ("def", "class") and prev_token[0] == tokenize.NAME:
                return True
            elif prev_token[0] == tokenize.DEDENT:
                break
        return False

    def _is_variable_docstring(
        self, tokens: list[tokenize.TokenInfo], i: int, indent_level: int
    ) -> bool:
        if indent_level <= 0:
            return False
        for prev_idx in range(i - 1, max(0, i - 10), -1):
            if tokens[prev_idx][0]:
                return True
        return False

    def remove_docstrings(self, source: str) -> str:
        try:
            io_obj = io.StringIO(source)
            tokens = list(tokenize.generate_tokens(io_obj.readline))
            result_tokens = []
            indent_level = 0
            last_non_ws_token_type = None
            last_non_ws_token_string = ""  # nosec B105
            for i, token in enumerate(tokens):
                token_type, token_string, _, _, _ = token
                if token_type == tokenize.INDENT:
                    indent_level += 1
                elif token_type == tokenize.DEDENT:
                    indent_level -= 1
                if token_type == STRING and self._is_triple_quoted(token_string):
                    is_docstring = (
                        self._is_module_docstring(tokens, i, indent_level)
                        or self._is_function_or_class_docstring(
                            tokens, i, last_non_ws_token_type, last_non_ws_token_string
                        )
                        or self._is_variable_docstring(tokens, i, indent_level)
                    )
                    if is_docstring:
                        continue
                if token_type not in (
                    tokenize.NL,
                    tokenize.NEWLINE,
                    tokenize.INDENT,
                    tokenize.DEDENT,
                ):
                    last_non_ws_token_type = token_type
                    last_non_ws_token_string = token_string
                result_tokens.append(token)
            return tokenize.untokenize(result_tokens)
        except Exception as e:
            self.console.print(f"Error removing docstrings: {e}")
            return source

    def remove_extra_whitespace(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        for i, line in enumerate(lines):
            line = line.rstrip()
            if i > 0 and (not line) and (not cleaned_lines[-1]):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def reformat_code(self, code: str) -> str | None:
        from .errors import CleaningError, ErrorCode, handle_error

        try:
            import tempfile

            # Create a temporary file for formatting
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".py", mode="w+", delete=False
                ) as temp:
                    temp_path = Path(temp.name)
                    temp_path.write_text(code)
            except Exception as e:
                error = CleaningError(
                    message="Failed to create temporary file for formatting",
                    error_code=ErrorCode.FORMATTING_ERROR,
                    details=f"Error: {e}",
                    recovery="Check disk space and permissions for the temp directory.",
                    exit_code=0,  # Non-fatal
                )
                handle_error(error, self.console, verbose=True, exit_on_error=False)
                return code

            # Run Ruff to format the code
            try:
                result = subprocess.run(
                    ["ruff", "format", str(temp_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    try:
                        formatted_code = temp_path.read_text()
                    except Exception as e:
                        error = CleaningError(
                            message="Failed to read formatted code",
                            error_code=ErrorCode.FORMATTING_ERROR,
                            details=f"Error reading temporary file after formatting: {e}",
                            recovery="This might be a permissions issue. Check if Ruff is installed properly.",
                            exit_code=0,  # Non-fatal
                        )
                        handle_error(
                            error, self.console, verbose=True, exit_on_error=False
                        )
                        formatted_code = code
                else:
                    error = CleaningError(
                        message="Ruff formatting failed",
                        error_code=ErrorCode.FORMATTING_ERROR,
                        details=f"Ruff output: {result.stderr}",
                        recovery="The file might contain syntax errors. Check the file manually.",
                        exit_code=0,  # Non-fatal
                    )
                    handle_error(error, self.console, exit_on_error=False)
                    formatted_code = code
            except Exception as e:
                error = CleaningError(
                    message="Error running Ruff formatter",
                    error_code=ErrorCode.FORMATTING_ERROR,
                    details=f"Error: {e}",
                    recovery="Ensure Ruff is installed correctly. Run 'pip install ruff' to install it.",
                    exit_code=0,  # Non-fatal
                )
                handle_error(error, self.console, verbose=True, exit_on_error=False)
                formatted_code = code
            finally:
                # Clean up temporary file
                with suppress(FileNotFoundError):
                    temp_path.unlink()

            return formatted_code

        except Exception as e:
            error = CleaningError(
                message="Unexpected error during code formatting",
                error_code=ErrorCode.FORMATTING_ERROR,
                details=f"Error: {e}",
                recovery="This is an unexpected error. Please report this issue.",
                exit_code=0,  # Non-fatal
            )
            handle_error(error, self.console, verbose=True, exit_on_error=False)
            return code


@dataclass
class ConfigManager:
    our_path: Path
    pkg_path: Path
    pkg_name: str
    console: Console
    our_toml_path: Path | None = None
    pkg_toml_path: Path | None = None
    python_version: str = default_python_version
    dry_run: bool = False

    def swap_package_name(self, value: list[str] | str) -> list[str] | str:
        if isinstance(value, list):
            value.remove("crackerjack")
            value.append(self.pkg_name)
        else:
            value = value.replace("crackerjack", self.pkg_name)
        return value

    def update_pyproject_configs(self) -> None:
        self._setup_toml_paths()
        if self._is_crackerjack_project():
            self._handle_crackerjack_project()
            return
        our_toml_config = self._load_our_toml()
        pkg_toml_config = self._load_pkg_toml()
        self._ensure_required_sections(pkg_toml_config)
        self._update_tool_settings(our_toml_config, pkg_toml_config)
        self._update_python_version(our_toml_config, pkg_toml_config)
        self._save_pkg_toml(pkg_toml_config)

    def _setup_toml_paths(self) -> None:
        toml_file = "pyproject.toml"
        self.our_toml_path = self.our_path / toml_file
        self.pkg_toml_path = self.pkg_path / toml_file

    def _is_crackerjack_project(self) -> bool:
        return self.pkg_path.stem == "crackerjack"

    def _handle_crackerjack_project(self) -> None:
        if self.our_toml_path and self.pkg_toml_path:
            self.our_toml_path.write_text(self.pkg_toml_path.read_text())

    def _load_our_toml(self) -> dict[str, t.Any]:
        if self.our_toml_path:
            return loads(self.our_toml_path.read_text())
        return {}

    def _load_pkg_toml(self) -> dict[str, t.Any]:
        if self.pkg_toml_path:
            return loads(self.pkg_toml_path.read_text())
        return {}

    def _ensure_required_sections(self, pkg_toml_config: dict[str, t.Any]) -> None:
        pkg_toml_config.setdefault("tool", {})
        pkg_toml_config.setdefault("project", {})

    def _update_tool_settings(
        self, our_toml_config: dict[str, t.Any], pkg_toml_config: dict[str, t.Any]
    ) -> None:
        for tool, settings in our_toml_config.get("tool", {}).items():
            for setting, value in settings.items():
                if isinstance(value, dict):
                    for k, v in {
                        x: self.swap_package_name(y)
                        for x, y in value.items()
                        if isinstance(y, str | list) and "crackerjack" in str(y)
                    }.items():
                        settings[setting][k] = v
                elif isinstance(value, str | list) and "crackerjack" in str(value):
                    value = self.swap_package_name(value)
                    settings[setting] = value
                if setting in (
                    "exclude-deps",
                    "exclude",
                    "excluded",
                    "skips",
                    "ignore",
                ) and isinstance(value, list):
                    conf = pkg_toml_config["tool"].get(tool, {}).get(setting, [])
                    settings[setting] = list(set(conf + value))
            pkg_toml_config["tool"][tool] = settings

    def _update_python_version(
        self, our_toml_config: dict[str, t.Any], pkg_toml_config: dict[str, t.Any]
    ) -> None:
        python_version_pattern = "\\s*W*(\\d\\.\\d*)"
        requires_python = our_toml_config.get("project", {}).get("requires-python", "")
        classifiers = []
        for classifier in pkg_toml_config.get("project", {}).get("classifiers", []):
            classifier = re.sub(
                python_version_pattern, f" {self.python_version}", classifier
            )
            classifiers.append(classifier)
        pkg_toml_config["project"]["classifiers"] = classifiers
        if requires_python:
            pkg_toml_config["project"]["requires-python"] = requires_python

    def _save_pkg_toml(self, pkg_toml_config: dict[str, t.Any]) -> None:
        if self.pkg_toml_path:
            self.pkg_toml_path.write_text(dumps(pkg_toml_config))

    def copy_configs(self) -> None:
        for config in config_files:
            config_path = self.our_path / config
            pkg_config_path = self.pkg_path / config
            pkg_config_path.touch()
            if self.pkg_path.stem == "crackerjack":
                config_path.write_text(pkg_config_path.read_text())
                continue
            if config != ".gitignore":
                pkg_config_path.write_text(
                    config_path.read_text().replace("crackerjack", self.pkg_name)
                )
            self.execute_command(["git", "add", config])

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(f"[yellow]Would run: {' '.join(cmd)}[/yellow]")
            return CompletedProcess(cmd, 0, "", "")
        return execute(cmd, **kwargs)


@dataclass
class ProjectManager:
    our_path: Path
    pkg_path: Path
    console: Console
    code_cleaner: CodeCleaner
    config_manager: ConfigManager
    pkg_dir: Path | None = None
    pkg_name: str = "crackerjack"
    dry_run: bool = False

    def run_interactive(self, hook: str) -> None:
        from .errors import ErrorCode, ExecutionError, handle_error

        success: bool = False
        attempts = 0
        max_attempts = 3

        while not success and attempts < max_attempts:
            attempts += 1
            result = self.execute_command(
                ["pre-commit", "run", hook.lower(), "--all-files"]
            )

            if result.returncode > 0:
                self.console.print(
                    f"\n\n[yellow]Hook '{hook}' failed (attempt {attempts}/{max_attempts})[/yellow]"
                )

                # Give more detailed information about the failure
                if result.stderr:
                    self.console.print(f"[red]Error details:[/red]\n{result.stderr}")

                retry = input(f"Retry running {hook.title()}? (y/N): ")
                self.console.print()

                if retry.strip().lower() != "y":
                    error = ExecutionError(
                        message=f"Interactive hook '{hook}' failed",
                        error_code=ErrorCode.PRE_COMMIT_ERROR,
                        details=f"Hook execution output:\n{result.stderr or result.stdout}",
                        recovery=f"Try running the hook manually: pre-commit run {hook.lower()} --all-files",
                        exit_code=1,
                    )
                    handle_error(error=error, console=self.console)
            else:
                self.console.print(f"[green]✅ Hook '{hook}' succeeded![/green]")
                success = True

        if not success:
            error = ExecutionError(
                message=f"Interactive hook '{hook}' failed after {max_attempts} attempts",
                error_code=ErrorCode.PRE_COMMIT_ERROR,
                details="The hook continued to fail after multiple attempts.",
                recovery=f"Fix the issues manually and run: pre-commit run {hook.lower()} --all-files",
                exit_code=1,
            )
            handle_error(error=error, console=self.console)

    def update_pkg_configs(self) -> None:
        self.config_manager.copy_configs()
        installed_pkgs = self.execute_command(
            ["pdm", "list", "--freeze"], capture_output=True, text=True
        ).stdout.splitlines()
        if not len([pkg for pkg in installed_pkgs if "pre-commit" in pkg]):
            self.console.print("Initializing project...")
            self.execute_command(["pdm", "self", "add", "keyring"])
            self.execute_command(["pdm", "config", "python.use_uv", "true"])
            self.execute_command(["git", "init"])
            self.execute_command(["git", "branch", "-m", "main"])
            self.execute_command(["git", "add", "pyproject.toml"])
            self.execute_command(["git", "add", "pdm.lock"])
            self.execute_command(["pre-commit", "install"])
            self.execute_command(["git", "config", "advice.addIgnoredFile", "false"])
        self.config_manager.update_pyproject_configs()

    def run_pre_commit(self) -> None:
        from .errors import ErrorCode, ExecutionError, handle_error

        self.console.print("\nRunning pre-commit hooks...\n")
        check_all = self.execute_command(["pre-commit", "run", "--all-files"])

        if check_all.returncode > 0:
            # First retry
            self.console.print("\nSome pre-commit hooks failed. Retrying once...\n")
            check_all = self.execute_command(["pre-commit", "run", "--all-files"])

            if check_all.returncode > 0:
                error = ExecutionError(
                    message="Pre-commit hooks failed",
                    error_code=ErrorCode.PRE_COMMIT_ERROR,
                    details="Pre-commit hooks failed even after a retry. Check the output above for specific hook failures.",
                    recovery="Review the error messages above. Manually fix the issues or run specific hooks interactively with 'pre-commit run <hook-id>'.",
                    exit_code=1,
                )
                handle_error(error=error, console=self.console, verbose=True)

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(f"[yellow]Would run: {' '.join(cmd)}[/yellow]")
            return CompletedProcess(cmd, 0, "", "")
        return execute(cmd, **kwargs)


@dataclass
class Crackerjack:
    our_path: Path = field(default_factory=lambda: Path(__file__).parent)
    pkg_path: Path = field(default_factory=lambda: Path(Path.cwd()))
    pkg_dir: Path | None = None
    pkg_name: str = "crackerjack"
    python_version: str = default_python_version
    console: Console = field(default_factory=lambda: Console(force_terminal=True))
    dry_run: bool = False
    code_cleaner: CodeCleaner | None = None
    config_manager: ConfigManager | None = None
    project_manager: ProjectManager | None = None

    def __post_init__(self) -> None:
        if self.code_cleaner is None:
            self.code_cleaner = CodeCleaner(console=self.console)
        if self.config_manager is None:
            self.config_manager = ConfigManager(
                our_path=self.our_path,
                pkg_path=self.pkg_path,
                pkg_name=self.pkg_name,
                console=self.console,
                python_version=self.python_version,
                dry_run=self.dry_run,
            )
        if self.project_manager is None:
            self.project_manager = ProjectManager(
                our_path=self.our_path,
                pkg_path=self.pkg_path,
                pkg_dir=self.pkg_dir,
                pkg_name=self.pkg_name,
                console=self.console,
                code_cleaner=self.code_cleaner,
                config_manager=self.config_manager,
                dry_run=self.dry_run,
            )

    def _setup_package(self) -> None:
        self.pkg_name = self.pkg_path.stem.lower().replace("-", "_")
        self.pkg_dir = self.pkg_path / self.pkg_name
        self.pkg_dir.mkdir(exist_ok=True)
        self.console.print("\nCrackerjacking...\n")
        self.config_manager.pkg_name = self.pkg_name
        self.project_manager.pkg_name = self.pkg_name
        self.project_manager.pkg_dir = self.pkg_dir

    def _update_project(self, options: OptionsProtocol) -> None:
        from .errors import ErrorCode, ExecutionError, handle_error

        if not options.no_config_updates:
            self.project_manager.update_pkg_configs()
            result: CompletedProcess[str] = self.execute_command(
                ["pdm", "install"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.console.print("PDM installed: ✅\n")
            else:
                error = ExecutionError(
                    message="PDM installation failed",
                    error_code=ErrorCode.PDM_INSTALL_ERROR,
                    details=f"Command output:\n{result.stderr}",
                    recovery="Ensure PDM is installed. Run `pipx install pdm` and try again. Check for network issues or package conflicts.",
                    exit_code=1,
                )

                # Don't exit immediately - this isn't always fatal
                handle_error(
                    error=error,
                    console=self.console,
                    verbose=options.verbose,
                    ai_agent=options.ai_agent,
                    exit_on_error=False,
                )

    def _update_precommit(self, options: OptionsProtocol) -> None:
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            self.execute_command(["pre-commit", "autoupdate"])

    def _run_interactive_hooks(self, options: OptionsProtocol) -> None:
        if options.interactive:
            for hook in interactive_hooks:
                self.project_manager.run_interactive(hook)

    def _clean_project(self, options: OptionsProtocol) -> None:
        if options.clean:
            if self.pkg_dir:
                self.code_cleaner.clean_files(self.pkg_dir)
            # Skip cleaning test files as they may contain test data in docstrings and comments
            # that are necessary for the tests to function properly

    def _prepare_pytest_command(self, options: OptionsProtocol) -> list[str]:
        """Prepare pytest command with appropriate options.

        Configures pytest command with:
        - Standard options for formatting and output control
        - Benchmark options when benchmark mode is enabled
        - Benchmark regression options when regression testing is enabled
        - Parallel execution via xdist for non-benchmark tests

        Benchmark and parallel execution (xdist) are incompatible, so the command
        automatically disables parallelism when benchmarks are enabled.

        Args:
            options: Command options with benchmark and test settings

        Returns:
            List of command-line arguments for pytest
        """
        test = ["pytest"]
        if options.verbose:
            test.append("-v")

        test.extend(
            [
                "--capture=fd",  # Capture stdout/stderr at file descriptor level
                "--tb=short",  # Shorter traceback format
                "--no-header",  # Reduce output noise
                "--disable-warnings",  # Disable warning capture
                "--durations=0",  # Show slowest tests to identify potential hanging tests
                "--timeout=60",  # 1-minute timeout for tests
            ]
        )

        # Benchmarks and parallel testing are incompatible
        # Handle them mutually exclusively
        if options.benchmark or options.benchmark_regression:
            # When running benchmarks, avoid parallel execution
            # and apply specific benchmark options
            if options.benchmark:
                test.append("--benchmark")

            # Add benchmark regression testing options if enabled
            if options.benchmark_regression:
                test.extend(
                    [
                        "--benchmark-regression",
                        f"--benchmark-regression-threshold={options.benchmark_regression_threshold}",
                    ]
                )
        else:
            # No benchmarks - use parallel execution for speed
            test.append("-xvs")

        return test

    def _setup_test_environment(self) -> None:
        os.environ["PYTHONASYNCIO_DEBUG"] = "0"  # Disable asyncio debug mode
        os.environ["RUNNING_UNDER_CRACKERJACK"] = "1"  # Signal to conftest.py
        if "PYTEST_ASYNCIO_MODE" not in os.environ:
            os.environ["PYTEST_ASYNCIO_MODE"] = "strict"

    def _run_pytest_process(
        self, test_command: list[str]
    ) -> subprocess.CompletedProcess[str]:
        from .errors import ErrorCode, ExecutionError, handle_error

        try:
            process = subprocess.Popen(
                test_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            timeout = 300
            start_time = time.time()
            stdout_data = []
            stderr_data = []
            while process.poll() is None:
                if time.time() - start_time > timeout:
                    error = ExecutionError(
                        message="Test execution timed out after 5 minutes.",
                        error_code=ErrorCode.COMMAND_TIMEOUT,
                        details=f"Command: {' '.join(test_command)}\nTimeout: {timeout} seconds",
                        recovery="Check for infinite loops or deadlocks in your tests. Consider increasing the timeout or optimizing your tests.",
                    )

                    self.console.print(
                        "[red]Test execution timed out after 5 minutes. Terminating...[/red]"
                    )
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stderr_data.append(
                            "Process had to be forcefully terminated after timeout."
                        )
                    break

                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        stdout_data.append(line)
                        self.console.print(line, end="")
                if process.stderr:
                    line = process.stderr.readline()
                    if line:
                        stderr_data.append(line)
                        self.console.print(f"[red]{line}[/red]", end="")
                time.sleep(0.1)

            if process.stdout:
                for line in process.stdout:
                    stdout_data.append(line)
                    self.console.print(line, end="")
            if process.stderr:
                for line in process.stderr:
                    stderr_data.append(line)
                    self.console.print(f"[red]{line}[/red]", end="")

            returncode = process.returncode or 0
            stdout = "".join(stdout_data)
            stderr = "".join(stderr_data)

            return subprocess.CompletedProcess(
                args=test_command, returncode=returncode, stdout=stdout, stderr=stderr
            )

        except Exception as e:
            error = ExecutionError(
                message=f"Error running tests: {e}",
                error_code=ErrorCode.TEST_EXECUTION_ERROR,
                details=f"Command: {' '.join(test_command)}\nError: {e}",
                recovery="Check if pytest is installed and that your test files are properly formatted.",
                exit_code=1,
            )

            # Don't exit here, let the caller handle it
            handle_error(
                error=error, console=self.console, verbose=True, exit_on_error=False
            )

            return subprocess.CompletedProcess(test_command, 1, "", str(e))

    def _report_test_results(
        self, result: subprocess.CompletedProcess[str], ai_agent: str
    ) -> None:
        from .errors import ErrorCode, TestError, handle_error

        if result.returncode > 0:
            error_details = None
            if result.stderr:
                self.console.print(result.stderr)
                error_details = result.stderr

            if ai_agent:
                self.console.print(
                    '[json]{"status": "failed", "action": "tests", "returncode": '
                    + str(result.returncode)
                    + "}[/json]"
                )
            else:
                # Use the structured error handler
                error = TestError(
                    message="Tests failed. Please fix the errors.",
                    error_code=ErrorCode.TEST_FAILURE,
                    details=error_details,
                    recovery="Review the test output above for specific failures. Fix the issues in your code and run tests again.",
                    exit_code=1,
                )
                handle_error(
                    error=error,
                    console=self.console,
                    ai_agent=(ai_agent != ""),
                )

        if ai_agent:
            self.console.print('[json]{"status": "success", "action": "tests"}[/json]')
        else:
            self.console.print("\n\n✅ Tests passed successfully!\n")

    def _run_tests(self, options: OptionsProtocol) -> None:
        if options.test:
            ai_agent = os.environ.get("AI_AGENT", "")
            if ai_agent:
                self.console.print(
                    '[json]{"status": "running", "action": "tests"}[/json]'
                )
            else:
                self.console.print("\n\nRunning tests...\n")
            test_command = self._prepare_pytest_command(options)
            self._setup_test_environment()
            result = self._run_pytest_process(test_command)
            self._report_test_results(result, ai_agent)

    def _bump_version(self, options: OptionsProtocol) -> None:
        for option in (options.publish, options.bump):
            if option:
                self.execute_command(["pdm", "bump", option])
                break

    def _publish_project(self, options: OptionsProtocol) -> None:
        from .errors import ErrorCode, PublishError, handle_error

        if options.publish:
            if platform.system() == "Darwin":
                authorize = self.execute_command(
                    ["pdm", "self", "add", "keyring"], capture_output=True, text=True
                )
                if authorize.returncode > 0:
                    error = PublishError(
                        message="Authentication setup failed",
                        error_code=ErrorCode.AUTHENTICATION_ERROR,
                        details=f"Failed to add keyring support to PDM.\nCommand output:\n{authorize.stderr}",
                        recovery="Please manually add your keyring credentials to PDM. Run `pdm self add keyring` and try again.",
                        exit_code=1,
                    )
                    handle_error(
                        error=error,
                        console=self.console,
                        verbose=options.verbose,
                        ai_agent=options.ai_agent,
                    )

            build = self.execute_command(
                ["pdm", "build"], capture_output=True, text=True
            )
            self.console.print(build.stdout)

            if build.returncode > 0:
                error = PublishError(
                    message="Package build failed",
                    error_code=ErrorCode.BUILD_ERROR,
                    details=f"Command output:\n{build.stderr}",
                    recovery="Review the error message above for details. Common issues include missing dependencies, invalid project structure, or incorrect metadata in pyproject.toml.",
                    exit_code=1,
                )
                handle_error(
                    error=error,
                    console=self.console,
                    verbose=options.verbose,
                    ai_agent=options.ai_agent,
                )

            publish_result = self.execute_command(
                ["pdm", "publish", "--no-build"], capture_output=True, text=True
            )

            if publish_result.returncode > 0:
                error = PublishError(
                    message="Package publication failed",
                    error_code=ErrorCode.PUBLISH_ERROR,
                    details=f"Command output:\n{publish_result.stderr}",
                    recovery="Ensure you have the correct PyPI credentials configured. Check your internet connection and that the package name is available on PyPI.",
                    exit_code=1,
                )
                handle_error(
                    error=error,
                    console=self.console,
                    verbose=options.verbose,
                    ai_agent=options.ai_agent,
                )
            else:
                self.console.print("[green]✅ Package published successfully![/green]")

    def _commit_and_push(self, options: OptionsProtocol) -> None:
        if options.commit:
            commit_msg = input("\nCommit message: ")
            self.execute_command(
                ["git", "commit", "-m", commit_msg, "--no-verify", "--", "."]
            )
            self.execute_command(["git", "push", "origin", "main"])

    def _create_pull_request(self, options: OptionsProtocol) -> None:
        if options.create_pr:
            self.console.print("\nCreating pull request...")
            current_branch = self.execute_command(
                ["git", "branch", "--show-current"], capture_output=True, text=True
            ).stdout.strip()
            remote_url = self.execute_command(
                ["git", "remote", "get-url", "origin"], capture_output=True, text=True
            ).stdout.strip()
            is_github = "github.com" in remote_url
            is_gitlab = "gitlab.com" in remote_url
            if is_github:
                gh_installed = (
                    self.execute_command(
                        ["which", "gh"], capture_output=True, text=True
                    ).returncode
                    == 0
                )
                if not gh_installed:
                    self.console.print(
                        "\n[red]GitHub CLI (gh) is not installed. Please install it first:[/red]\n"
                        "  brew install gh  # for macOS\n"
                        "  or visit https://cli.github.com/ for other installation methods"
                    )
                    return
                auth_status = self.execute_command(
                    ["gh", "auth", "status"], capture_output=True, text=True
                ).returncode
                if auth_status != 0:
                    self.console.print(
                        "\n[red]You need to authenticate with GitHub first. Run:[/red]\n"
                        "  gh auth login"
                    )
                    return
                pr_title = input("\nEnter a title for your pull request: ")
                self.console.print(
                    "Enter a description for your pull request (press Ctrl+D when done):"
                )
                pr_description = ""
                with suppress(EOFError):
                    pr_description = "".join(iter(input, ""))
                self.console.print("Creating pull request to GitHub repository...")
                result = self.execute_command(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--title",
                        pr_title,
                        "--body",
                        pr_description,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.console.print(
                        f"\n[green]Pull request created successfully![/green]\n{result.stdout}"
                    )
                else:
                    self.console.print(
                        f"\n[red]Failed to create pull request:[/red]\n{result.stderr}"
                    )
            elif is_gitlab:
                glab_installed = (
                    self.execute_command(
                        ["which", "glab"], capture_output=True, text=True
                    ).returncode
                    == 0
                )
                if not glab_installed:
                    self.console.print(
                        "\n[red]GitLab CLI (glab) is not installed. Please install it first:[/red]\n"
                        "  brew install glab  # for macOS\n"
                        "  or visit https://gitlab.com/gitlab-org/cli for other installation methods"
                    )
                    return
                auth_status = self.execute_command(
                    ["glab", "auth", "status"], capture_output=True, text=True
                ).returncode
                if auth_status != 0:
                    self.console.print(
                        "\n[red]You need to authenticate with GitLab first. Run:[/red]\n"
                        "  glab auth login"
                    )
                    return
                mr_title = input("\nEnter a title for your merge request: ")
                self.console.print(
                    "Enter a description for your merge request (press Ctrl+D when done):"
                )
                mr_description = ""
                with suppress(EOFError):
                    mr_description = "".join(iter(input, ""))
                self.console.print("Creating merge request to GitLab repository...")
                result = self.execute_command(
                    [
                        "glab",
                        "mr",
                        "create",
                        "--title",
                        mr_title,
                        "--description",
                        mr_description,
                        "--source-branch",
                        current_branch,
                        "--target-branch",
                        "main",
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.console.print(
                        f"\n[green]Merge request created successfully![/green]\n{result.stdout}"
                    )
                else:
                    self.console.print(
                        f"\n[red]Failed to create merge request:[/red]\n{result.stderr}"
                    )
            else:
                self.console.print(
                    f"\n[red]Unsupported git hosting service: {remote_url}[/red]\n"
                    "This command currently supports GitHub and GitLab."
                )

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(f"[yellow]Would run: {' '.join(cmd)}[/yellow]")
            return CompletedProcess(cmd, 0, "", "")
        return execute(cmd, **kwargs)

    def process(self, options: OptionsProtocol) -> None:
        actions_performed = []
        if options.all:
            options.clean = True
            options.test = True
            options.publish = options.all
            options.commit = True

        self._setup_package()
        actions_performed.append("setup_package")

        self._update_project(options)
        actions_performed.append("update_project")

        self._update_precommit(options)
        if options.update_precommit:
            actions_performed.append("update_precommit")

        self._run_interactive_hooks(options)
        if options.interactive:
            actions_performed.append("run_interactive_hooks")

        self._clean_project(options)
        if options.clean:
            actions_performed.append("clean_project")

        if not options.skip_hooks:
            self.project_manager.run_pre_commit()
            actions_performed.append("run_pre_commit")
        else:
            self.console.print(
                "\n[yellow]Skipping pre-commit hooks as requested[/yellow]\n"
            )
            actions_performed.append("skip_pre_commit")

        self._run_tests(options)
        if options.test:
            actions_performed.append("run_tests")

        self._bump_version(options)
        if options.bump or options.publish:
            actions_performed.append("bump_version")

        self._publish_project(options)
        if options.publish:
            actions_performed.append("publish_project")

        self._commit_and_push(options)
        if options.commit:
            actions_performed.append("commit_and_push")

        self._create_pull_request(options)
        if options.create_pr:
            actions_performed.append("create_pull_request")

        if getattr(options, "ai_agent", False):
            import json

            result = {
                "status": "complete",
                "package": self.pkg_name,
                "actions": actions_performed,
            }
            self.console.print(f"[json]{json.dumps(result)}[/json]")
        else:
            self.console.print("\n🍺 Crackerjack complete!\n")


def create_crackerjack_runner(
    console: Console | None = None,
    our_path: Path | None = None,
    pkg_path: Path | None = None,
    python_version: str = default_python_version,
    dry_run: bool = False,
) -> Crackerjack:
    return Crackerjack(
        console=console or Console(force_terminal=True),
        our_path=our_path or Path(__file__).parent,
        pkg_path=pkg_path or Path.cwd(),
        python_version=python_version,
        dry_run=dry_run,
    )
