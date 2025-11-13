#!/usr/bin/env python3
"""Performance benchmarking script for ACB workflow migration baseline.

This script establishes performance baselines by running crackerjack multiple
times across different modes and recording timing statistics (P50/P95/P99).

Usage:
    python scripts/benchmark_performance.py --runs 20 --output baseline-report.md
"""

import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import click


@dataclass
class BenchmarkRun:
    """Single benchmark run result."""

    mode: str
    duration_seconds: float
    exit_code: int
    timestamp: float
    success: bool


@dataclass
class BenchmarkStats:
    """Statistical summary of benchmark runs."""

    mode: str
    runs: int
    mean: float
    median: float
    p95: float
    p99: float
    min: float
    max: float
    std_dev: float
    success_rate: float


def run_command(args: list[str], timeout: int = 300) -> tuple[float, int]:
    """Run command and return (duration, exit_code)."""
    start = time.time()
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        duration = time.time() - start
        return (duration, result.returncode)
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return (duration, 124)  # Timeout exit code


def calculate_stats(runs: list[BenchmarkRun]) -> BenchmarkStats:
    """Calculate statistical summary from runs."""
    durations = [r.duration_seconds for r in runs]
    successes = sum(1 for r in runs if r.success)

    return BenchmarkStats(
        mode=runs[0].mode,
        runs=len(runs),
        mean=statistics.mean(durations),
        median=statistics.median(durations),
        p95=statistics.quantiles(durations, n=20)[18],  # 95th percentile
        p99=statistics.quantiles(durations, n=100)[98]
        if len(durations) >= 100
        else max(durations),  # 99th percentile
        min=min(durations),
        max=max(durations),
        std_dev=statistics.stdev(durations) if len(durations) > 1 else 0.0,
        success_rate=(successes / len(runs)) * 100,
    )


def format_markdown_report(results: dict[str, list[BenchmarkRun]]) -> str:
    """Generate markdown performance report."""
    report = [
        "# Crackerjack Performance Baseline Report\n",
        f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Summary\n",
    ]

    # Calculate stats for each mode
    stats_by_mode: dict[str, BenchmarkStats] = {}
    for mode, runs in results.items():
        stats_by_mode[mode] = calculate_stats(runs)

    # Summary table
    report.extend(
        (
            "| Mode | Runs | Mean | Median (P50) | P95 | P99 | Success Rate |",
            "|------|------|------|--------------|-----|-----|--------------|",
        )
    )

    for mode in ("default", "fast", "comp"):
        if mode not in stats_by_mode:
            continue
        stats = stats_by_mode[mode]
        report.append(
            f"| `{mode}` | {stats.runs} | {stats.mean:.2f}s | {stats.median:.2f}s | "
            f"{stats.p95:.2f}s | {stats.p99:.2f}s | {stats.success_rate:.0f}% |"
        )

    # Detailed statistics
    report.append("\n## Detailed Statistics\n")

    for mode, stats in stats_by_mode.items():
        report.extend(
            (
                f"### Mode: `{mode}`\n",
                f"- **Runs**: {stats.runs}",
                f"- **Mean**: {stats.mean:.2f}s",
                f"- **Median (P50)**: {stats.median:.2f}s",
                f"- **P95**: {stats.p95:.2f}s",
                f"- **P99**: {stats.p99:.2f}s",
                f"- **Min**: {stats.min:.2f}s",
                f"- **Max**: {stats.max:.2f}s",
                f"- **Std Dev**: {stats.std_dev:.2f}s",
                f"- **Success Rate**: {stats.success_rate:.0f}%\n",
            )
        )

    # Abort criteria
    report.extend(
        ("## ACB Migration Abort Criteria\n", "Based on these baseline measurements:\n")
    )

    for mode, stats in stats_by_mode.items():
        threshold = stats.median * 1.1  # 10% slower
        report.append(
            f"- **{mode} mode**: Abort if median > {threshold:.2f}s (10% slower than {stats.median:.2f}s)"
        )

    return "\n".join(report)


@click.command()
@click.option("--runs", default=20, help="Number of runs per mode")
@click.option(
    "--output",
    default="docs/performance-baseline.md",
    help="Output markdown report path",
)
@click.option("--timeout", default=300, help="Timeout per run in seconds")
@click.option(
    "--modes", default="default,fast,comp", help="Comma-separated modes to benchmark"
)
def main(runs: int, output: str, timeout: int, modes: str):
    """Run performance benchmarks and generate baseline report."""
    mode_list = modes.split(",")
    results: dict[str, list[BenchmarkRun]] = {mode: [] for mode in mode_list}

    click.echo(f"🔬 Running performance baseline ({runs} runs per mode)...")
    click.echo(f"Modes: {', '.join(mode_list)}\n")

    for mode in mode_list:
        click.echo(f"📊 Benchmarking mode: {mode}")

        # Build command
        if mode == "default":
            cmd = ["python", "-m", "crackerjack"]
        elif mode == "fast":
            cmd = ["python", "-m", "crackerjack", "--fast"]
        elif mode == "comp":
            cmd = ["python", "-m", "crackerjack", "--comp"]
        else:
            click.echo(f"  ⚠️  Unknown mode: {mode}, skipping")
            continue

        # Run benchmarks
        for i in range(runs):
            click.echo(f"  Run {i + 1}/{runs}...", nl=False)
            duration, exit_code = run_command(cmd, timeout)
            success = exit_code == 0

            run_result = BenchmarkRun(
                mode=mode,
                duration_seconds=duration,
                exit_code=exit_code,
                timestamp=time.time(),
                success=success,
            )
            results[mode].append(run_result)

            status = "✅" if success else "❌"
            click.echo(f" {status} {duration:.2f}s (exit: {exit_code})")

        # Quick stats
        stats = calculate_stats(results[mode])
        click.echo(
            f"  📈 {mode} median: {stats.median:.2f}s "
            f"(P95: {stats.p95:.2f}s, success: {stats.success_rate:.0f}%)\n"
        )

    # Generate report
    report = format_markdown_report(results)

    # Write report
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)

    click.echo(f"\n✅ Baseline report written to: {output}")

    # Also save raw data
    raw_output = output_path.with_suffix(".json")
    raw_data = {mode: [asdict(r) for r in runs] for mode, runs in results.items()}
    raw_output.write_text(json.dumps(raw_data, indent=2))

    click.echo(f"📊 Raw data written to: {raw_output}")


if __name__ == "__main__":
    main()
