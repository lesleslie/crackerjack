import gc
import os
import sys
import time
import tracemalloc
import typing as t
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from threading import Lock
from typing import Any
from weakref import WeakSet

import psutil
from acb.depends import Inject, depends
from acb.logger import Logger


@dataclass
class MemoryStats:
    total_allocated_mb: float
    peak_usage_mb: float
    current_usage_mb: float
    gc_collections: int
    lazy_objects_created: int
    lazy_objects_loaded: int
    resource_pools_active: int


class LazyLoader:
    def __init__(
        self,
        factory: Callable[[], Any],
        logger: Logger,
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
        self._logger = logger

        MemoryOptimizer.get_instance().register_lazy_object(self)

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._loaded

    @property
    def access_count(self) -> int:
        return self._access_count

    def get(self) -> Any:
        with self._lock:
            if not self._loaded:
                self._logger.debug(f"Lazy loading resource: {self._name}")
                start_time = time.time()

                try:
                    self._value = self._factory()
                    self._loaded = True
                    load_time = time.time() - start_time
                    self._logger.debug(f"Loaded {self._name} in {load_time: .3f}s")

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
        with self._lock:
            if self._loaded and self._value is not None:
                self._logger.debug(f"Disposing lazy resource: {self._name}")

                if hasattr(self._value, "close"):
                    try:
                        self._value.close()
                    except Exception as e:
                        self._logger.warning(f"Error closing {self._name}: {e}")

                self._value = None
                self._loaded = False

                gc.collect()

    def __del__(self) -> None:
        if self._auto_dispose:
            self.dispose()


class ResourcePool:
    def __init__(
        self,
        factory: Callable[[], Any],
        logger: Logger,
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
        self._logger = logger

    def acquire(self) -> Any:
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
        with self._lock:
            if resource in self._in_use:
                self._in_use.discard(resource)

                if len(self._pool) < self._max_size:
                    self._pool.append(resource)
                    self._logger.debug(f"Returned resource to {self._name} pool")
                else:
                    if hasattr(resource, "close"):
                        try:
                            resource.close()
                        except Exception as e:
                            self._logger.warning(f"Error closing resource: {e}")

                    self._logger.debug(
                        f"Pool full, disposed resource from {self._name}"
                    )

    def clear(self) -> None:
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
    def __init__(self, logger: Logger) -> None:
        self._start_memory = 0.0
        self._peak_memory = 0.0
        self._measurements: list[tuple[float, float]] = []
        self._logger = logger

    def start_profiling(self) -> None:
        self._start_memory = self._get_memory_usage()
        self._peak_memory = self._start_memory
        self._measurements.clear()
        self._logger.debug(f"Started memory profiling at {self._start_memory: .2f} MB")

    def record_checkpoint(self, name: str = "") -> float:
        current_memory = self._get_memory_usage()
        self._peak_memory = max(self._peak_memory, current_memory)

        timestamp = time.time()
        self._measurements.append((timestamp, current_memory))

        if name:
            self._logger.debug(f"Memory checkpoint '{name}': {current_memory: .2f} MB")

        return current_memory

    def get_summary(self) -> dict[str, Any]:
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
        try:
            process = psutil.Process(os.getpid())
            memory_mb: float = process.memory_info().rss / 1024 / 1024
            return memory_mb
        except ImportError:
            if tracemalloc.is_tracing():
                current, _peak = tracemalloc.get_traced_memory()
                return current / 1024 / 1024
            else:
                return sys.getsizeof(gc.get_objects()) / 1024 / 1024


class MemoryOptimizer:
    _instance: t.Optional["MemoryOptimizer"] = None
    _lock = Lock()

    @depends.inject
    def __init__(
        self,
        logger: Inject[Logger],
    ) -> None:
        self._lazy_objects: WeakSet[t.Any] = WeakSet()
        self._resource_pools: dict[str, ResourcePool] = {}
        self._profiler = MemoryProfiler(logger=logger)
        self._stats_lock = Lock()
        self._lazy_created_count = 0
        self._lazy_loaded_count = 0
        self._gc_threshold = 100
        self._auto_gc = True
        self._logger = logger

    @classmethod
    def get_instance(cls) -> "MemoryOptimizer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register_lazy_object(self, lazy_obj: LazyLoader) -> None:
        self._lazy_objects.add(lazy_obj)
        with self._stats_lock:
            self._lazy_created_count += 1

    def notify_lazy_load(self, name: str) -> None:
        with self._stats_lock:
            self._lazy_loaded_count += 1

        if self._auto_gc and self._should_run_gc():
            self._run_memory_cleanup()

    def register_resource_pool(self, name: str, pool: ResourcePool) -> None:
        self._resource_pools[name] = pool
        self._logger.debug(f"Registered resource pool: {name}")

    def get_resource_pool(self, name: str) -> ResourcePool | None:
        return self._resource_pools.get(name)

    def start_profiling(self) -> None:
        self._profiler.start_profiling()

    def record_checkpoint(self, name: str = "") -> float:
        return self._profiler.record_checkpoint(name)

    def get_memory_stats(self) -> MemoryStats:
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
        self._logger.info("Running memory optimization")

        self._cleanup_lazy_objects()

        self._cleanup_resource_pools()

        collected = gc.collect()
        self._logger.debug(f"Garbage collection freed {collected} objects")

    def _should_run_gc(self) -> bool:
        current_memory = self._profiler.get_summary().get("current_memory_mb", 0)
        should_gc: bool = current_memory > self._gc_threshold
        return should_gc

    def _run_memory_cleanup(self) -> None:
        self._logger.debug("Running automatic memory cleanup")

        before_gc = self._profiler._get_memory_usage()
        collected = gc.collect()
        after_gc = self._profiler._get_memory_usage()

        memory_freed = before_gc - after_gc

        if memory_freed > 1.0:
            self._logger.info(
                f"Memory cleanup freed {memory_freed: .2f} MB ({collected} objects)"
            )

    def _cleanup_lazy_objects(self) -> None:
        disposed_count = 0

        lazy_objects = list[t.Any](self._lazy_objects)

        for lazy_obj in lazy_objects:
            if (
                hasattr(lazy_obj, "_last_access")
                and lazy_obj._last_access < time.time() - 300
                and lazy_obj.is_loaded
            ):
                lazy_obj.dispose()
                disposed_count += 1

        if disposed_count > 0:
            self._logger.debug(f"Disposed {disposed_count} unused lazy objects")

    def _cleanup_resource_pools(self) -> None:
        for name, pool in self._resource_pools.items():
            stats = pool.get_stats()

            if stats["efficiency"] < 0.1 and stats["created_total"] > 10:
                pool.clear()
                self._logger.debug(f"Cleared inefficient resource pool: {name}")


def lazy_property(factory: t.Callable[[], t.Any]) -> property:
    def decorator(self: t.Any) -> Any:
        attr_name = f"_lazy_{factory.__name__}"

        if not hasattr(self, attr_name):
            # Get logger from DI instead of MemoryOptimizer to avoid circular dependency
            logger = depends.get_sync(Logger)
            loader = LazyLoader(factory, logger=logger, name=factory.__name__)
            setattr(self, attr_name, loader)

        return getattr(self, attr_name).get()

    return property(decorator)


def memory_optimized(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @wraps(func)
    def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        optimizer = MemoryOptimizer.get_instance()

        before_memory = optimizer.record_checkpoint(f"{func.__name__}_start")

        try:
            result = func(*args, **kwargs)

            after_memory = optimizer.record_checkpoint(f"{func.__name__}_end")

            memory_delta = after_memory - before_memory
            if memory_delta > 10.0:
                optimizer._logger.warning(
                    f"Function {func.__name__} increased memory by {memory_delta: .2f} MB"
                )

            return result

        finally:
            if optimizer._should_run_gc():
                optimizer._run_memory_cleanup()

    return wrapper


def create_lazy_service(factory: Callable[[], Any], name: str) -> LazyLoader:
    # Get logger from DI instead of MemoryOptimizer to avoid circular dependency
    logger = depends.get_sync(Logger)
    return LazyLoader(factory, logger=logger, name=name)


def create_resource_pool(
    factory: Callable[[], Any],
    max_size: int = 5,
    name: str = "unnamed",
) -> ResourcePool:
    # Get logger from DI instead of MemoryOptimizer to avoid circular dependency
    logger = depends.get_sync(Logger)
    pool = ResourcePool(factory, logger=logger, max_size=max_size, name=name)
    MemoryOptimizer.get_instance().register_resource_pool(name, pool)
    return pool
