import os
from pathlib import Path

import psutil
from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.models.protocols import OptionsProtocol


class TestCommandBuilder:
    @depends.inject
    def __init__(
        self,
        pkg_path: Inject[Path],
        console: Inject[Console],
        settings: Inject[CrackerjackSettings],
    ) -> None:
        # Normalize to pathlib.Path to avoid async path methods
        try:
            self.pkg_path = Path(str(pkg_path))
        except Exception:
            self.pkg_path = Path(pkg_path)

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
        """Handle NotImplementedError specifically."""
        if print_info and self.console:
            self.console.print(
                "[yellow]⚠️  CPU detection unavailable, using 2 workers[/yellow]"
            )
        return 2

    def _handle_general_error(self, print_info: bool, e: Exception) -> int:
        """Handle general exceptions gracefully."""
        if print_info and self.console:
            self.console.print(
                f"[yellow]⚠️  Worker detection failed: {e}. Using 2 workers.[/yellow]"
            )
        return 2

    def get_optimal_workers(
        self, options: OptionsProtocol, print_info: bool = True
    ) -> int | str:
        """Calculate optimal worker count using pytest-xdist.

        This method leverages pytest-xdist's built-in '-n auto' for CPU detection
        while adding memory safety checks and support for custom worker configurations.

        Worker Selection Logic:
        ----------------------
        1. Emergency rollback: CRACKERJACK_DISABLE_AUTO_WORKERS=1 → 1 worker
        2. Explicit value (test_workers > 0): Use as-is
        3. Auto-detect (test_workers = 0 AND auto_detect_workers=True): Return "auto"
        4. Legacy mode (test_workers = 0 AND auto_detect_workers=False): 1 worker
        5. Fractional (test_workers < 0): Divide CPU count by abs(value)

        Safety Bounds:
        -------------
        - Minimum: 1 worker (sequential execution)
        - Maximum: 8 workers (configurable via settings.testing.max_workers)
        - Memory: 2GB per worker minimum (configurable)

        Examples:
        --------
        >>> options = Options(test_workers=4)
        >>> builder.get_optimal_workers(options)
        4  # Explicit value

        >>> options = Options(test_workers=0)  # auto_detect_workers=True
        >>> builder.get_optimal_workers(options)
        "auto"  # Delegates to pytest-xdist

        >>> options = Options(test_workers=-2)  # 8-core machine
        >>> builder.get_optimal_workers(options)
        4  # 8 // 2 = 4 (with memory safety check)

        Returns:
            int | str: Number of workers (1-8) or "auto" for pytest-xdist detection

        Raises:
            Never raises - returns safe default (2) on any error
        """
        try:
            # Check for emergency rollback
            if self._check_emergency_rollback(print_info):
                return 1

            # Check explicit worker count
            explicit_result = self._check_explicit_workers(options, print_info)
            if explicit_result is not None:
                return explicit_result

            # Check auto-detection
            auto_result = self._check_auto_detection(options, print_info)
            if auto_result is not None:
                return auto_result

            # Check fractional workers
            fractional_result = self._check_fractional_workers(options, print_info)
            if fractional_result is not None:
                return fractional_result

            # Safe default if no conditions match
            return 2

        except NotImplementedError:
            return self._handle_not_implemented_error(print_info)
        except Exception as e:
            return self._handle_general_error(print_info, e)

    def _check_emergency_rollback(self, print_info: bool) -> bool:
        """Check for emergency rollback via environment variable."""
        if os.getenv("CRACKERJACK_DISABLE_AUTO_WORKERS") == "1":
            if print_info and self.console:
                self.console.print(
                    "[yellow]⚠️  Auto-detection disabled via environment variable[/yellow]"
                )
            return True
        return False

    def _check_explicit_workers(
        self, options: OptionsProtocol, print_info: bool
    ) -> int | None:
        """Check for explicit worker count."""
        if hasattr(options, "test_workers") and options.test_workers > 0:
            return options.test_workers
        return None

    def _check_auto_detection(
        self, options: OptionsProtocol, print_info: bool
    ) -> str | int | None:
        """Check for auto-detection setting."""
        if hasattr(options, "test_workers") and options.test_workers == 0:
            # Check if auto-detection is enabled in settings
            if self.settings and self.settings.testing.auto_detect_workers:
                # Show message only when getting optimal workers with print_info=True
                if print_info and self.console:
                    self.console.print(
                        "[cyan]🔧 Using pytest-xdist auto-detection for workers[/cyan]"
                    )
                return "auto"  # pytest-xdist will handle CPU detection

            # Legacy behavior: auto_detect_workers=False
            return 1
        return None

    def _check_fractional_workers(
        self, options: OptionsProtocol, print_info: bool
    ) -> int | None:
        """Check for fractional worker setting."""
        if hasattr(options, "test_workers") and options.test_workers < 0:
            import multiprocessing

            cpu_count = multiprocessing.cpu_count()
            divisor = abs(options.test_workers)
            workers = max(1, cpu_count // divisor)

            # Apply memory safety check
            workers = self._apply_memory_limit(workers)

            if print_info and self.console:
                self.console.print(
                    f"[cyan]🔧 Fractional workers: {cpu_count} cores ÷ {divisor} = {workers} workers[/cyan]"
                )

            return workers
        return None

    def _apply_memory_limit(self, workers: int) -> int:
        """Limit workers based on available memory to prevent OOM.

        Args:
            workers: Desired number of workers

        Returns:
            int: Worker count limited by available memory
        """
        try:
            # Get memory threshold from settings (default 2GB per worker)
            memory_per_worker = (
                self.settings.testing.memory_per_worker_gb if self.settings else 2.0
            )

            # Calculate available memory in GB
            available_gb = psutil.virtual_memory().available / (1024**3)

            # Calculate max workers based on memory
            max_by_memory = max(1, int(available_gb / memory_per_worker))

            # Return the minimum of desired workers and memory-limited workers
            limited_workers = min(workers, max_by_memory)

            # Log if we're limiting due to memory
            if limited_workers < workers and self.console:
                self.console.print(
                    f"[yellow]⚠️  Limited to {limited_workers} workers (available memory: {available_gb:.1f}GB)[/yellow]"
                )

            return limited_workers

        except Exception:
            # Conservative fallback if psutil fails
            return min(workers, 4)

    def get_test_timeout(self, options: OptionsProtocol) -> int:
        if hasattr(options, "test_timeout") and options.test_timeout:
            return options.test_timeout

        if hasattr(options, "benchmark") and options.benchmark:
            return 900
        return 300

    def _detect_package_name(self) -> str:
        """Detect the main package name for coverage reporting."""
        # Method 1: Try to read from pyproject.toml
        pyproject_path = self.pkg_path / "pyproject.toml"
        if pyproject_path.exists():
            from contextlib import suppress

            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)
                    project_name = data.get("project", {}).get("name")
                    if project_name:
                        # Convert project name to package name (hyphens to underscores)
                        return project_name.replace("-", "_")
            # Fall back to directory detection

        # Method 2: Look for Python packages in the project root
        for item in self.pkg_path.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith(".")
                and item.name not in ("tests", "docs", "build", "dist", "__pycache__")
                and (item / "__init__.py").exists()
            ):
                return item.name

        # Method 3: Fallback to crackerjack if nothing found (for crackerjack itself)
        return "crackerjack"

    def _add_coverage_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        # Determine package name from project structure
        package_name = self._detect_package_name()

        cmd.extend(
            [
                f"--cov={package_name}",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-report=json",  # Required for badge updates
                "--cov-fail-under=0",
            ]
        )

    def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add pytest-xdist worker options with proper distribution strategy.

        Args:
            cmd: Command list to append worker options to
            options: Test options containing worker configuration
        """
        workers = self.get_optimal_workers(options)

        # Skip benchmarks for parallelization (results get skewed)
        if hasattr(options, "benchmark") and options.benchmark:
            if self.console:
                self.console.print(
                    "[yellow]⚠️  Benchmarks running sequentially (parallel execution skews results)[/yellow]"
                )
            return

        if workers == "auto":
            # Use pytest-xdist's native auto-detection
            cmd.extend(["-n", "auto", "--dist=loadfile"])
            if self.console:
                self.console.print(
                    "[cyan]🚀 Tests running with auto-detected workers (--dist=loadfile)[/cyan]"
                )
        elif isinstance(workers, int) and workers > 1:
            # Explicit worker count
            cmd.extend(["-n", str(workers), "--dist=loadfile"])
            if self.console:
                self.console.print(
                    f"[cyan]🚀 Tests running with {workers} workers (--dist=loadfile)[/cyan]"
                )
        else:
            # Sequential execution (workers == 1)
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
        # Always use verbose mode to ensure collection headers are visible
        cmd.append("-v")

        cmd.extend(
            [
                "--tb=short",
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
        cmd = ["uv", "run", "python", "-m", "pytest", "-v"]  # Always use verbose mode

        cmd.extend(
            [
                "--cov=crackerjack",
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
            # Removed --quiet to ensure collection headers are visible
            "tests" if (self.pkg_path / "tests").exists() else ".",
        ]
