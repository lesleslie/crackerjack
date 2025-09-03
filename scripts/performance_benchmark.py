#!/usr/bin/env python3
"""
Performance benchmark for code cleaner optimizations.
"""

import time
from pathlib import Path
from typing import NamedTuple

from rich.console import Console

from crackerjack.code_cleaner import CodeCleaner


class BenchmarkResult(NamedTuple):
    operation: str
    files_processed: int
    total_size_bytes: int
    duration_seconds: float
    files_per_second: float
    bytes_per_second: float


class CodeCleanerBenchmark:
    """Performance benchmark for code cleaner operations."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.cleaner = CodeCleaner(console=self.console)

    def benchmark_directory(self, directory: Path) -> BenchmarkResult:
        """Benchmark code cleaning on a directory of Python files."""
        python_files = list(directory.rglob("*.py"))

        # Filter files that should be processed
        files_to_process = [
            f for f in python_files if self.cleaner.should_process_file(f)
        ]

        if not files_to_process:
            return BenchmarkResult("directory_clean", 0, 0, 0.0, 0.0, 0.0)

        # Calculate total size
        total_size = sum(f.stat().st_size for f in files_to_process)

        self.console.print(
            f"[blue]Benchmarking {len(files_to_process)} files ({total_size:,} bytes)[/blue]"
        )

        start_time = time.perf_counter()
        results = self.cleaner.clean_files(directory)
        end_time = time.perf_counter()

        duration = end_time - start_time
        successful_files = sum(1 for r in results if r.success)

        files_per_second = len(files_to_process) / duration if duration > 0 else 0
        bytes_per_second = total_size / duration if duration > 0 else 0

        self.console.print(
            f"[green]✅ Processed {successful_files}/{len(files_to_process)} files in {duration:.2f}s[/green]"
        )
        self.console.print(
            f"[cyan]Performance: {files_per_second:.1f} files/s, {bytes_per_second:,.0f} bytes/s[/cyan]"
        )

        return BenchmarkResult(
            operation="directory_clean",
            files_processed=len(files_to_process),
            total_size_bytes=total_size,
            duration_seconds=duration,
            files_per_second=files_per_second,
            bytes_per_second=bytes_per_second,
        )

    def benchmark_large_file(self, file_path: Path) -> BenchmarkResult:
        """Benchmark code cleaning on a single large file."""
        if not file_path.exists():
            return BenchmarkResult("large_file_clean", 0, 0, 0.0, 0.0, 0.0)

        file_size = file_path.stat().st_size
        self.console.print(
            f"[blue]Benchmarking large file: {file_path} ({file_size:,} bytes)[/blue]"
        )

        start_time = time.perf_counter()
        result = self.cleaner.clean_file(file_path)
        end_time = time.perf_counter()

        duration = end_time - start_time
        bytes_per_second = file_size / duration if duration > 0 else 0

        status = "✅" if result.success else "❌"
        self.console.print(f"[green]{status} Processed in {duration:.2f}s[/green]")
        self.console.print(f"[cyan]Performance: {bytes_per_second:,.0f} bytes/s[/cyan]")

        return BenchmarkResult(
            operation="large_file_clean",
            files_processed=1,
            total_size_bytes=file_size,
            duration_seconds=duration,
            files_per_second=1 / duration if duration > 0 else 0,
            bytes_per_second=bytes_per_second,
        )

    def benchmark_string_operations(
        self, sample_code: str, iterations: int = 1000
    ) -> BenchmarkResult:
        """Benchmark string processing operations on sample code."""
        self.console.print(
            f"[blue]Benchmarking string operations ({iterations} iterations)[/blue]"
        )

        total_size = len(sample_code.encode("utf-8")) * iterations

        start_time = time.perf_counter()
        for _ in range(iterations):
            # Test each step individually for granular performance analysis
            _ = self.cleaner.remove_line_comments(sample_code)
            _ = self.cleaner.remove_docstrings(sample_code)
            _ = self.cleaner.remove_extra_whitespace(sample_code)
            _ = self.cleaner.format_code(sample_code)
        end_time = time.perf_counter()

        duration = end_time - start_time
        operations_per_second = (
            (iterations * 4) / duration if duration > 0 else 0
        )  # 4 operations per iteration
        bytes_per_second = total_size / duration if duration > 0 else 0

        self.console.print(
            f"[green]✅ Completed {iterations * 4} operations in {duration:.2f}s[/green]"
        )
        self.console.print(
            f"[cyan]Performance: {operations_per_second:.1f} operations/s, {bytes_per_second:,.0f} bytes/s[/cyan]"
        )

        return BenchmarkResult(
            operation="string_operations",
            files_processed=iterations,
            total_size_bytes=total_size,
            duration_seconds=duration,
            files_per_second=operations_per_second,
            bytes_per_second=bytes_per_second,
        )


def main():
    """Run comprehensive benchmarks."""
    console = Console()
    benchmark = CodeCleanerBenchmark(console)

    console.print("[bold blue]🚀 Code Cleaner Performance Benchmark[/bold blue]")
    console.print()

    # Benchmark on crackerjack directory
    crackerjack_dir = Path(__file__).parent / "crackerjack"
    if crackerjack_dir.exists():
        console.print("[bold]Directory Benchmark (crackerjack package):[/bold]")
        benchmark.benchmark_directory(crackerjack_dir)
        console.print()

    # Benchmark on large file (this file itself)
    console.print("[bold]Large File Benchmark:[/bold]")
    large_file = Path(__file__).parent / "crackerjack" / "code_cleaner.py"
    if large_file.exists():
        benchmark.benchmark_large_file(large_file)
    console.print()

    # String operations benchmark
    console.print("[bold]String Operations Benchmark:[/bold]")
    sample_code = '''
"""Sample Python code for benchmarking."""
import os  # This is a comment
import sys  # Another comment

def example_function(arg1, arg2):
    """This is a docstring that should be removed."""
    # This is an inline comment
    result = arg1 + arg2  # More comments here
    return result

class ExampleClass:
    """Class docstring."""

    def method(self):
        # Method comment
        pass
'''
    benchmark.benchmark_string_operations(sample_code, iterations=500)

    console.print()
    console.print("[bold green]🎯 Benchmark Complete![/bold green]")


if __name__ == "__main__":
    main()
