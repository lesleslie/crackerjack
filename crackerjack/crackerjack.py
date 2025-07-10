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

config_files = (
    ".gitignore",
    ".pre-commit-config.yaml",
    ".pre-commit-config-ai.yaml",
    ".libcst.codemod.yaml",
)
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
        from crackerjack.errors import ExecutionError, handle_error

        try:
            code = file_path.read_text(encoding="utf-8")
            original_code = code
            cleaning_failed = False
            try:
                code = self.remove_line_comments(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove line comments from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.remove_docstrings(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove docstrings from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.remove_extra_whitespace(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to remove extra whitespace from {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            try:
                code = self.reformat_code(code)
            except Exception as e:
                self.console.print(
                    f"[bold bright_yellow]⚠️  Warning: Failed to reformat {file_path}: {e}[/bold bright_yellow]"
                )
                code = original_code
                cleaning_failed = True
            file_path.write_text(code, encoding="utf-8")
            if cleaning_failed:
                self.console.print(
                    f"[bold yellow]⚡ Partially cleaned:[/bold yellow] [dim bright_white]{file_path}[/dim bright_white]"
                )
            else:
                self.console.print(
                    f"[bold green]✨ Cleaned:[/bold green] [dim bright_white]{file_path}[/dim bright_white]"
                )
        except PermissionError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Permission denied)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Permission denied while cleaning {file_path}",
                    error_code=ErrorCode.PERMISSION_ERROR,
                    details=str(e),
                    recovery=f"Check file permissions for {file_path} and ensure you have write access",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except OSError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (File system error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"File system error while cleaning {file_path}",
                    error_code=ErrorCode.FILE_WRITE_ERROR,
                    details=str(e),
                    recovery=f"Check that {file_path} exists and is not being used by another process",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except UnicodeDecodeError as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Encoding error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Encoding error while reading {file_path}",
                    error_code=ErrorCode.FILE_READ_ERROR,
                    details=str(e),
                    recovery=f"File {file_path} contains non-UTF-8 characters. Please check the file encoding.",
                ),
                console=self.console,
                exit_on_error=False,
            )
        except Exception as e:
            self.console.print(
                f"[red]Failed to clean: {file_path} (Unexpected error)[/red]"
            )
            handle_error(
                ExecutionError(
                    message=f"Unexpected error while cleaning {file_path}",
                    error_code=ErrorCode.UNEXPECTED_ERROR,
                    details=str(e),
                    recovery="This is an unexpected error. Please report this issue with the file content if possible.",
                ),
                console=self.console,
                exit_on_error=False,
            )

    def _initialize_docstring_state(self) -> dict[str, t.Any]:
        return {
            "in_docstring": False,
            "delimiter": None,
            "waiting": False,
            "function_indent": 0,
            "removed_docstring": False,
            "in_multiline_def": False,
        }

    def _handle_function_definition(
        self, line: str, stripped: str, state: dict[str, t.Any]
    ) -> bool:
        if self._is_function_or_class_definition(stripped):
            state["waiting"] = True
            state["function_indent"] = len(line) - len(line.lstrip())
            state["removed_docstring"] = False
            state["in_multiline_def"] = not stripped.endswith(":")
            return True
        return False

    def _handle_multiline_definition(
        self, line: str, stripped: str, state: dict[str, t.Any]
    ) -> bool:
        if state["in_multiline_def"]:
            if stripped.endswith(":"):
                state["in_multiline_def"] = False
            return True
        return False

    def _handle_waiting_docstring(
        self, lines: list[str], i: int, stripped: str, state: dict[str, t.Any]
    ) -> tuple[bool, str | None]:
        if state["waiting"] and stripped:
            if self._handle_docstring_start(stripped, state):
                pass_line = None
                if not state["in_docstring"]:
                    function_indent: int = state["function_indent"]
                    if self._needs_pass_statement(lines, i + 1, function_indent):
                        pass_line = " " * (function_indent + 4) + "pass"
                state["removed_docstring"] = True
                return True, pass_line
            else:
                state["waiting"] = False
        return False, None

    def _handle_docstring_content(
        self, lines: list[str], i: int, stripped: str, state: dict[str, t.Any]
    ) -> tuple[bool, str | None]:
        if state["in_docstring"]:
            if self._handle_docstring_end(stripped, state):
                pass_line = None
                function_indent: int = state["function_indent"]
                if self._needs_pass_statement(lines, i + 1, function_indent):
                    pass_line = " " * (function_indent + 4) + "pass"
                state["removed_docstring"] = False
                return True, pass_line
            else:
                return True, None
        return False, None

    def _process_line(
        self, lines: list[str], i: int, line: str, state: dict[str, t.Any]
    ) -> tuple[bool, str | None]:
        stripped = line.strip()
        if self._handle_function_definition(line, stripped, state):
            return True, line
        if self._handle_multiline_definition(line, stripped, state):
            return True, line
        handled, pass_line = self._handle_waiting_docstring(lines, i, stripped, state)
        if handled:
            return True, pass_line
        handled, pass_line = self._handle_docstring_content(lines, i, stripped, state)
        if handled:
            return True, pass_line
        if state["removed_docstring"] and stripped:
            state["removed_docstring"] = False
        return False, line

    def remove_docstrings(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        docstring_state = self._initialize_docstring_state()
        for i, line in enumerate(lines):
            handled, result_line = self._process_line(lines, i, line, docstring_state)
            if handled:
                if result_line is not None:
                    cleaned_lines.append(result_line)
            else:
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def _is_function_or_class_definition(self, stripped_line: str) -> bool:
        return stripped_line.startswith(("def ", "class ", "async def "))

    def _handle_docstring_start(self, stripped: str, state: dict[str, t.Any]) -> bool:
        if not stripped.startswith(('"""', "'''", '"', "'")):
            return False
        if stripped.startswith(('"""', "'''")):
            delimiter = stripped[:3]
        else:
            delimiter = stripped[0]
        state["delimiter"] = delimiter
        if self._is_single_line_docstring(stripped, delimiter):
            state["waiting"] = False
            return True
        else:
            state["in_docstring"] = True
            state["waiting"] = False
            return True

    def _is_single_line_docstring(self, stripped: str, delimiter: str) -> bool:
        return stripped.endswith(delimiter) and len(stripped) > len(delimiter)

    def _handle_docstring_end(self, stripped: str, state: dict[str, t.Any]) -> bool:
        if state["delimiter"] and stripped.endswith(state["delimiter"]):
            state["in_docstring"] = False
            state["delimiter"] = None
            return True
        return False

    def _needs_pass_statement(
        self, lines: list[str], start_index: int, function_indent: int
    ) -> bool:
        for i in range(start_index, len(lines)):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                continue
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= function_indent:
                return True
            if line_indent > function_indent:
                return False
        return True

    def remove_line_comments(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        for line in lines:
            if not line.strip():
                cleaned_lines.append(line)
                continue
            cleaned_line = self._process_line_for_comments(line)
            if cleaned_line or not line.strip():
                cleaned_lines.append(cleaned_line or line)
        return "\n".join(cleaned_lines)

    def _process_line_for_comments(self, line: str) -> str:
        result = []
        string_state = {"in_string": None}
        for i, char in enumerate(line):
            if self._handle_string_character(char, i, line, string_state, result):
                continue
            elif self._handle_comment_character(char, i, line, string_state, result):
                break
            else:
                result.append(char)
        return "".join(result).rstrip()

    def _handle_string_character(
        self,
        char: str,
        index: int,
        line: str,
        string_state: dict[str, t.Any],
        result: list[str],
    ) -> bool:
        if char not in ("'", '"'):
            return False
        if index > 0 and line[index - 1] == "\\":
            return False
        if string_state["in_string"] is None:
            string_state["in_string"] = char
        elif string_state["in_string"] == char:
            string_state["in_string"] = None
        result.append(char)
        return True

    def _handle_comment_character(
        self,
        char: str,
        index: int,
        line: str,
        string_state: dict[str, t.Any],
        result: list[str],
    ) -> bool:
        if char != "#" or string_state["in_string"] is not None:
            return False
        comment = line[index:].strip()
        if self._is_special_comment_line(comment):
            result.append(line[index:])
        return True

    def _is_special_comment_line(self, comment: str) -> bool:
        special_comment_pattern = (
            r"^#\s*(?:type:\s*ignore(?:\[.*?\])?|noqa|nosec|pragma:\s*no\s*cover"
            r"|pylint:\s*disable|mypy:\s*ignore)"
        )
        return bool(re.match(special_comment_pattern, comment))

    def remove_extra_whitespace(self, code: str) -> str:
        lines = code.split("\n")
        cleaned_lines = []
        function_tracker = {"in_function": False, "function_indent": 0}
        import_tracker = {"in_imports": False, "last_import_type": None}
        for i, line in enumerate(lines):
            line = line.rstrip()
            stripped_line = line.lstrip()
            self._update_function_state(line, stripped_line, function_tracker)
            self._update_import_state(line, stripped_line, import_tracker)
            if not line:
                if self._should_skip_empty_line(
                    i, lines, cleaned_lines, function_tracker, import_tracker
                ):
                    continue
            cleaned_lines.append(line)
        return "\n".join(self._remove_trailing_empty_lines(cleaned_lines))

    def _update_function_state(
        self, line: str, stripped_line: str, function_tracker: dict[str, t.Any]
    ) -> None:
        if stripped_line.startswith(("def ", "async def ")):
            function_tracker["in_function"] = True
            function_tracker["function_indent"] = len(line) - len(stripped_line)
        elif self._is_function_end(line, stripped_line, function_tracker):
            function_tracker["in_function"] = False
            function_tracker["function_indent"] = 0

    def _update_import_state(
        self, line: str, stripped_line: str, import_tracker: dict[str, t.Any]
    ) -> None:
        if stripped_line.startswith(("import ", "from ")):
            import_tracker["in_imports"] = True
            if self._is_stdlib_import(stripped_line):
                current_type = "stdlib"
            elif self._is_local_import(stripped_line):
                current_type = "local"
            else:
                current_type = "third_party"
            import_tracker["last_import_type"] = current_type
        elif stripped_line and not stripped_line.startswith("#"):
            import_tracker["in_imports"] = False
            import_tracker["last_import_type"] = None

    def _is_stdlib_import(self, stripped_line: str) -> bool:
        try:
            if stripped_line.startswith("from "):
                module = stripped_line.split()[1].split(".")[0]
            else:
                module = stripped_line.split()[1].split(".")[0]
        except IndexError:
            return False
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "datetime",
            "time",
            "pathlib",
            "typing",
            "collections",
            "itertools",
            "functools",
            "operator",
            "math",
            "random",
            "uuid",
            "urllib",
            "http",
            "html",
            "xml",
            "email",
            "csv",
            "sqlite3",
            "subprocess",
            "threading",
            "multiprocessing",
            "asyncio",
            "contextlib",
            "dataclasses",
            "enum",
            "abc",
            "io",
            "tempfile",
            "shutil",
            "glob",
            "pickle",
            "copy",
            "heapq",
            "bisect",
            "array",
            "struct",
            "zlib",
            "hashlib",
            "hmac",
            "secrets",
            "base64",
            "binascii",
            "codecs",
            "locale",
            "platform",
            "socket",
            "ssl",
            "ipaddress",
            "logging",
            "warnings",
            "inspect",
            "ast",
            "dis",
            "tokenize",
            "keyword",
            "linecache",
            "traceback",
            "weakref",
            "gc",
            "ctypes",
            "unittest",
            "doctest",
            "pdb",
            "profile",
            "cProfile",
            "timeit",
            "trace",
            "calendar",
            "decimal",
            "fractions",
            "statistics",
            "tomllib",
        }
        return module in stdlib_modules

    def _is_local_import(self, stripped_line: str) -> bool:
        return stripped_line.startswith("from .") or " . " in stripped_line

    def _is_function_end(
        self, line: str, stripped_line: str, function_tracker: dict[str, t.Any]
    ) -> bool:
        return (
            function_tracker["in_function"]
            and bool(line)
            and (len(line) - len(stripped_line) <= function_tracker["function_indent"])
            and (not stripped_line.startswith(("@", "#")))
        )

    def _should_skip_empty_line(
        self,
        line_idx: int,
        lines: list[str],
        cleaned_lines: list[str],
        function_tracker: dict[str, t.Any],
        import_tracker: dict[str, t.Any],
    ) -> bool:
        if line_idx > 0 and cleaned_lines and (not cleaned_lines[-1]):
            return True

        if self._is_import_section_separator(line_idx, lines, import_tracker):
            return False

        if function_tracker["in_function"]:
            return self._should_skip_function_empty_line(line_idx, lines)
        return False

    def _is_import_section_separator(
        self, line_idx: int, lines: list[str], import_tracker: dict[str, t.Any]
    ) -> bool:
        if not import_tracker["in_imports"]:
            return False

        next_line_idx = line_idx + 1
        while next_line_idx < len(lines) and not lines[next_line_idx].strip():
            next_line_idx += 1

        if next_line_idx >= len(lines):
            return False

        next_line = lines[next_line_idx].strip()
        if not next_line.startswith(("import ", "from ")):
            return False

        if self._is_stdlib_import(next_line):
            next_type = "stdlib"
        elif self._is_local_import(next_line):
            next_type = "local"
        else:
            next_type = "third_party"

        return import_tracker["last_import_type"] != next_type

    def _should_skip_function_empty_line(self, line_idx: int, lines: list[str]) -> bool:
        next_line_idx = line_idx + 1
        if next_line_idx >= len(lines):
            return False
        next_line = lines[next_line_idx].strip()
        return not self._is_significant_next_line(next_line)

    def _is_significant_next_line(self, next_line: str) -> bool:
        if next_line.startswith(("return", "class ", "def ", "async def ", "@")):
            return True
        if next_line in ("pass", "break", "continue", "raise"):
            return True
        return self._is_special_comment(next_line)

    def _is_special_comment(self, line: str) -> bool:
        if not line.startswith("#"):
            return False
        special_patterns = ("type:", "noqa", "nosec", "pragma:", "pylint:", "mypy:")
        return any(pattern in line for pattern in special_patterns)

    def _remove_trailing_empty_lines(self, lines: list[str]) -> list[str]:
        while lines and (not lines[-1]):
            lines.pop()
        return lines

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
                        f"[bold bright_yellow]⚠️  Ruff formatting failed: {result.stderr}[/bold bright_yellow]"
                    )
                    handle_error(
                        ExecutionError(
                            message="Code formatting failed",
                            error_code=ErrorCode.FORMATTING_ERROR,
                            details=result.stderr,
                            recovery="Check Ruff configuration and formatting rules",
                        ),
                        console=self.console,
                        exit_on_error=False,
                    )
                    formatted_code = code
            except Exception as e:
                self.console.print(
                    f"[bold bright_red]❌ Error running Ruff: {e}[/bold bright_red]"
                )
                handle_error(
                    ExecutionError(
                        message="Error running Ruff",
                        error_code=ErrorCode.FORMATTING_ERROR,
                        details=str(e),
                        recovery="Verify Ruff is installed and configured correctly",
                    ),
                    console=self.console,
                    exit_on_error=False,
                )
                formatted_code = code
            finally:
                with suppress(FileNotFoundError):
                    temp_path.unlink()
            return formatted_code
        except Exception as e:
            self.console.print(
                f"[bold bright_red]❌ Error during reformatting: {e}[/bold bright_red]"
            )
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
            if tool not in pkg_toml_config["tool"]:
                pkg_toml_config["tool"][tool] = {}
            pkg_tool_config = pkg_toml_config["tool"][tool]
            self._merge_tool_config(settings, pkg_tool_config, tool)

    def _merge_tool_config(
        self, our_config: dict[str, t.Any], pkg_config: dict[str, t.Any], tool: str
    ) -> None:
        for setting, value in our_config.items():
            if isinstance(value, dict):
                self._merge_nested_config(setting, value, pkg_config)
            else:
                self._merge_direct_config(setting, value, pkg_config)

    def _merge_nested_config(
        self, setting: str, value: dict[str, t.Any], pkg_config: dict[str, t.Any]
    ) -> None:
        if setting not in pkg_config:
            pkg_config[setting] = {}
        elif not isinstance(pkg_config[setting], dict):
            pkg_config[setting] = {}
        self._merge_tool_config(value, pkg_config[setting], "")
        for k, v in value.items():
            self._merge_nested_value(k, v, pkg_config[setting])

    def _merge_nested_value(
        self, key: str, value: t.Any, nested_config: dict[str, t.Any]
    ) -> None:
        if isinstance(value, str | list) and "crackerjack" in str(value):
            nested_config[key] = self.swap_package_name(value)
        elif self._is_mergeable_list(key, value):
            existing = nested_config.get(key, [])
            if isinstance(existing, list) and isinstance(value, list):
                nested_config[key] = list(set(existing + value))
            else:
                nested_config[key] = value
        elif key not in nested_config:
            nested_config[key] = value

    def _merge_direct_config(
        self, setting: str, value: t.Any, pkg_config: dict[str, t.Any]
    ) -> None:
        if isinstance(value, str | list) and "crackerjack" in str(value):
            pkg_config[setting] = self.swap_package_name(value)
        elif self._is_mergeable_list(setting, value):
            existing = pkg_config.get(setting, [])
            if isinstance(existing, list) and isinstance(value, list):
                pkg_config[setting] = list(set(existing + value))
            else:
                pkg_config[setting] = value
        elif setting not in pkg_config:
            pkg_config[setting] = value

    def _is_mergeable_list(self, key: str, value: t.Any) -> bool:
        return key in (
            "exclude-deps",
            "exclude",
            "excluded",
            "skips",
            "ignore",
        ) and isinstance(value, list)

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
            self.console.print(
                f"[bold bright_black]→ {' '.join(cmd)}[/bold bright_black]"
            )
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
    options: t.Any = None

    def update_pkg_configs(self) -> None:
        self.config_manager.copy_configs()
        installed_pkgs = self.execute_command(
            ["pdm", "list", "--freeze"], capture_output=True, text=True
        ).stdout.splitlines()
        if not len([pkg for pkg in installed_pkgs if "pre-commit" in pkg]):
            self.console.print("\n" + "─" * 60)
            self.console.print(
                "[bold bright_blue]⚡ INIT[/bold bright_blue] [bold bright_white]First-time project setup[/bold bright_white]"
            )
            self.console.print("─" * 60 + "\n")
            self.execute_command(["pdm", "self", "add", "keyring"])
            self.execute_command(["pdm", "config", "python.use_uv", "true"])
            self.execute_command(["git", "init"])
            self.execute_command(["git", "branch", "-m", "main"])
            self.execute_command(["git", "add", "pyproject.toml"])
            self.execute_command(["git", "add", "pdm.lock"])
            install_cmd = ["pre-commit", "install"]
            if hasattr(self, "options") and getattr(self.options, "ai_agent", False):
                install_cmd.extend(["-c", ".pre-commit-config-ai.yaml"])
            self.execute_command(install_cmd)
            self.execute_command(["git", "config", "advice.addIgnoredFile", "false"])
        self.config_manager.update_pyproject_configs()

    def run_pre_commit(self) -> None:
        self.console.print("\n" + "-" * 60)
        self.console.print(
            "[bold bright_cyan]🔍 HOOKS[/bold bright_cyan] [bold bright_white]Running code quality checks[/bold bright_white]"
        )
        self.console.print("-" * 60 + "\n")
        cmd = ["pre-commit", "run", "--all-files"]
        if hasattr(self, "options") and getattr(self.options, "ai_agent", False):
            cmd.extend(["-c", ".pre-commit-config-ai.yaml"])
        check_all = self.execute_command(cmd)
        if check_all.returncode > 0:
            self.execute_command(["pdm", "lock"])
            self.console.print("\n[bold green]✓ Dependencies locked[/bold green]\n")
            check_all = self.execute_command(cmd)
            if check_all.returncode > 0:
                self.console.print(
                    "\n\n[bold red]❌ Pre-commit failed. Please fix errors.[/bold red]\n"
                )
                raise SystemExit(1)

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(
                f"[bold bright_black]→ {' '.join(cmd)}[/bold bright_black]"
            )
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
        self.console.print("\n" + "-" * 60)
        self.console.print(
            "[bold bright_magenta]🛠️  SETUP[/bold bright_magenta] [bold bright_white]Initializing project structure[/bold bright_white]"
        )
        self.console.print("-" * 60 + "\n")
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
                self.console.print(
                    "[bold green]✓ Dependencies installed[/bold green]\n"
                )
            else:
                self.console.print(
                    "\n\n[bold red]❌ PDM installation failed. Is PDM installed? Run `pipx install pdm` and try again.[/bold red]\n\n"
                )

    def _update_precommit(self, options: t.Any) -> None:
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            update_cmd = ["pre-commit", "autoupdate"]
            if options.ai_agent:
                update_cmd.extend(["-c", ".pre-commit-config-ai.yaml"])
            self.execute_command(update_cmd)

    def _clean_project(self, options: t.Any) -> None:
        if options.clean:
            if self.pkg_dir:
                self.console.print("\n" + "-" * 60)
                self.console.print(
                    "[bold bright_blue]🧹 CLEAN[/bold bright_blue] [bold bright_white]Removing docstrings and comments[/bold bright_white]"
                )
                self.console.print("-" * 60 + "\n")
                self.code_cleaner.clean_files(self.pkg_dir)
            if self.pkg_path.stem == "crackerjack":
                tests_dir = self.pkg_path / "tests"
                if tests_dir.exists() and tests_dir.is_dir():
                    self.console.print("\n" + "─" * 60)
                    self.console.print(
                        "[bold bright_blue]🧪 TESTS[/bold bright_blue] [bold bright_white]Cleaning test files[/bold bright_white]"
                    )
                    self.console.print("─" * 60 + "\n")
                    self.code_cleaner.clean_files(tests_dir)

    def _get_test_timeout(self, options: OptionsProtocol, project_size: str) -> int:
        if options.test_timeout > 0:
            return options.test_timeout
        return (
            360 if project_size == "large" else 240 if project_size == "medium" else 120
        )

    def _add_ai_agent_flags(
        self, test: list[str], options: OptionsProtocol, test_timeout: int
    ) -> None:
        test.extend(
            [
                "--junitxml=test-results.xml",
                "--cov-report=json:coverage.json",
                "--tb=short",
                "--no-header",
                "--quiet",
                f"--timeout={test_timeout}",
            ]
        )
        if options.benchmark or options.benchmark_regression:
            test.append("--benchmark-json=benchmark.json")

    def _add_standard_flags(self, test: list[str], test_timeout: int) -> None:
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

    def _add_benchmark_flags(self, test: list[str], options: OptionsProtocol) -> None:
        if options.benchmark:
            test.extend(["--benchmark", "--benchmark-autosave"])
        if options.benchmark_regression:
            test.extend(
                [
                    "--benchmark-regression",
                    f"--benchmark-regression-threshold={options.benchmark_regression_threshold}",
                ]
            )

    def _add_worker_flags(
        self, test: list[str], options: OptionsProtocol, project_size: str
    ) -> None:
        if options.test_workers > 0:
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

    def _prepare_pytest_command(self, options: OptionsProtocol) -> list[str]:
        test = ["pytest"]
        project_size = self._detect_project_size()
        test_timeout = self._get_test_timeout(options, project_size)
        if getattr(options, "ai_agent", False):
            self._add_ai_agent_flags(test, options, test_timeout)
        else:
            self._add_standard_flags(test, test_timeout)
        if options.benchmark or options.benchmark_regression:
            self._add_benchmark_flags(test, options)
        else:
            self._add_worker_flags(test, options, project_size)
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
        except (OSError, PermissionError):
            return "medium"

    def _print_ai_agent_files(self, options: t.Any) -> None:
        if getattr(options, "ai_agent", False):
            self.console.print(
                "[bold bright_black]→ Structured test results: test-results.xml[/bold bright_black]"
            )
            self.console.print(
                "[bold bright_black]→ Coverage report: coverage.json[/bold bright_black]"
            )
            if options.benchmark or options.benchmark_regression:
                self.console.print(
                    "[bold bright_black]→ Benchmark results: benchmark.json[/bold bright_black]"
                )

    def _handle_test_failure(self, result: t.Any, options: t.Any) -> None:
        if result.stderr:
            self.console.print(result.stderr)
        self.console.print(
            "\n\n[bold bright_red]❌ Tests failed. Please fix errors.[/bold bright_red]\n"
        )
        self._print_ai_agent_files(options)
        raise SystemExit(1)

    def _handle_test_success(self, options: t.Any) -> None:
        self.console.print(
            "\n\n[bold bright_green]✅ Tests passed successfully![/bold bright_green]\n"
        )
        self._print_ai_agent_files(options)

    def _run_tests(self, options: t.Any) -> None:
        if not options.test:
            return
        self.console.print("\n" + "-" * 60)
        self.console.print(
            "[bold bright_green]🧪 TESTING[/bold bright_green] [bold bright_white]Executing test suite[/bold bright_white]"
        )
        self.console.print("-" * 60 + "\n")
        test_command = self._prepare_pytest_command(options)
        result = self.execute_command(test_command, capture_output=True, text=True)
        if result.stdout:
            self.console.print(result.stdout)
        if result.returncode > 0:
            self._handle_test_failure(result, options)
        else:
            self._handle_test_success(options)

    def _bump_version(self, options: OptionsProtocol) -> None:
        for option in (options.publish, options.bump):
            if option:
                self.console.print("\n" + "-" * 60)
                self.console.print(
                    f"[bold bright_magenta]📦 VERSION[/bold bright_magenta] [bold bright_white]Bumping {option} version[/bold bright_white]"
                )
                self.console.print("-" * 60 + "\n")
                if str(option) in ("minor", "major"):
                    from rich.prompt import Confirm

                    if not Confirm.ask(
                        f"Are you sure you want to bump the {option} version?",
                        default=False,
                    ):
                        self.console.print(
                            f"[bold yellow]⏭️  Skipping {option} version bump[/bold yellow]"
                        )
                        return
                self.execute_command(["pdm", "bump", option])
                break

    def _publish_project(self, options: OptionsProtocol) -> None:
        if options.publish:
            self.console.print("\n" + "-" * 60)
            self.console.print(
                "[bold bright_cyan]🚀 PUBLISH[/bold bright_cyan] [bold bright_white]Building and publishing package[/bold bright_white]"
            )
            self.console.print("-" * 60 + "\n")
            build = self.execute_command(
                ["pdm", "build"], capture_output=True, text=True
            )
            self.console.print(build.stdout)
            if build.returncode > 0:
                self.console.print(build.stderr)
                self.console.print(
                    "[bold bright_red]❌ Build failed. Please fix errors.[/bold bright_red]"
                )
                raise SystemExit(1)
            self.execute_command(["pdm", "publish", "--no-build"])

    def _commit_and_push(self, options: OptionsProtocol) -> None:
        if options.commit:
            self.console.print("\n" + "-" * 60)
            self.console.print(
                "[bold bright_white]📝 COMMIT[/bold bright_white] [bold bright_white]Saving changes to git[/bold bright_white]"
            )
            self.console.print("-" * 60 + "\n")
            commit_msg = input("\nCommit message: ")
            self.execute_command(
                ["git", "commit", "-m", commit_msg, "--no-verify", "--", "."]
            )
            self.execute_command(["git", "push", "origin", "main"])

    def execute_command(
        self, cmd: list[str], **kwargs: t.Any
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            self.console.print(
                f"[bold bright_black]→ {' '.join(cmd)}[/bold bright_black]"
            )
            return CompletedProcess(cmd, 0, "", "")
        return execute(cmd, **kwargs)

    def process(self, options: OptionsProtocol) -> None:
        self.console.print("\n" + "-" * 60)
        self.console.print(
            "[bold bright_cyan]⚒️ CRACKERJACKING[/bold bright_cyan] [bold bright_white]Starting workflow execution[/bold bright_white]"
        )
        self.console.print("-" * 60 + "\n")
        if options.all:
            options.clean = True
            options.test = True
            options.publish = options.all
            options.commit = True
        self._setup_package()
        self._update_project(options)
        self._update_precommit(options)
        self._clean_project(options)
        self.project_manager.options = options
        if not options.skip_hooks:
            self.project_manager.run_pre_commit()
        else:
            self.console.print(
                "\n[bold bright_yellow]⏭️  Skipping pre-commit hooks...[/bold bright_yellow]\n"
            )
        self._run_tests(options)
        self._bump_version(options)
        self._publish_project(options)
        self._commit_and_push(options)
        self.console.print("\n" + "-" * 60)
        self.console.print(
            "[bold bright_green]✨ CRACKERJACK COMPLETE[/bold bright_green] [bold bright_white]Workflow completed successfully![/bold bright_white]"
        )
        self.console.print("-" * 60 + "\n")


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
