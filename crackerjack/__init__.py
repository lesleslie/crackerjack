import logging
import sys
import typing as t

_EARLY_DEBUG_MODE = any(
    arg in ("--debug", "-d", "--ai-debug") or arg.startswith("--debug=")
    for arg in sys.argv[1:]
)

if not _EARLY_DEBUG_MODE:
    crackerjack_logger = logging.getLogger("crackerjack")
    crackerjack_logger.setLevel(logging.WARNING)

    for logger_name in (
        "uvicorn",
        "fastapi",
        "httpx",
        "httpcore",
        "oneiric",
        "Oneiric",
        "oneiric.core",
        "oneiric.runtime",
    ):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False

from importlib.metadata import version

# Lazily-loaded submodules. Keeping these out of the eager import chain means
# that ``import crackerjack.core.timeout_manager`` (or any other submodule)
# does NOT trigger ``crackerjack.api`` -> ``crackerjack.models.protocols`` ->
# ``crackerjack.config.mcp_settings_adapter`` -> ``mcp_common`` -> ``fastmcp``
# -> ``mcp.types``. That chain can fail when the test runner's ``sys.path``
# shim shadows the real ``mcp`` package (e.g.
# ``tests/unit/test_adapter_observability.py`` inserts the ``crackerjack/``
# source dir at ``sys.path[0]``, which makes ``crackerjack/mcp/`` shadow the
# site-packages ``mcp`` and breaks ``import mcp.types``). Symbols that
# genuinely require the chain are loaded on first attribute access.
_LAZY_EXPORTS: dict[str, str] = {
    # .api
    "CrackerjackAPI": "crackerjack.api",
    "PublishResult": "crackerjack.api",
    "QualityCheckResult": "crackerjack.api",
    "TestResult": "crackerjack.api",
    "clean_code": "crackerjack.api",
    "publish_package": "crackerjack.api",
    "run_quality_checks": "crackerjack.api",
    "run_tests": "crackerjack.api",
    # .errors
    "CleaningError": "crackerjack.errors",
    "ConfigError": "crackerjack.errors",
    "CrackerjackError": "crackerjack.errors",
    "DependencyError": "crackerjack.errors",
    "ErrorCode": "crackerjack.errors",
    "ExecutionError": "crackerjack.errors",
    "FileError": "crackerjack.errors",
    "GitError": "crackerjack.errors",
    "NetworkError": "crackerjack.errors",
    "PublishError": "crackerjack.errors",
    "ResourceError": "crackerjack.errors",
    "SecurityError": "crackerjack.errors",
    "TestExecutionError": "crackerjack.errors",
    "TimeoutError": "crackerjack.errors",
    "ValidationError": "crackerjack.errors",
    "check_command_result": "crackerjack.errors",
    "check_file_exists": "crackerjack.errors",
    "handle_error": "crackerjack.errors",
    # .interactive
    "InteractiveWorkflowOptions": "crackerjack.interactive",
    # ``WorkflowOptions`` is a public alias for ``InteractiveWorkflowOptions``.
    "WorkflowOptions": "crackerjack.interactive",
}


def __getattr__(name: str) -> t.Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_name)
    # ``WorkflowOptions`` is a public alias for ``InteractiveWorkflowOptions``
    # in ``crackerjack.interactive``; resolve via the source name.
    if name == "WorkflowOptions":
        value = module.InteractiveWorkflowOptions
    else:
        value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals().keys()))


__version__ = version("crackerjack")
__all__: t.Sequence[str] = [
    "CleaningError",
    "ConfigError",
    "CrackerjackAPI",
    "CrackerjackError",
    "DependencyError",
    "ErrorCode",
    "ExecutionError",
    "FileError",
    "GitError",
    "NetworkError",
    "PublishError",
    "PublishResult",
    "QualityCheckResult",
    "ResourceError",
    "SecurityError",
    "TestExecutionError",
    "TestResult",
    "TimeoutError",
    "ValidationError",
    "WorkflowOptions",
    "__version__",
    "check_command_result",
    "check_file_exists",
    "clean_code",
    "handle_error",
    "publish_package",
    "run_quality_checks",
    "run_tests",
]
