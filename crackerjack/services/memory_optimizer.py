"""Memory optimization service with lazy loading and resource management.

This module provides memory-efficient patterns for managing heavy resources,
lazy loading, and memory profiling capabilities.
"""

import gc
import sys
import time
import typing as t
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from threading import Lock
from typing import Any
from weakref import WeakSet

from crackerjack.services.logging import get_logger


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    total_allocated_mb: float
    peak_usage_mb: float
    current_usage_mb: float
    gc_collections: int
    lazy_objects_created: int
    lazy_objects_loaded: int
    resource_pools_active: int


class LazyLoader:
    """Lazy loader for expensive resources."""

    def __init__(
        self,
        factory: Callable[[], Any],
        name: str = "unnamed",
        auto_dispose: bool = True,
    ):
        self._factory = factory
        self._name = name
        self._auto_dispose = auto_dispose
        self._value: Any | None = None
        self._loaded = False
        self._lock = Lock()
        self._access_count = 0
        self._last_access = time.time()
        self._logger = get_logger(f"crackerjack.lazy_loader.{name}")

        # Register for memory tracking
        MemoryOptimizer.get_instance().register_lazy_object(self)

    @property
    def is_loaded(self) -> bool:
        """Check if resource is loaded."""
        with self._lock:
            return self._loaded

    @property
    def access_count(self) -> int:
        """Get access count."""
        return self._access_count

    def get(self) -> Any:
        """Get the loaded resource, loading if necessary."""
        with self._lock:
            if not self._loaded:
                self._logger.debug(f"Lazy loading resource: {self._name}")
                start_time = time.time()

                try:
                    self._value = self._factory()
                    self._loaded = True
                    load_time = time.time() - start_time
                    self._logger.debug(f"Loaded {self._name} in {load_time:.3f}s")

                    # Register for memory tracking
                    MemoryOptimizer.get_instance().notify_lazy_load(self._name)

                except Exception as e:
                    self._logger.error(f"Failed to load {self._name}: {e}")
                    raise

            self._access_count += 1
            self._last_access = time.time()

            if self._value is None:
                raise RuntimeError(f"Lazy loader {self._name} has no value")

            return self._value

    def dispose(self) -> None:
        """Dispose of the loaded resource."""
        with self._lock:
            if self._loaded and self._value is not None:
                self._logger.debug(f"Disposing lazy resource: {self._name}")

                # If the object has a cleanup method, call it
                if hasattr(self._value, "close"):
                    try:
                        self._value.close()
                    except Exception as e:
                        self._logger.warning(f"Error closing {self._name}: {e}")

                self._value = None
                self._loaded = False

                # Force garbage collection for this object
                gc.collect()

    def __del__(self):
        """Clean up on deletion."""
        if self._auto_dispose:
            self.dispose()


class ResourcePool:
    """Pool for reusable expensive objects."""

    def __init__(
        self,
        factory: Callable[[], Any],
        max_size: int = 5,
        name: str = "unnamed",
    ):
        self._factory = factory
        self._max_size = max_size
        self._name = name
        self._pool: list[Any] = []
        self._in_use: WeakSet[t.Any] = WeakSet()
        self._lock = Lock()
        self._created_count = 0
        self._reused_count = 0
        self._logger = get_logger(f"crackerjack.resource_pool.{name}")

    def acquire(self) -> Any:
        """Acquire a resource from the pool."""
        with self._lock:
            if self._pool:
                resource = self._pool.pop()
                self._in_use.add(resource)
                self._reused_count += 1
                self._logger.debug(f"Reused resource from {self._name} pool")
                return resource
            else:
                resource = self._factory()
                self._in_use.add(resource)
                self._created_count += 1
                self._logger.debug(f"Created new resource for {self._name} pool")
                return resource

    def release(self, resource: Any) -> None:
        """Release a resource back to the pool."""
        with self._lock:
            if resource in self._in_use:
                self._in_use.discard(resource)

                if len(self._pool) < self._max_size:
                    self._pool.append(resource)
                    self._logger.debug(f"Returned resource to {self._name} pool")
                else:
                    # Pool is full, dispose of resource
                    if hasattr(resource, "close"):
                        try:
                            resource.close()
                        except Exception as e:
                            self._logger.warning(f"Error closing resource: {e}")

                    self._logger.debug(
                        f"Pool full, disposed resource from {self._name}"
                    )

    def clear(self) -> None:
        """Clear all resources from the pool."""
        with self._lock:
            for resource in self._pool:
                if hasattr(resource, "close"):
                    try:
                        resource.close()
                    except Exception as e:
                        self._logger.warning(f"Error closing pooled resource: {e}")

            self._pool.clear()
            self._logger.info(f"Cleared {self._name} resource pool")

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                "pool_size": len(self._pool),
                "in_use": len(self._in_use),
                "created_total": self._created_count,
                "reused_total": self._reused_count,
                "efficiency": (
                    self._reused_count / (self._created_count + self._reused_count)
                    if self._created_count + self._reused_count > 0
                    else 0.0
                ),
            }


