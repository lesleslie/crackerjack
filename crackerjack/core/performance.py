import functools
import time
import typing as t
from pathlib import Path

from acb.console import Console


class FileCache:
    def __init__(self, ttl: float = 300.0) -> None:
        self.ttl = ttl
        self._cache: dict[str, tuple[float, t.Any]] = {}

    def get(self, key: str) -> t.Any | None:
        if key not in self._cache:
            return None
        timestamp, value = self._cache[key]
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: t.Any) -> None:
        self._cache[key] = (time.time(), value)

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


class PerformanceMonitor:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console
        self.metrics: dict[str, list[float]] = {}

    def time_operation(
        self,
        operation_name: str,
    ) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
        def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            @functools.wraps(func)
            def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                start_time = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.time() - start_time
                    self.record_metric(operation_name, duration)

            return wrapper

        return decorator

    def record_metric(self, name: str, value: float) -> None:
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)

    def get_stats(self, name: str) -> dict[str, float]:
        if name not in self.metrics or not self.metrics[name]:
            return {}
        values = self.metrics[name]
        return {
            "count": len(values),
            "total": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def print_stats(self, name: str | None = None) -> None:
        if not self.console:
            return
        if name:
            stats = self.get_stats(name)
            if stats:
                self.console.print(
                    f"[cyan]📊 {name}: [/ cyan] "
                    f"avg={stats['avg']: .3f}s, "
                    f"min={stats['min']: .3f}s, "
                    f"max={stats['max']: .3f}s, "
                    f"count={stats['count']}",
                )
        else:
            for metric_name in self.metrics:
                self.print_stats(metric_name)


def memoize_with_ttl(
    ttl: float = 300.0,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        cache: dict[str, tuple[float, t.Any]] = {}

        @functools.wraps(func)
        def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            key = str(args) + str(sorted(kwargs.items()))
            if key in cache:
                timestamp, value = cache[key]
                if time.time() - timestamp <= ttl:
                    return value
                del cache[key]
            result = func(*args, **kwargs)
            cache[key] = (time.time(), result)
            return result

        setattr(wrapper, "cache_clear", cache.clear)
        setattr(wrapper, "cache_info", lambda: {"size": len(cache), "ttl": ttl})
        return wrapper

    return decorator


def batch_file_operations(
    operations: list[t.Callable[[], t.Any]],
    batch_size: int = 50,
) -> list[t.Any]:
    results: list[t.Any] = []
    for i in range(0, len(operations), batch_size):
        batch = operations[i : i + batch_size]
        batch_results: list[t.Any] = []
        for operation in batch:
            try:
                result = operation()
                batch_results.append(result)
            except Exception as e:
                batch_results.append(e)
        results.extend(batch_results)
        if i + batch_size < len(operations):
            time.sleep(0.01)

    return results


class OptimizedFileWatcher:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self._file_cache = FileCache(ttl=60.0)

    @memoize_with_ttl(ttl=30.0)
    def get_python_files(self) -> list[Path]:
        return list[t.Any](self.root_path.rglob("*.py"))

    def get_modified_files(self, since: float) -> list[Path]:
        cache_key = f"modified_since_{since}"
        cached = self._file_cache.get(cache_key)
        if cached is not None:
            return t.cast(list[Path], cached)
        modified_files: list[Path] = []
        for py_file in self.get_python_files():
            try:
                if py_file.stat().st_mtime > since:
                    modified_files.append(py_file)
            except (OSError, FileNotFoundError):
                continue
        self._file_cache.set(cache_key, modified_files)
        return modified_files

    def clear_cache(self) -> None:
        self._file_cache.clear()

        if hasattr(self.get_python_files, "cache_clear"):
            cache_clear = getattr(self.get_python_files, "cache_clear")
            cache_clear()


class ParallelTaskExecutor:
    def __init__(self, max_workers: int | None = None) -> None:
        import os

        self.max_workers = max_workers or min(os.cpu_count() or 1, 8)

    def execute_tasks(
        self,
        tasks: list[t.Callable[[], t.Any]],
        timeout: float = 300.0,
    ) -> list[t.Any]:
        if len(tasks) <= 1:
            return [task() for task in tasks]
        import concurrent.futures

        results: list[tuple[int, t.Any]] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
        ) as executor:
            future_to_task = {executor.submit(task): i for i, task in enumerate(tasks)}
            for future in concurrent.futures.as_completed(
                future_to_task,
                timeout=timeout,
            ):
                task_index = future_to_task[future]
                try:
                    result = future.result()
                    results.append((task_index, result))
                except Exception as e:
                    results.append((task_index, e))
        import operator

        results.sort(key=operator.itemgetter(0))
        return [result for _, result in results]


def optimize_subprocess_calls(
    commands: list[list[str]],
    cwd: Path | None = None,
) -> list[t.Any]:
    if len(commands) <= 1:
        import subprocess

        return [
            subprocess.run(cmd, check=False, cwd=cwd, capture_output=True, text=True)
            for cmd in commands
        ]
    executor = ParallelTaskExecutor()

    def run_command(cmd: list[str]) -> t.Any:
        import subprocess

        return subprocess.run(cmd, check=False, cwd=cwd, capture_output=True, text=True)

    import functools

    tasks: list[t.Callable[[], t.Any]] = [
        functools.partial(run_command, cmd) for cmd in commands
    ]
    return executor.execute_tasks(tasks)


_performance_monitor: PerformanceMonitor | None = None


def get_performance_monitor() -> PerformanceMonitor:
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def reset_performance_monitor() -> None:
    global _performance_monitor
    _performance_monitor = None
