"""Test command building and configuration.

This module handles pytest command construction with various options and configurations.
Split from test_manager.py for better separation of concerns.
"""

from pathlib import Path

from crackerjack.models.protocols import OptionsProtocol


class TestCommandBuilder:
    """Builds pytest commands with appropriate options and configurations."""

    def __init__(self, pkg_path: Path) -> None:
        self.pkg_path = pkg_path

    def build_command(self, options: OptionsProtocol) -> list[str]:
        """Build complete pytest command with all options."""
        cmd = ["python", "-m", "pytest"]

        self._add_coverage_options(cmd, options)
        self._add_worker_options(cmd, options)
        self._add_benchmark_options(cmd, options)
        self._add_timeout_options(cmd, options)
        self._add_verbosity_options(cmd, options)
        self._add_test_path(cmd)

        return cmd

    def get_optimal_workers(self, options: OptionsProtocol) -> int:
        """Calculate optimal number of pytest workers based on system and configuration."""
        if hasattr(options, "test_workers") and options.test_workers:
            return options.test_workers

        # Auto-detect based on CPU count
        import multiprocessing

        cpu_count = multiprocessing.cpu_count()

        # Conservative worker count to avoid overwhelming the system
        if cpu_count <= 2:
            return 1
        elif cpu_count <= 4:
            return 2
        elif cpu_count <= 8:
            return 3
        return 4

    def get_test_timeout(self, options: OptionsProtocol) -> int:
        """Get test timeout based on options or default."""
        if hasattr(options, "test_timeout") and options.test_timeout:
            return options.test_timeout

        # Default timeout based on test configuration
        if hasattr(options, "benchmark") and options.benchmark:
            return 900  # 15 minutes for benchmarks
        return 300  # 5 minutes for regular tests

    def _add_coverage_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add coverage-related options to command."""
        # Always include coverage for comprehensive testing
        cmd.extend(
            [
                "--cov=crackerjack",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-fail-under=0",  # Don't fail on low coverage, let ratchet handle it
            ]
        )

    def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add parallel execution options to command."""
        workers = self.get_optimal_workers(options)
        if workers > 1:
            cmd.extend(["-n", str(workers)])

    def _add_benchmark_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add benchmark-specific options to command."""
        if hasattr(options, "benchmark") and options.benchmark:
            cmd.extend(
                [
                    "--benchmark-only",
                    "--benchmark-sort=mean",
                    "--benchmark-columns=min,max,mean,stddev",
                ]
            )

    def _add_timeout_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add timeout options to command."""
        timeout = self.get_test_timeout(options)
        cmd.extend(["--timeout", str(timeout)])

    def _add_verbosity_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        """Add verbosity and output formatting options."""
        # Always use verbose output for better progress tracking
        cmd.append("-v")

        # Add useful output options
        cmd.extend(
            [
                "--tb=short",  # Shorter traceback format
                "--strict-markers",  # Ensure all markers are defined
                "--strict-config",  # Ensure configuration is valid
            ]
        )

    def _add_test_path(self, cmd: list[str]) -> None:
        """Add test path to command."""
        # Add tests directory if it exists, otherwise current directory
        test_paths = ["tests", "test"]

        for test_path in test_paths:
            full_path = self.pkg_path / test_path
            if full_path.exists() and full_path.is_dir():
                cmd.append(str(full_path))
                return

        # Fallback to current directory
        cmd.append(str(self.pkg_path))

    def build_specific_test_command(self, test_pattern: str) -> list[str]:
        """Build command for running specific tests matching a pattern."""
        cmd = ["python", "-m", "pytest", "-v"]

        # Add basic coverage
        cmd.extend(
            [
                "--cov=crackerjack",
                "--cov-report=term-missing",
            ]
        )

        # Add the test pattern
        cmd.extend(["-k", test_pattern])

        # Add test path
        self._add_test_path(cmd)

        return cmd

    def build_validation_command(self) -> list[str]:
        """Build command for test environment validation."""
        return [
            "python",
            "-m",
            "pytest",
            "--collect-only",
            "--quiet",
            "tests" if (self.pkg_path / "tests").exists() else ".",
        ]
