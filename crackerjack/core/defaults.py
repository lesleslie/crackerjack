from pathlib import Path
from typing import Any, Final

DEFAULT_COVERAGE_THRESHOLD: Final[int] = 80


DEFAULT_COMPLEXITY_THRESHOLD: Final[int] = 15


DEFAULT_MAX_FUNCTION_LENGTH: Final[int] = 50


DEFAULT_TEST_TIMEOUT: Final[int] = 300


DEFAULT_COMMAND_TIMEOUT: Final[int] = 600


DEFAULT_PARALLEL_EXECUTION: Final[bool] = True


DEFAULT_AUTO_DETECT_WORKERS: Final[bool] = True


DEFAULT_MAX_WORKERS: Final[int] = 8


DEFAULT_MIN_WORKERS: Final[int] = 2


DEFAULT_RUFF_SELECT: Final[list[str]] = [
    "E",
    "W",
    "F",
    "I",
    "N",
    "UP",
    "B",
    "C4",
    "SIM",
    "RUF",
]


DEFAULT_RUFF_IGNORE: Final[list[str]] = [
    "E502",
]


DEFAULT_ENABLE_COVERAGE: Final[bool] = True


DEFAULT_COVERAGE_REPORTS: Final[list[str]] = [
    "term",
    "html",
]


DEFAULT_ENABLE_SECURITY: Final[bool] = True


DEFAULT_SECURITY_TOOLS: Final[list[str]] = [
    "bandit",
    "safety",
]


DEFAULT_PROJECT_ROOT: Final[Path] = Path.cwd()


DEFAULT_PACKAGE_NAME: Final[str] = None


DEFAULT_EXCLUDE_DIRS: Final[list[str]] = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    "build",
    "dist",
    "*.egg-info",
]


DEFAULT_OUTPUT_FORMAT: Final[str] = "console"


DEFAULT_VERBOSE: Final[bool] = False


DEFAULT_SHOW_PROGRESS: Final[bool] = True


DEFAULT_COLOR_OUTPUT: Final[bool] = True


DEFAULT_FAIL_ON_TEST_ERRORS: Final[bool] = True


DEFAULT_FAIL_ON_COVERAGE: Final[bool] = True


DEFAULT_FAIL_ON_COMPLEXITY: Final[bool] = True


DEFAULT_FAIL_ON_SECURITY: Final[bool] = True


DEFAULT_ENABLE_CACHING: Final[bool] = True


DEFAULT_CACHE_TTL: Final[int] = 3600


DEFAULT_CACHE_MAX_ENTRIES: Final[int] = 1000


DEFAULT_AI_FIX_ENABLED: Final[bool] = False


DEFAULT_AI_PROVIDER: Final[str] = "claude"


DEFAULT_AI_MAX_ITERATIONS: Final[int] = 5


DEFAULT_DOCS_CLEANUP_ENABLED: Final[bool] = True


DEFAULT_DOCS_BACKUP_BEFORE_CLEANUP: Final[bool] = True


DEFAULT_GIT_COMMIT: Final[bool] = False


DEFAULT_GIT_CREATE_PR: Final[bool] = False


DEFAULT_UPDATE_PRECOMMIT: Final[bool] = False


def get_all_defaults() -> dict[str, any]:  # type: ignore
    import inspect
    import sys

    defaults = {}
    module = sys.modules[__name__]

    for name, value in inspect.getmembers(module):
        if not name.startswith("DEFAULT_"):
            continue

        if callable(value):
            continue

        if inspect.ismodule(value):
            continue

        if name == "__all__":
            continue

        defaults[name] = value

    return defaults


def get_default(name: str) -> Any:

    if not name.startswith("DEFAULT_"):
        name = f"DEFAULT_{name}"

    if name not in globals():
        raise AttributeError(f"Default '{name}' does not exist")

    return globals()[name]


__all__ = [
    "DEFAULT_COVERAGE_THRESHOLD",
    "DEFAULT_COMPLEXITY_THRESHOLD",
    "DEFAULT_MAX_FUNCTION_LENGTH",
    "DEFAULT_TEST_TIMEOUT",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_PARALLEL_EXECUTION",
    "DEFAULT_AUTO_DETECT_WORKERS",
    "DEFAULT_MAX_WORKERS",
    "DEFAULT_MIN_WORKERS",
    "DEFAULT_RUFF_SELECT",
    "DEFAULT_RUFF_IGNORE",
    "DEFAULT_ENABLE_COVERAGE",
    "DEFAULT_COVERAGE_REPORTS",
    "DEFAULT_ENABLE_SECURITY",
    "DEFAULT_SECURITY_TOOLS",
    "DEFAULT_PROJECT_ROOT",
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_OUTPUT_FORMAT",
    "DEFAULT_VERBOSE",
    "DEFAULT_SHOW_PROGRESS",
    "DEFAULT_COLOR_OUTPUT",
    "DEFAULT_FAIL_ON_TEST_ERRORS",
    "DEFAULT_FAIL_ON_COVERAGE",
    "DEFAULT_FAIL_ON_COMPLEXITY",
    "DEFAULT_FAIL_ON_SECURITY",
    "DEFAULT_ENABLE_CACHING",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CACHE_MAX_ENTRIES",
    "DEFAULT_AI_FIX_ENABLED",
    "DEFAULT_AI_PROVIDER",
    "DEFAULT_AI_MAX_ITERATIONS",
    "DEFAULT_DOCS_CLEANUP_ENABLED",
    "DEFAULT_DOCS_BACKUP_BEFORE_CLEANUP",
    "DEFAULT_GIT_COMMIT",
    "DEFAULT_GIT_CREATE_PR",
    "DEFAULT_UPDATE_PRECOMMIT",
    "get_all_defaults",
    "get_default",
]
