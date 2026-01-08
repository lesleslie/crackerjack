import os
from pathlib import Path

import psutil
from rich.console import Console

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.models.protocols import OptionsProtocol


def parse_pytest_addopts(addopts: str | list) -> list[str]:
    """Parse pytest addopts into a list of arguments.

    Args:
        addopts: Either a string or list of pytest addopts

    Returns:
        List of individual pytest arguments
    """
    if isinstance(addopts, list):
        return addopts

    import shlex

    try:
        return shlex.split(addopts)
    except Exception:
        return addopts.split()

class TestCommandBuilder:
    def __init__(
        self,
        pkg_path: Path | None = None,
        console: Console | None = None,
        settings: CrackerjackSettings | None = None,
    ) -> None:

        resolved_pkg_path = pkg_path
        if resolved_pkg_path is None:
            resolved_pkg_path = Path.cwd()

        try:
            self.pkg_path = Path(str(resolved_pkg_path))
        except Exception:
            self.pkg_path = Path(resolved_pkg_path)

        if console is None:
            try:
                console = Console()
            except Exception:
                console = Console()

        if settings is None:
            settings = CrackerjackSettings()

        self.console = console
        self.settings = settings

    def build_command(self, options: OptionsProtocol) -> list[str]:
        cmd = ["uv", "run", "python", "-m", "pytest"]

        self._add_coverage_options(cmd, options)
        self._add_worker_options(cmd, options)
        self._add_benchmark_options(cmd, options)
        self._add_timeout_options(cmd, options)
        self._add_verbosity_options(cmd, options)
        self._add_test_path(cmd)

        return cmd

    def _handle_not_implemented_error(self, print_info: bool) -> int:
        if print_info and self.console:
            self.console.print(
                "[yellow]⚠️ CPU detection unavailable, using 2 workers[/yellow]"
            )
        return 2

    def _handle_general_error(self, print_info: bool, e: Exception) -> int:
        if print_info and self.console:
            self.console.print(
                f"[yellow]⚠️ Worker detection failed: {e}. Using 2 workers.[/yellow]"
            )
        return 2

    def get_optimal_workers(
        self, options: OptionsProtocol, print_info: bool = True
    ) -> int | str:
        try:

            if self._check_emergency_rollback(print_info):
                return 1


            explicit_result = self._check_explicit_workers(options, print_info)
            if explicit_result is not None:
                return explicit_result


            auto_result = self._check_auto_detection(options, print_info)
            if auto_result is not None:
                return auto_result


            fractional_result = self._check_fractional_workers(options, print_info)
            if fractional_result is not None:
                return fractional_result


            return 2

        except NotImplementedError:
            return self._handle_not_implemented_error(print_info)
        except Exception as e:
            return self._handle_general_error(print_info, e)

    def _check_emergency_rollback(self, print_info: bool) -> bool:
        if os.getenv("CRACKERJACK_DISABLE_AUTO_WORKERS") == "1":
            if print_info and self.console:
                self.console.print(
                    "[yellow]⚠️ Auto-detection disabled via environment variable[/yellow]"
                )
            return True
        return False

    def _check_explicit_workers(
        self, options: OptionsProtocol, print_info: bool
    ) -> int | None:
        if hasattr(options, "test_workers") and options.test_workers > 0:
            return options.test_workers
        return None

    def _check_auto_detection(
        self, options: OptionsProtocol, print_info: bool
    ) -> str | int | None:
        if hasattr(options, "test_workers") and options.test_workers == 0:

            if self.settings and self.settings.testing.auto_detect_workers:

                if print_info and self.console:
                    self.console.print(
                        "[cyan]🔧 Using pytest-xdist auto-detection for workers[/cyan]"
                    )
                return "auto"


            return 1
        return None

    def _check_fractional_workers(
        self, options: OptionsProtocol, print_info: bool
    ) -> int | None:
        if hasattr(options, "test_workers") and options.test_workers < 0:
            import multiprocessing

            cpu_count = multiprocessing.cpu_count()
            divisor = abs(options.test_workers)
            workers = max(1, cpu_count // divisor)


            workers = self._apply_memory_limit(workers)

            if print_info and self.console:
                self.console.print(
                    f"[cyan]🔧 Fractional workers: {cpu_count} cores ÷ {divisor} = {workers} workers[/cyan]"
                )

            return workers
        return None

    def _apply_memory_limit(self, workers: int) -> int:
        try:

            memory_per_worker = (
                self.settings.testing.memory_per_worker_gb if self.settings else 2.0
            )


            available_gb = psutil.virtual_memory().available / (1024**3)


            max_by_memory = max(1, int(available_gb / memory_per_worker))


            limited_workers = min(workers, max_by_memory)


            if limited_workers < workers and self.console:
                self.console.print(
                    f"[yellow]⚠️ Limited to {limited_workers} workers (available memory: {available_gb:.1f}GB)[/yellow]"
                )

            return limited_workers

        except Exception:

            return min(workers, 4)

    def get_test_timeout(self, options: OptionsProtocol) -> int:
        if hasattr(options, "test_timeout") and options.test_timeout:
            return options.test_timeout

        if hasattr(options, "benchmark") and options.benchmark:
            return 1800
        return 1800

    def _detect_package_name(self) -> str:

        pyproject_path = self.pkg_path / "pyproject.toml"
        if pyproject_path.exists():
            from contextlib import suppress

            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)
                    project_name = data.get("project", {}).get("name")
                    if project_name:

                        return project_name.replace("-", "_")


        for item in self.pkg_path.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith(".")
                and item.name not in ("tests", "docs", "build", "dist", "__pycache__")
                and (item / "__init__.py").exists()
            ):
                return item.name


        return "crackerjack"

    def _add_coverage_options(self, cmd: list[str], options: OptionsProtocol) -> None:

        package_name = self._detect_package_name()

        cmd.extend(
            [
                f"--cov={package_name}",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-report=json",
                "--cov-fail-under=0",
            ]
        )

    def _check_project_disabled_xdist(self) -> bool:
        """Check if project has disabled pytest-xdist in configuration.

        Reads pyproject.toml or pytest.ini to check if -p no:xdist is set in addopts.
        This respects project-specific configuration that may disable xdist for
        technical reasons (e.g., DuckDB locking, coverage issues).

        Returns:
            True if project has explicitly disabled xdist, False otherwise
        """
        try:
            pyproject_path = self.pkg_path / "pyproject.toml"

            if not pyproject_path.exists():
                return False

            addopts = self._load_pytest_addopts(pyproject_path)
            if addopts:
                return self._addopts_disables_xdist(addopts)

            return False

        except Exception:
            return False

    def _load_pytest_addopts(self, pyproject_path: Path) -> str | None:
        """Load pytest addopts from pyproject.toml.

        Args:
            pyproject_path: Path to pyproject.toml file

        Returns:
            Addopts string or None
        """
        import tomllib

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        # Check both [tool.pytest] and [tool.pytest.ini_options] formats
        pytest_config = data.get("tool", {}).get("pytest", {})

        # Try ini_options first (pytest.ini_options format)
        ini_options = pytest_config.get("ini_options", {})
        addopts = ini_options.get("addopts")

        # If not in ini_options, try direct pytest config format
        if addopts is None:
            addopts = pytest_config.get("addopts")

        return addopts

    def _addopts_disables_xdist(self, addopts: str) -> bool:
        """Check if addopts string disables xdist.

        Args:
            addopts: Addopts string from pytest config

        Returns:
            True if -p no:xdist is found
        """
        parsed_opts = parse_pytest_addopts(addopts)

        # Check for -p no:xdist in various forms
        if "-p" in parsed_opts:
            idx = parsed_opts.index("-p")
            if idx + 1 < len(parsed_opts) and parsed_opts[idx + 1] == "no:xdist":
                return True

        # Also check for compact form "-pno:xdist"
        return self._has_compact_no_xdist_flag(parsed_opts)

    def _has_compact_no_xdist_flag(self, parsed_opts: list[str]) -> bool:
        """Check for compact -pno:xdist flag in parsed options.

        Args:
            parsed_opts: List of parsed command-line options

        Returns:
            True if -pno:xdist or similar flag is found
        """
        for opt in parsed_opts:
            if opt.startswith("-p") and "no:xdist" in opt:
                return True
        return False

    def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add pytest-xdist worker options to command if appropriate.

        Args:
            cmd: Command list to modify
            options: Test command options
        """
        # Check if project has explicitly disabled xdist
        if self._check_project_disabled_xdist():
            self._print_xdist_disabled_message()
            return

        # Skip xdist for benchmarks (parallel execution skews results)
        if self._should_skip_xdist_for_benchmark(options):
            return

        workers = self.get_optimal_workers(options)
        self._add_worker_count_options(cmd, workers)

    def _print_xdist_disabled_message(self) -> None:
        """Print message explaining xdist is disabled by project config."""
        if self.console:
            self.console.print(
                "[yellow]⚠️ Project has disabled pytest-xdist in configuration[/yellow]"
            )
            self.console.print(
                "[cyan]🧪 Tests running sequentially (respecting project config)[/cyan]"
            )

    def _should_skip_xdist_for_benchmark(self, options: OptionsProtocol) -> bool:
        """Check if xdist should be skipped for benchmark tests.

        Args:
            options: Test command options

        Returns:
            True if benchmarks are running
        """
        if hasattr(options, "benchmark") and options.benchmark:
            if self.console:
                self.console.print(
                    "[yellow]⚠️ Benchmarks running sequentially (parallel execution skews results)[/yellow]"
                )
            return True
        return False

    def _add_worker_count_options(self, cmd: list[str], workers: str | int) -> None:
        """Add worker count options to command.

        Args:
            cmd: Command list to modify
            workers: Number of workers or 'auto'
        """
        if workers == "auto":
            cmd.extend(["-n", "auto", "--dist=loadfile"])
            if self.console:
                self.console.print(
                    "[cyan]🚀 Tests running with auto-detected workers (--dist=loadfile)[/cyan]"
                )
        elif isinstance(workers, int) and workers > 1:
            cmd.extend(["-n", str(workers), "--dist=loadfile"])
            if self.console:
                self.console.print(
                    f"[cyan]🚀 Tests running with {workers} workers (--dist=loadfile)[/cyan]"
                )
        else:
            if self.console:
                self.console.print("[cyan]🧪 Tests running sequentially[/cyan]")

    def _add_benchmark_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        if hasattr(options, "benchmark") and options.benchmark:
            cmd.extend(
                [
                    "--benchmark-only",
                    "--benchmark-sort=mean",
                    "--benchmark-columns=min, max, mean, stddev",
                ]
            )

    def _add_timeout_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        timeout = self.get_test_timeout(options)
        cmd.extend(["--timeout", str(timeout)])

    def _add_verbosity_options(self, cmd: list[str], options: OptionsProtocol) -> None:

        if options.verbose:
            if getattr(options, "ai_debug", False):
                cmd.append("-vvv")
                self.console.print("[cyan]🔍 Using extra verbose mode (-vvv)[/cyan]")
            else:
                cmd.append("-vv")
                self.console.print("[cyan]🔍 Using verbose mode (-vv)[/cyan]")
        else:
            cmd.append("-v")

        cmd.extend(
            [

                "--tb=long" if options.verbose else "--tb=short",

                "-ra",
                "--strict-markers",
                "--strict-config",
            ]
        )

    def _add_test_path(self, cmd: list[str]) -> None:
        test_paths = ["tests", "test"]

        for test_path in test_paths:
            full_path = self.pkg_path / test_path
            if full_path.exists() and full_path.is_dir():
                cmd.append(str(full_path))
                return

        cmd.append(str(self.pkg_path))

    def build_specific_test_command(self, test_pattern: str) -> list[str]:
        cmd = ["uv", "run", "python", "-m", "pytest", "-v"]


        package_name = self._detect_package_name()
        cmd.extend(
            [
                f"--cov={package_name}",
                "--cov-report=term-missing",
            ]
        )

        cmd.extend(["-k", test_pattern])

        self._add_test_path(cmd)

        return cmd

    def build_validation_command(self) -> list[str]:
        return [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "--collect-only",

            "tests" if (self.pkg_path / "tests").exists() else ".",
        ]
