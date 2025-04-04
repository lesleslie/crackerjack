import io
import platform
import re
import subprocess
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
    publish: t.Any | None
    bump: t.Any | None
    all: t.Any | None


@dataclass
class CodeCleaner:
    console: Console

    def clean_files(self, pkg_dir: Path | None) -> None:
        if pkg_dir is None:
            return
        for file_path in pkg_dir.rglob("*.py"):
            if not str(file_path.parent).startswith("__"):
                self.clean_file(file_path)
        if pkg_dir.parent.joinpath("__pycache__").exists():
            pkg_dir.parent.joinpath("__pycache__").rmdir()

    def clean_file(self, file_path: Path) -> None:
        try:
            if file_path.resolve() == Path(__file__).resolve():
                self.console.print(f"Skipping cleaning of {file_path} (self file).")
                return
        except Exception as e:
            self.console.print(f"Error comparing file paths: {e}")
        try:
            code = file_path.read_text()
            code = self.remove_docstrings(code)
            code = self.remove_line_comments(code)
            code = self.remove_extra_whitespace(code)
            code = self.reformat_code(code)
            file_path.write_text(code)  # type: ignore
            self.console.print(f"Cleaned: {file_path}")
        except Exception as e:
            self.console.print(f"Error cleaning {file_path}: {e}")

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
                    self.console.print(f"Ruff formatting failed: {result.stderr}")
                    formatted_code = code
            except Exception as e:
                self.console.print(f"Error running Ruff: {e}")
                formatted_code = code
            finally:
                with suppress(FileNotFoundError):
                    temp_path.unlink()
            return formatted_code
        except Exception as e:
            self.console.print(f"Error during reformatting: {e}")
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
                        if isinstance(y, (str, list)) and "crackerjack" in str(y)
                    }.items():
                        settings[setting][k] = v
                elif isinstance(value, (str, list)) and "crackerjack" in str(value):
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
        if not options.no_config_updates:
            self.project_manager.update_pkg_configs()
            result: CompletedProcess[str] = self.execute_command(
                ["pdm", "install"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.console.print("PDM installed: ✅\n")
            else:
                self.console.print(
                    "\n\n❌ PDM installation failed. Is PDM is installed? Run `pipx install pdm` and try again.\n\n"
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
            tests_dir = self.pkg_path / "tests"
            if tests_dir.exists() and tests_dir.is_dir():
                self.console.print("\nCleaning tests directory...\n")
                self.code_cleaner.clean_files(tests_dir)

    def _run_tests(self, options: OptionsProtocol) -> None:
        if options.test:
            self.console.print("\n\nRunning tests...\n")
            test = ["pytest"]
            if options.verbose:
                test.append("-v")
            result = self.execute_command(test, capture_output=True, text=True)
            if result.stdout:
                self.console.print(result.stdout)
            if result.returncode > 0:
                if result.stderr:
                    self.console.print(result.stderr)
                self.console.print("\n\n❌ Tests failed. Please fix errors.\n")
                raise SystemExit(1)
            self.console.print("\n\n✅ Tests passed successfully!\n")

    def _bump_version(self, options: OptionsProtocol) -> None:
        for option in (options.publish, options.bump):
            if option:
                self.execute_command(["pdm", "bump", option])
                break

    def _publish_project(self, options: OptionsProtocol) -> None:
        if options.publish:
            if platform.system() == "Darwin":
                authorize = self.execute_command(
                    ["pdm", "self", "add", "keyring"], capture_output=True, text=True
                )
                if authorize.returncode > 0:
                    self.console.print(
                        "\n\nAuthorization failed. Please add your keyring credentials to PDM. Run `pdm self add keyring` and try again.\n\n"
                    )
                    raise SystemExit(1)
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
        self.project_manager.run_pre_commit()
        self._run_tests(options)
        self._bump_version(options)
        self._publish_project(options)
        self._commit_and_push(options)
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