class MemoryProfiler:
    """Simple memory profiler for performance monitoring."""

    def __init__(self):
        self._start_memory = 0.0
        self._peak_memory = 0.0
        self._measurements: list[tuple[float, float]] = []
        self._logger = get_logger("crackerjack.memory_profiler")

    def start_profiling(self) -> None:
        """Start memory profiling."""
        self._start_memory = self._get_memory_usage()
        self._peak_memory = self._start_memory
        self._measurements.clear()
        self._logger.debug(f"Started memory profiling at {self._start_memory:.2f} MB")

    def record_checkpoint(self, name: str = "") -> float:
        """Record memory checkpoint."""
        current_memory = self._get_memory_usage()
        self._peak_memory = max(self._peak_memory, current_memory)

        timestamp = time.time()
        self._measurements.append((timestamp, current_memory))

        if name:
            self._logger.debug(f"Memory checkpoint '{name}': {current_memory:.2f} MB")

        return current_memory

    def get_summary(self) -> dict[str, Any]:
        """Get profiling summary."""
        if not self._measurements:
            return {}

        current_memory = self._get_memory_usage()
        memory_delta = current_memory - self._start_memory

        return {
            "start_memory_mb": self._start_memory,
            "current_memory_mb": current_memory,
            "peak_memory_mb": self._peak_memory,
            "memory_delta_mb": memory_delta,
            "checkpoints": len(self._measurements),
        }

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Fallback to tracemalloc if psutil not available
            import tracemalloc

            if tracemalloc.is_tracing():
                current, _peak = tracemalloc.get_traced_memory()
                return current / 1024 / 1024
            else:
                # Basic fallback using sys.getsizeof (less accurate)
                return sys.getsizeof(gc.get_objects()) / 1024 / 1024


