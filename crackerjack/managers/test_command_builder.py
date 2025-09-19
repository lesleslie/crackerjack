from pathlib import Path

from crackerjack.models.protocols import OptionsProtocol


class TestCommandBuilder:
    def __init__(self, pkg_path: Path) -> None:
        self.pkg_path = pkg_path

    def build_command(self, options: OptionsProtocol) -> list[str]:
        cmd = ["uv", "run", "python", "-m", "pytest"]

        self._add_coverage_options(cmd, options)
        self._add_worker_options(cmd, options)
        self._add_benchmark_options(cmd, options)
        self._add_timeout_options(cmd, options)
        self._add_verbosity_options(cmd, options)
        self._add_test_path(cmd)

        return cmd

    def get_optimal_workers(self, options: OptionsProtocol) -> int:
        if hasattr(options, "test_workers") and options.test_workers:
            return options.test_workers

        return 1

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
        workers = self.get_optimal_workers(options)
        if workers > 1:
            cmd.extend(["-n", str(workers)])

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
        cmd = ["uv", "run", "python", "-m", "pytest", "-v"]

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
            "--quiet",
            "tests" if (self.pkg_path / "tests").exists() else ".",
        ]
