"""
Real-world examples of error handling decorator usage in Crackerjack.

This module demonstrates practical usage patterns for the decorator-based
error handling system, showing how to combine decorators for robust error
handling in production code.
"""

import asyncio
import subprocess
from pathlib import Path

from crackerjack.decorators import (
    cache_errors,
    graceful_degradation,
    handle_errors,
    log_errors,
    retry,
    validate_args,
    with_timeout,
)
from crackerjack.errors import ExecutionError, FileError, NetworkError


# Example 1: Simple retry for network operations
@retry(max_attempts=3, backoff=2.0, exceptions=[NetworkError])
async def fetch_package_metadata(package_name: str) -> dict:
    """
    Fetch package metadata from PyPI with automatic retry.

    Retries up to 3 times with exponential backoff on network errors.
    """
    # Simulated network operation
    async with asyncio.timeout(10):
        # In real code: await http_client.get(f"https://pypi.org/pypi/{package_name}/json")
        return {"name": package_name, "version": "1.0.0"}


# Example 2: Timeout enforcement for subprocess operations
@with_timeout(seconds=30, error_message="Git operation timed out")
@log_errors()
async def run_git_command(args: list[str], cwd: Path) -> str:
    """
    Run git command with timeout and error logging.

    Times out after 30 seconds and logs all errors before re-raising.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# Example 3: Graceful degradation for optional features
@graceful_degradation(fallback_value=[], warn=True)
def load_optional_plugins(plugin_dir: Path) -> list[str]:
    """
    Load optional plugins, returning empty list on failure.

    Useful for features that shouldn't break the application.
    """
    if not plugin_dir.exists():
        raise FileError("Plugin directory not found")

    return [p.name for p in plugin_dir.glob("*.py")]


# Example 4: Argument validation for critical functions
@validate_args(
    validators={
        "version": lambda v: v in ("major", "minor", "patch"),
        "files": lambda f: len(f) > 0,
    },
    type_check=True,
)
async def bump_version(version: str, files: list[Path]) -> bool:
    """
    Bump version with validated arguments.

    Validates that version is valid type and files list is non-empty.
    """
    # Implementation
    return True


# Example 5: Error transformation and handling
@handle_errors(
    error_types=[OSError, PermissionError],
    transform_to=FileError,
    fallback={},
)
def load_config_file(path: Path) -> dict:
    """
    Load configuration file with error transformation.

    Transforms OS/permission errors to FileError and returns empty dict as fallback.
    """
    with path.open() as f:
        # In real code: return toml.load(f)
        return {"config": "data"}


# Example 6: Error pattern caching for analysis
@cache_errors(error_type="lint", auto_analyze=True)
async def run_linter(files: list[Path]) -> dict:
    """
    Run linter with error pattern caching.

    Automatically tracks error patterns for future auto-fix suggestions.
    """
    # Simulated linter run
    result = subprocess.run(
        ["ruff", "check", *[str(f) for f in files]],
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "errors": result.stderr if result.returncode != 0 else None,
    }


# Example 7: Complex decorator stack for robust operations
@with_timeout(seconds=60)
@retry(max_attempts=3, backoff=2.0)
@log_errors()
@handle_errors(
    error_types=[ExecutionError],
    fallback={"success": False, "output": ""},
)
async def execute_quality_checks(project_dir: Path) -> dict:
    """
    Execute quality checks with comprehensive error handling.

    Stack demonstrates:
    - Timeout enforcement (60s)
    - Retry on failure (3 attempts)
    - Error logging
    - Error handling with fallback
    """
    # Simulated quality check execution
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--run-tests"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=50,
    )

    if result.returncode != 0:
        raise ExecutionError(
            message="Quality checks failed",
            details=result.stderr,
        )

    return {
        "success": True,
        "output": result.stdout,
    }


# Example 8: Validation with multiple validators per argument
@validate_args(
    validators={
        "email": (
            lambda e: "@" in e,
            lambda e: "." in e.split("@")[1],
            lambda e: len(e) >= 6,
        ),
        "age": lambda a: 0 < a < 150,
    }
)
def register_user(email: str, age: int) -> bool:
    """
    Register user with multi-stage email validation.

    Email validators check for:
    - Contains @
    - Domain has a dot
    - Minimum length
    """
    # Implementation
    return True


# Example 9: Combining retry with error pattern caching
@cache_errors(error_type="test", auto_analyze=True)
@retry(max_attempts=2, backoff=1.0)
async def run_test_suite(test_dir: Path) -> dict:
    """
    Run test suite with retry and pattern caching.

    Useful for flaky tests - retries once and caches error patterns
    for analysis.
    """
    result = subprocess.run(
        ["pytest", str(test_dir), "-v"],
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "errors": result.stderr if result.returncode != 0 else None,
    }


# Example 10: Graceful degradation with callable fallback
@graceful_degradation(
    fallback_value=lambda: {"provider": "default", "enabled": False},
    warn=True,
)
def load_ai_provider_config(config_path: Path) -> dict:
    """
    Load AI provider configuration with smart fallback.

    Returns default configuration object on error (callable fallback
    allows dynamic defaults).
    """
    if not config_path.exists():
        raise FileError(f"Config not found: {config_path}")

    # Load config
    return {"provider": "openai", "enabled": True}


# Example 11: Sync and async decorator compatibility
@handle_errors(fallback=False)
@validate_args(validators={"path": lambda p: p.exists()})
def sync_file_operation(path: Path) -> bool:
    """Synchronous file operation with validation and error handling."""
    return path.is_file()


@handle_errors(fallback=False)
@validate_args(validators={"path": lambda p: p.exists()})
async def async_file_operation(path: Path) -> bool:
    """Asynchronous file operation with same decorators."""
    await asyncio.sleep(0.1)  # Simulate async work
    return path.is_file()


# Example 12: Integration with existing ErrorHandlingMixin
class QualityManager:
    """Example showing decorators working alongside ErrorHandlingMixin."""

    def __init__(self) -> None:
        # ErrorHandlingMixin provides console and logger
        from rich.console import Console

        self.console = Console()
        self.logger = None  # Would be actual logger in production

    @retry(max_attempts=3, backoff=1.5)
    @log_errors()
    async def run_hooks(self, hook_type: str) -> bool:
        """
        Run pre-commit hooks with retry and logging.

        Combines decorator-based error handling with class-based approach.
        """
        # Implementation would use self.console and self.logger
        result = subprocess.run(
            ["pre-commit", "run", hook_type],
            capture_output=True,
            text=True,
        )

        return result.returncode == 0


async def main() -> None:
    """Demonstrate decorator usage."""
    # Example usage
    metadata = await fetch_package_metadata("crackerjack")
    print(f"Fetched metadata: {metadata}")

    # Graceful degradation example
    plugins = load_optional_plugins(Path("/nonexistent/plugins"))
    print(f"Loaded plugins: {plugins}")  # Returns [] gracefully

    # Validation example
    try:
        await bump_version("invalid", [Path("file.py")])
    except Exception as e:
        print(f"Validation failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