class MemoryOptimizer:
    """Central memory optimization coordinator."""

    _instance: t.Optional["MemoryOptimizer"] = None
    _lock = Lock()

    def __init__(self):
        self._lazy_objects: WeakSet[t.Any] = WeakSet()
        self._resource_pools: dict[str, ResourcePool] = {}
        self._profiler = MemoryProfiler()
        self._stats_lock = Lock()
        self._lazy_created_count = 0
        self._lazy_loaded_count = 0
        self._gc_threshold = 100  # MB
        self._auto_gc = True
        self._logger = get_logger("crackerjack.memory_optimizer")

    @classmethod
    def get_instance(cls) -> "MemoryOptimizer":
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register_lazy_object(self, lazy_obj: LazyLoader) -> None:
        """Register a lazy object for tracking."""
        self._lazy_objects.add(lazy_obj)
        with self._stats_lock:
            self._lazy_created_count += 1

    def notify_lazy_load(self, name: str) -> None:
        """Notify that a lazy object was loaded."""
        with self._stats_lock:
            self._lazy_loaded_count += 1

        # Check if we should trigger garbage collection
        if self._auto_gc and self._should_run_gc():
            self._run_memory_cleanup()

    def register_resource_pool(self, name: str, pool: ResourcePool) -> None:
        """Register a resource pool."""
        self._resource_pools[name] = pool
        self._logger.debug(f"Registered resource pool: {name}")

    def get_resource_pool(self, name: str) -> ResourcePool | None:
        """Get a registered resource pool."""
        return self._resource_pools.get(name)

    def start_profiling(self) -> None:
        """Start memory profiling."""
        self._profiler.start_profiling()

    def record_checkpoint(self, name: str = "") -> float:
        """Record memory checkpoint."""
        return self._profiler.record_checkpoint(name)

    def get_memory_stats(self) -> MemoryStats:
        """Get comprehensive memory statistics."""
        profiler_stats = self._profiler.get_summary()

        with self._stats_lock:
            return MemoryStats(
                total_allocated_mb=profiler_stats.get("peak_memory_mb", 0.0),
                peak_usage_mb=profiler_stats.get("peak_memory_mb", 0.0),
                current_usage_mb=profiler_stats.get("current_memory_mb", 0.0),
                gc_collections=len(gc.get_stats()) if hasattr(gc, "get_stats") else 0,
                lazy_objects_created=self._lazy_created_count,
                lazy_objects_loaded=self._lazy_loaded_count,
                resource_pools_active=len(self._resource_pools),
            )

    def optimize_memory(self) -> None:
        """Run memory optimization."""
        self._logger.info("Running memory optimization")

        # Dispose unused lazy objects
        self._cleanup_lazy_objects()

        # Clear resource pools if needed
        self._cleanup_resource_pools()

        # Force garbage collection
        collected = gc.collect()
        self._logger.debug(f"Garbage collection freed {collected} objects")

    def _should_run_gc(self) -> bool:
        """Check if garbage collection should be triggered."""
        current_memory = self._profiler.get_summary().get("current_memory_mb", 0)
        return current_memory > self._gc_threshold

    def _run_memory_cleanup(self) -> None:
        """Run memory cleanup operations."""
        self._logger.debug("Running automatic memory cleanup")

        # Collect garbage
        before_gc = self._profiler._get_memory_usage()
        collected = gc.collect()
        after_gc = self._profiler._get_memory_usage()

        memory_freed = before_gc - after_gc

        if memory_freed > 1.0:  # More than 1MB freed
            self._logger.info(
                f"Memory cleanup freed {memory_freed:.2f} MB ({collected} objects)"
            )

    def _cleanup_lazy_objects(self) -> None:
        """Clean up unused lazy objects."""
        disposed_count = 0

        # Convert to list to avoid modification during iteration
        lazy_objects = list(self._lazy_objects)

        for lazy_obj in lazy_objects:
            # Dispose objects that haven't been accessed recently
            if (
                hasattr(lazy_obj, "_last_access")
                and lazy_obj._last_access < time.time() - 300  # 5 minutes
                and lazy_obj.is_loaded
            ):
                lazy_obj.dispose()
                disposed_count += 1

        if disposed_count > 0:
            self._logger.debug(f"Disposed {disposed_count} unused lazy objects")

    def _cleanup_resource_pools(self) -> None:
        """Clean up resource pools."""
        for name, pool in self._resource_pools.items():
            stats = pool.get_stats()

            # Clear pool if efficiency is very low (lots of created, few reused)
            if stats["efficiency"] < 0.1 and stats["created_total"] > 10:
                pool.clear()
                self._logger.debug(f"Cleared inefficient resource pool: {name}")


def lazy_property(factory: t.Callable[[], Any]) -> t.Callable[[t.Any], Any]:
    """Decorator for lazy property loading."""

    def decorator(self: t.Any) -> Any:
        attr_name = f"_lazy_{factory.__name__}"

        if not hasattr(self, attr_name):
            loader = LazyLoader(factory, factory.__name__)
            setattr(self, attr_name, loader)

        return getattr(self, attr_name).get()

    return property(decorator)  # type: ignore[return-value]


def memory_optimized(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    """Decorator to add memory optimization to functions."""

    @wraps(func)
    def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        optimizer = MemoryOptimizer.get_instance()

        # Record memory before function execution
        before_memory = optimizer.record_checkpoint(f"{func.__name__}_start")

        try:
            result = func(*args, **kwargs)

            # Record memory after function execution
            after_memory = optimizer.record_checkpoint(f"{func.__name__}_end")

            # Log significant memory increases
            memory_delta = after_memory - before_memory
            if memory_delta > 10.0:  # More than 10MB increase
                optimizer._logger.warning(
                    f"Function {func.__name__} increased memory by {memory_delta:.2f} MB"
                )

            return result

        finally:
            # Run cleanup if memory usage is high
            if optimizer._should_run_gc():
                optimizer._run_memory_cleanup()

    return wrapper


# Global optimizer instance
def get_memory_optimizer() -> MemoryOptimizer:
    """Get global memory optimizer instance."""
    return MemoryOptimizer.get_instance()


# Factory functions for common patterns
def create_lazy_service(factory: Callable[[], Any], name: str) -> LazyLoader:
    """Create a lazy-loaded service."""
    return LazyLoader(factory, name)


def create_resource_pool(
    factory: Callable[[], Any],
    max_size: int = 5,
    name: str = "unnamed",
) -> ResourcePool:
    """Create a resource pool and register it."""
    pool = ResourcePool(factory, max_size, name)
    MemoryOptimizer.get_instance().register_resource_pool(name, pool)
    return pool
