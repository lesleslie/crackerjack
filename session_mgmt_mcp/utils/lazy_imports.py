#!/usr/bin/env python3
"""Lazy loading utilities for optional dependencies.

This module provides lazy loading for heavy or optional dependencies to improve
startup performance and handle missing dependencies gracefully.
"""

import importlib
from collections.abc import Callable
from functools import wraps
from typing import Any, Never

from .logging import get_session_logger

logger = get_session_logger()


class LazyImport:
    """Lazy import wrapper that loads modules on first access."""

    def __init__(
        self,
        module_name: str,
        fallback_value: Any = None,
        import_error_msg: str | None = None,
    ) -> None:
        self.module_name = module_name
        self.fallback_value = fallback_value
        self.import_error_msg = import_error_msg
        self._module = None
        self._import_attempted = False
        self._import_failed = False

    def __getattr__(self, name: str) -> Any:
        if not self._import_attempted:
            self._try_import()

        if self._import_failed:
            if self.fallback_value is not None:
                return getattr(self.fallback_value, name, None)
            raise ImportError(
                self.import_error_msg or f"Module {self.module_name} not available",
            )

        return getattr(self._module, name)

    def _try_import(self) -> None:
        """Attempt to import the module."""
        self._import_attempted = True
        try:
            self._module = importlib.import_module(self.module_name)
            logger.debug(f"Successfully imported {self.module_name}")
        except ImportError as e:
            self._import_failed = True
            logger.warning(f"Failed to import {self.module_name}: {e}")

    @property
    def available(self) -> bool:
        """Check if the module is available."""
        if not self._import_attempted:
            self._try_import()
        return not self._import_failed

    def __bool__(self) -> bool:
        if not self._import_attempted:
            self._try_import()
        return not self._import_failed


class LazyLoader:
    """Manages lazy loading of multiple optional dependencies."""

    def __init__(self) -> None:
        self._loaders: dict[str, LazyImport] = {}

    def add_import(
        self,
        name: str,
        module_name: str,
        fallback_value: Any = None,
        error_msg: str | None = None,
    ) -> LazyImport:
        """Add a lazy import."""
        loader = LazyImport(module_name, fallback_value, error_msg)
        self._loaders[name] = loader
        return loader

    def get_import(self, name: str) -> LazyImport | None:
        """Get a lazy import by name."""
        return self._loaders.get(name)

    def check_availability(self) -> dict[str, bool]:
        """Check availability of all registered imports."""
        return {name: loader.available for name, loader in self._loaders.items()}


# Global lazy loader instance
lazy_loader = LazyLoader()

# Common lazy imports for session-mgmt-mcp
transformers = lazy_loader.add_import(
    "transformers",
    "transformers",
    error_msg="Transformers not available. Install with: uv sync --extra embeddings",
)

onnxruntime = lazy_loader.add_import(
    "onnxruntime",
    "onnxruntime",
    error_msg="ONNX Runtime not available. Install with: uv sync --extra embeddings",
)

tiktoken = lazy_loader.add_import(
    "tiktoken",
    "tiktoken",
    error_msg="tiktoken not available. Install with: uv sync --extra embeddings",
)

duckdb = lazy_loader.add_import(
    "duckdb",
    "duckdb",
    error_msg="DuckDB not available. Install with: uv add duckdb",
)

numpy = lazy_loader.add_import(
    "numpy",
    "numpy",
    error_msg="NumPy not available. Install with: uv sync --extra embeddings",
)


def require_dependency(dependency_name: str, install_hint: str | None = None):
    """Decorator to require a specific dependency for a function."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            loader = lazy_loader.get_import(dependency_name)
            if not loader or not loader.available:
                error_msg = f"Function {func.__name__} requires {dependency_name}"
                if install_hint:
                    error_msg += f". Install with: {install_hint}"
                raise ImportError(error_msg)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def optional_dependency(dependency_name: str, fallback_result: Any = None):
    """Decorator to handle optional dependencies gracefully."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            loader = lazy_loader.get_import(dependency_name)
            if not loader or not loader.available:
                logger.info(
                    f"Function {func.__name__} skipped - {dependency_name} not available",
                )
                return fallback_result
            return func(*args, **kwargs)

        return wrapper

    return decorator


class MockModule:
    """Mock module that provides fallback implementations."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __getattr__(self, name: str):
        def mock_function(*args, **kwargs) -> Never:
            msg = f"Mock function {name} called - {self.name} not available"
            raise ImportError(
                msg,
            )

        return mock_function


def create_embedding_mock():
    """Create a mock for embedding functionality."""

    class MockEmbedding:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def encode(self, texts, *args, **kwargs):
            # Return random-like embeddings for testing
            import random

            if isinstance(texts, str):
                return [[random.random() for _ in range(384)]]
            return [[random.random() for _ in range(384)] for _ in texts]

    return MockEmbedding


def get_dependency_status() -> dict[str, dict[str, Any]]:
    """Get comprehensive status of all dependencies."""
    status = {}

    # Check core dependencies
    core_deps = ["duckdb"]
    for dep in core_deps:
        loader = lazy_loader.get_import(dep)
        status[dep] = {
            "available": loader.available if loader else False,
            "required": True,
            "category": "core",
        }

    # Check optional dependencies
    optional_deps = ["transformers", "onnxruntime", "tiktoken", "numpy"]
    for dep in optional_deps:
        loader = lazy_loader.get_import(dep)
        status[dep] = {
            "available": loader.available if loader else False,
            "required": False,
            "category": "embeddings"
            if dep in ["transformers", "onnxruntime", "numpy"]
            else "optimization",
        }

    # Overall status
    core_available = all(status[dep]["available"] for dep in core_deps)
    embeddings_available = all(
        status[dep]["available"] for dep in ["transformers", "onnxruntime", "numpy"]
    )

    status["_summary"] = {
        "core_functionality": core_available,
        "embedding_functionality": embeddings_available,
        "optimization_functionality": status["tiktoken"]["available"],
        "overall_health": core_available,
    }

    return status


def log_dependency_status() -> None:
    """Log the current dependency status."""
    status = get_dependency_status()
    summary = status["_summary"]

    logger.info(
        "Dependency status check completed",
        core_functionality=summary["core_functionality"],
        embedding_functionality=summary["embedding_functionality"],
        optimization_functionality=summary["optimization_functionality"],
    )

    # Log missing dependencies
    missing_core = [dep for dep in ["duckdb"] if not status[dep]["available"]]
    missing_optional = [
        dep
        for dep in ["transformers", "onnxruntime", "tiktoken", "numpy"]
        if not status[dep]["available"]
    ]

    if missing_core:
        logger.warning("Missing core dependencies", missing=missing_core)

    if missing_optional:
        logger.info(
            "Missing optional dependencies",
            missing=missing_optional,
            install_hint="uv sync --extra embeddings",
        )


# Note: Dependency status logging should be called explicitly
# to avoid import-time issues. Call log_dependency_status() when needed.
