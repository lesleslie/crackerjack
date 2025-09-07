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

        # Temporarily disable multi-worker execution due to pytest-xdist
        # hanging issues with async tests. See GitHub issue for details.
        # TODO: Re-enable after fixing async test timeout issues
        return 1

        # Original multi-worker logic (commented out):
        # import multiprocessing
        # cpu_count = multiprocessing.cpu_count()
        # if cpu_count <= 2:
        #     return 1
        # elif cpu_count <= 4:
        #     return 2
        # elif cpu_count <= 8:
        #     return 3
        # return 4

    def get_test_timeout(self, options: OptionsProtocol) -> int:
        if hasattr(options, "test_timeout") and options.test_timeout:
            return options.test_timeout

        if hasattr(options, "benchmark") and options.benchmark:
            return 900
        return 300

    def _add_coverage_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        cmd.extend(
            [
                "--cov=crackerjack",
                "--cov-report=term-missing",
                "--cov-report=html",
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
                    "--benchmark-columns=min,max,mean,stddev",
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
