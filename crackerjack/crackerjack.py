import re
import subprocess
import typing as t
from contextlib import suppress
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run as execute
from tomllib import loads

from pydantic import BaseModel
from rich.console import Console
from tomli_w import dumps
from crackerjack.errors import ErrorCode, ExecutionError

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
    test_workers: int = 0
    test_timeout: int = 0
    publish: t.Any | None
    bump: t.Any | None
    all: t.Any | None
    ai_agent: bool = False
    create_pr: bool = False
    skip_hooks: bool = False


class CodeCleaner(BaseModel, arbitrary_types_allowed=True):
    console: Console

    def clean_files(self, pkg_dir: Path | None) -> None:
        if pkg_dir is None:
            return
        for file_path in pkg_dir.rglob("*.py"):
            if not str(file_path.parent).startswith("__"):
                self.clean_file(file_path)
        with suppress(PermissionError, OSError):
            pycache_dir = pkg_dir / "__pycache__"
            if pycache_dir.exists():
                for cache_file in pycache_dir.iterdir():
                    with suppress(PermissionError, OSError):
                        cache_file.unlink()
                pycache_dir.rmdir()
            parent_pycache = pkg_dir.parent / "__pycache__"
            if parent_pycache.exists():
                for cache_file in parent_pycache.iterdir():
                    with suppress(PermissionError, OSError):
                        cache_file.unlink()
                parent_pycache.rmdir()

    def clean_file(self, file_path: Path) -> None:
        try:
            code = file_path.read_text()
            code = self.remove_line_comments(code)
            code = self.remove_docstrings(code)
            code = self.remove_extra_whitespace(code)
            code = self.reformat_code(code)
            file_path.write_text(code)
            print(f"Cleaned: {file_path}")
        except Exception as e:
            print(f"Error cleaning {file_path}: {e}")

    def remove_docstrings(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        in_docstring = False
        docstring_delimiter = None
        waiting_for_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("def ", "class ", "async def ")):
                waiting_for_docstring = True
                cleaned_lines.append(line)
                continue
            if waiting_for_docstring and stripped:
                if stripped.startswith(('"""', "'''", '"', "'")):
                    if stripped.startswith(('"""', "'''")):
                        docstring_delimiter = stripped[:3]
                    else:
                        docstring_delimiter = stripped[0]
                    if stripped.endswith(docstring_delimiter) and len(stripped) > len(
                        docstring_delimiter
                    ):
                        waiting_for_docstring = False
                        continue
                    else:
                        in_docstring = True
                        waiting_for_docstring = False
                        continue
                else:
                    waiting_for_docstring = False
            if in_docstring:
                if docstring_delimiter and stripped.endswith(docstring_delimiter):
                    in_docstring = False
                    docstring_delimiter = None
                    continue
                else:
                    continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def remove_line_comments(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        for line in lines:
            if not line.strip():
                cleaned_lines.append(line)
                continue
            in_string = None
            result = []
            i = 0
            n = len(line)
            while i < n:
                char = line[i]
                if char in ("'", '"') and (i == 0 or line[i - 1] != "\\"):
                    if in_string is None:
                        in_string = char
                    elif in_string == char:
                        in_string = None
                    result.append(char)
                    i += 1
                elif char == "#" and in_string is None:
                    comment = line[i:].strip()
                    if re.match(
                        r"^#\s*(?:type:\s*ignore(?:\[.*?\])?|noqa|nosec|pragma:\s*no\s*cover|pylint:\s*disable|mypy:\s*ignore)",
                        comment,
                    ):
                        result.append(line[i:])
                        break
                    break
                else:
                    result.append(char)
                    i += 1
            cleaned_line = "".join(result).rstrip()
            if cleaned_line or not line.strip():
                cleaned_lines.append(cleaned_line or line)
        return "\n".join(cleaned_lines)

    def remove_extra_whitespace(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        in_function = False
        function_indent = 0
        for i, line in enumerate(lines):
            line = line.rstrip()
            stripped_line = line.lstrip()
            if stripped_line.startswith(("def ", "async def ")):
                in_function = True
                function_indent = len(line) - len(stripped_line)
            elif (
                in_function
                and line
                and (len(line) - len(stripped_line) <= function_indent)
                and (not stripped_line.startswith(("@", "#")))
            ):
                in_function = False
                function_indent = 0
            if not line:
                if i > 0 and cleaned_lines and (not cleaned_lines[-1]):
                    continue
                if in_function:
                    next_line_idx = i + 1
                    if next_line_idx < len(lines):
                        next_line = lines[next_line_idx].strip()
                        if not (
                            next_line.startswith(
                                ("return", "class ", "def ", "async def ", "@")
                            )
                            or next_line in ("pass", "break", "continue", "raise")
                            or (
                                next_line.startswith("#")
                                and any(
                                    pattern in next_line
                                    for pattern in (
                                        "type:",
                                        "noqa",
                                        "nosec",
                                        "pragma:",
                                        "pylint:",
                                        "mypy:",
                                    )
                                )
                            )
                        ):
                            continue
            cleaned_lines.append(line)
        while cleaned_lines and (not cleaned_lines[-1]):
            cleaned_lines.pop()
        return "\n".join(cleaned_lines)

    def reformat_code(self, code: str) -> str:
        from crackerjack.errors import handle_error

        try:
            import tempfile

            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w+", delete=False
            ) as temp:
                temp_path = Path(temp.name)
                temp_path.write_text(code)
            try:
                result = subprocess.run(
                    ["ruff", "format", str(temp_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    formatted_code = temp_path.read_text()
                else:
                    self.console.print(
                        f"[yellow]Ruff formatting failed: {result.stderr}[/yellow]"
                    )
                    handle_error(
                        ExecutionError(
                            message="Code formatting failed",
                            error_code=ErrorCode.FORMATTING_ERROR,
                            details=result.stderr,
                            recovery="Check Ruff configuration and formatting rules",
                        ),
                        console=self.console,
                    )
                    formatted_code = code
            except Exception as e:
                self.console.print(f"[red]Error running Ruff: {e}[/red]")
                handle_error(
                    ExecutionError(
                        message="Error running Ruff",
                        error_code=ErrorCode.FORMATTING_ERROR,
                        details=str(e),
                        recovery="Verify Ruff is installed and configured correctly",
                    ),
                    console=self.console,
                )
                formatted_code = code
            finally:
                with suppress(FileNotFoundError):
                    temp_path.unlink()
            return formatted_code
        except Exception as e:
            self.console.print(f"[red]Error during reformatting: {e}[/red]")
            handle_error(
                ExecutionError(
                    message="Error during reformatting",
                    error_code=ErrorCode.FORMATTING_ERROR,
                    details=str(e),
                    recovery="Check file permissions and disk space",
                ),
                console=self.console,
            )
            return code


class ConfigManager(BaseModel, arbitrary_types_allowed=True):
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


class ProjectManager(BaseModel, arbitrary_types_allowed=True):
    our_path: Path
    pkg_path: Path
    pkg_dir: Path | None = None
    pkg_name: str = "crackerjack"
    console: Console
    code_cleaner: CodeCleaner
    config_manager: ConfigManager
    dry_run: bool = False

    def run_interactive(self, hook: str) -> None:
        success: bool = False
        while not success:
            fail = self.execute_command(
                ["pre-commit", "run", hook.lower(), "--all-files"]
            )
            if fail.returncode > 0:
                retry = input(f"\n\n{hook.title()} failed. Retry? (y/N): ")
                self.console.print()
                if retry.strip().lower() == "y":
                    continue
                raise SystemExit(1)
            success = True

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
        self.console.print("\nRunning pre-commit hooks...\n")
        check_all = self.execute_command(["pre-commit", "run", "--all-files"])
        if check_all.returncode > 0:
            check_all = self.execute_command(["pre-commit", "run", "--all-files"])
            if check_all.returncode > 0:
                self.console.print("\n\nPre-commit failed. Please fix errors.\n")
                raise SystemExit(1)

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(f"[yellow]Would run: {' '.join(cmd)}[/yellow]")
            return CompletedProcess(cmd, 0, "", "")
        return execute(cmd, **kwargs)


class Crackerjack(BaseModel, arbitrary_types_allowed=True):
    our_path: Path = Path(__file__).parent
    pkg_path: Path = Path(Path.cwd())
    pkg_dir: Path | None = None
    pkg_name: str = "crackerjack"
    python_version: str = default_python_version
    console: Console = Console(force_terminal=True)
    dry_run: bool = False
    code_cleaner: CodeCleaner | None = None
    config_manager: ConfigManager | None = None
    project_manager: ProjectManager | None = None

    def __init__(self, **data: t.Any) -> None:
        super().__init__(**data)
        self.code_cleaner = CodeCleaner(console=self.console)
        self.config_manager = ConfigManager(
            our_path=self.our_path,
            pkg_path=self.pkg_path,
            pkg_name=self.pkg_name,
            console=self.console,
            python_version=self.python_version,
            dry_run=self.dry_run,
        )
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

    def _update_project(self, options: t.Any) -> None:
        if not options.no_config_updates:
            self.project_manager.update_pkg_configs()
            result: CompletedProcess[str] = self.execute_command(
                ["pdm", "install"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.console.print("PDM installed: ✅\n")
                self.execute_command(["pdm", "lock"])
                self.console.print("Lock file updated: ✅\n")
            else:
                self.console.print(
                    "\n\n❌ PDM installation failed. Is PDM is installed? Run `pipx install pdm` and try again.\n\n"
                )

    def _update_precommit(self, options: t.Any) -> None:
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            self.execute_command(["pre-commit", "autoupdate"])

    def _run_interactive_hooks(self, options: t.Any) -> None:
        if options.interactive:
            for hook in interactive_hooks:
                self.project_manager.run_interactive(hook)

    def _clean_project(self, options: t.Any) -> None:
        if options.clean:
            if self.pkg_dir:
                self.code_cleaner.clean_files(self.pkg_dir)
            if self.pkg_path.stem == "crackerjack":
                tests_dir = self.pkg_path / "tests"
                if tests_dir.exists() and tests_dir.is_dir():
                    self.console.print("\nCleaning tests directory...\n")
                    self.code_cleaner.clean_files(tests_dir)

    def _prepare_pytest_command(self, options: OptionsProtocol) -> list[str]:
        test = ["pytest"]
        project_size = self._detect_project_size()
        if options.test_timeout > 0:
            test_timeout = options.test_timeout
        else:
            test_timeout = (
                300
                if project_size == "large"
                else 120
                if project_size == "medium"
                else 60
            )
        test.extend(
            [
                "--capture=fd",
                "--tb=short",
                "--no-header",
                "--disable-warnings",
                "--durations=0",
                f"--timeout={test_timeout}",
            ]
        )
        if options.benchmark or options.benchmark_regression:
            if options.benchmark:
                test.append("--benchmark")
            if options.benchmark_regression:
                test.extend(
                    [
                        "--benchmark-regression",
                        f"--benchmark-regression-threshold={options.benchmark_regression_threshold}",
                    ]
                )
        elif options.test_workers > 0:
            if options.test_workers == 1:
                test.append("-vs")
            else:
                test.extend(["-xvs", "-n", str(options.test_workers)])
        elif project_size == "large":
            test.extend(["-xvs", "-n", "2"])
        elif project_size == "medium":
            test.extend(["-xvs", "-n", "auto"])
        else:
            test.append("-xvs")
        return test

    def _detect_project_size(self) -> str:
        if self.pkg_name in ("acb", "fastblocks"):
            return "large"
        try:
            py_files = list(self.pkg_path.rglob("*.py"))
            test_files = list(self.pkg_path.rglob("test_*.py"))
            total_files = len(py_files)
            num_test_files = len(test_files)
            if total_files > 100 or num_test_files > 50:
                return "large"
            elif total_files > 50 or num_test_files > 20:
                return "medium"
            else:
                return "small"
        except Exception:
            return "medium"

    def _run_tests(self, options: t.Any) -> None:
        if options.test:
            self.console.print("\n\nRunning tests...\n")
            test_command = self._prepare_pytest_command(options)
            result = self.execute_command(test_command, capture_output=True, text=True)
            if result.stdout:
                self.console.print(result.stdout)
            if result.returncode > 0:
                if result.stderr:
                    self.console.print(result.stderr)
                self.console.print("\n\n❌ Tests failed. Please fix errors.\n")
                return
            self.console.print("\n\n✅ Tests passed successfully!\n")

    def _bump_version(self, options: OptionsProtocol) -> None:
        for option in (options.publish, options.bump):
            if option:
                self.execute_command(["pdm", "bump", option])
                break

    def _publish_project(self, options: OptionsProtocol) -> None:
        if options.publish:
            build = self.execute_command(
                ["pdm", "build"], capture_output=True, text=True
            )
            self.console.print(build.stdout)
            if build.returncode > 0:
                self.console.print(build.stderr)
                self.console.print("\n\nBuild failed. Please fix errors.\n")
                raise SystemExit(1)
            self.execute_command(["pdm", "publish", "--no-build"])

    def _commit_and_push(self, options: OptionsProtocol) -> None:
        if options.commit:
            commit_msg = input("\nCommit message: ")
            self.execute_command(
                ["git", "commit", "-m", commit_msg, "--no-verify", "--", "."]
            )
            self.execute_command(["git", "push", "origin", "main"])

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(f"[yellow]Would run: {' '.join(cmd)}[/yellow]")
            return CompletedProcess(cmd, 0, "", "")
        return execute(cmd, **kwargs)

    def process(self, options: OptionsProtocol) -> None:
        if options.all:
            options.clean = True
            options.test = True
            options.publish = options.all
            options.commit = True
        self._setup_package()
        self._update_project(options)
        self._update_precommit(options)
        self._run_interactive_hooks(options)
        self._clean_project(options)
        if not options.skip_hooks:
            self.project_manager.run_pre_commit()
        else:
            self.console.print("Skipping pre-commit hooks")
        self._run_tests(options)
        self._bump_version(options)
        self._publish_project(options)
        self._commit_and_push(options)
        self.console.print("\n🍺 Crackerjack complete!\n")


crackerjack_it = Crackerjack().process


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
