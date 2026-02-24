import asyncio
import logging
import re
import time
import typing as t
from dataclasses import dataclass
from pathlib import Path

if t.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False

    failure_threshold: int = 3
    recovery_timeout: float = 60.0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def can_execute(self) -> bool:
        if not self.is_open:
            return True

        elapsed = time.time() - self.last_failure_time
        if elapsed >= self.recovery_timeout:
            logger.info("Circuit breaker entering half-open state")
            return True

        return False


@dataclass
class SearchResult:
    file_path: str
    line_number: int
    column: int
    match_text: str
    context_before: str | None = None
    context_after: str | None = None


class PyCharmMCPAdapter:
    def __init__(
        self,
        mcp_client: t.Any | None = None,
        timeout: float = 30.0,
        max_results: int = 100,
    ) -> None:
        self._mcp = mcp_client
        self._timeout = timeout
        self._max_results = max_results
        self._circuit_breaker = CircuitBreakerState()
        self._cache: dict[str, t.Any] = {}
        self._cache_ttl: dict[str, float] = {}
        self.logger = logging.getLogger(__name__)

    async def search_regex(
        self,
        pattern: str,
        file_pattern: str | None = None,
    ) -> list[SearchResult]:

        sanitized_pattern = self._sanitize_regex(pattern)
        if not sanitized_pattern:
            self.logger.warning(f"Invalid regex pattern rejected: {pattern[:50]}")
            return []

        cache_key = f"search:{sanitized_pattern}:{file_pattern}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        results = await self._execute_with_circuit_breaker(
            self._search_regex_impl,
            sanitized_pattern,
            file_pattern,
        )

        self._set_cached(cache_key, results, ttl=60.0)

        return results

    async def replace_text_in_file(
        self,
        file_path: str,
        search_text: str,
        replace_text: str,
    ) -> bool:

        if not self._is_safe_path(file_path):
            self.logger.warning(f"Unsafe file path rejected: {file_path}")
            return False

        return await self._execute_with_circuit_breaker(
            self._replace_text_impl,
            file_path,
            search_text,
            replace_text,
        )

    async def get_file_problems(
        self,
        file_path: str,
        errors_only: bool = False,
    ) -> list[dict[str, t.Any]]:

        if not self._is_safe_path(file_path):
            return []

        cache_key = f"problems:{file_path}:{errors_only}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        problems = await self._execute_with_circuit_breaker(
            self._get_file_problems_impl,
            file_path,
            errors_only,
        )

        self._set_cached(cache_key, problems, ttl=10.0)

        return problems

    async def reformat_file(self, file_path: str) -> bool:
        if not self._is_safe_path(file_path):
            return False

        return await self._execute_with_circuit_breaker(
            self._reformat_file_impl,
            file_path,
        )

    async def _search_regex_impl(
        self,
        pattern: str,
        file_pattern: str | None,
    ) -> list[SearchResult]:
        if not self._mcp:
            return self._fallback_search(pattern, file_pattern)

        try:
            results = await asyncio.wait_for(
                self._mcp.search_regex(
                    pattern=pattern,
                    file_pattern=file_pattern,
                ),
                timeout=self._timeout,
            )

            search_results = []
            for item in results[: self._max_results]:
                search_results.append(
                    SearchResult(
                        file_path=item.get("file_path", ""),
                        line_number=item.get("line", 0),
                        column=item.get("column", 0),
                        match_text=item.get("match", ""),
                        context_before=item.get("context_before"),
                        context_after=item.get("context_after"),
                    )
                )

            return search_results

        except TimeoutError:
            self.logger.warning(f"Search timed out for pattern: {pattern[:50]}")
            return []
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []

    async def _replace_text_impl(
        self,
        file_path: str,
        search_text: str,
        replace_text: str,
    ) -> bool:
        if not self._mcp:
            return self._fallback_replace(file_path, search_text, replace_text)

        try:
            result = await asyncio.wait_for(
                self._mcp.replace_text_in_file(
                    file_path=file_path,
                    search_text=search_text,
                    replace_text=replace_text,
                ),
                timeout=self._timeout,
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Replace failed: {e}")
            return False

    async def _get_file_problems_impl(
        self,
        file_path: str,
        errors_only: bool,
    ) -> list[dict[str, t.Any]]:
        if not self._mcp:
            return []

        try:
            problems = await asyncio.wait_for(
                self._mcp.get_file_problems(
                    file_path=file_path,
                    errors_only=errors_only,
                ),
                timeout=self._timeout,
            )
            return list(problems) if problems else []
        except Exception as e:
            self.logger.error(f"Get problems failed: {e}")
            return []

    async def _reformat_file_impl(self, file_path: str) -> bool:
        if not self._mcp:
            return False

        try:
            result = await asyncio.wait_for(
                self._mcp.reformat_file(file_path=file_path),
                timeout=self._timeout,
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Reformat failed: {e}")
            return False

    def _fallback_search(
        self,
        pattern: str,
        file_pattern: str | None,
    ) -> list[SearchResult]:
        import subprocess

        results = []

        try:
            cmd = ["grep", "-rn", "-E", pattern]
            if file_pattern:
                cmd.extend(["--include", file_pattern])
            cmd.append(".")

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            for line in proc.stdout.split("\n")[: self._max_results]:
                if ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        results.append(
                            SearchResult(
                                file_path=parts[0],
                                line_number=int(parts[1]),
                                column=0,
                                match_text=parts[2],
                            )
                        )

        except Exception as e:
            self.logger.debug(f"Fallback search failed: {e}")

        return results

    def _fallback_replace(
        self,
        file_path: str,
        search_text: str,
        replace_text: str,
    ) -> bool:
        try:
            path = Path(file_path)
            if not path.exists():
                return False

            content = path.read_text()
            new_content = content.replace(search_text, replace_text)

            if new_content != content:
                path.write_text(new_content)
                return True
            return False
        except Exception as e:
            self.logger.debug(f"Fallback replace failed: {e}")
            return False

    def _sanitize_regex(self, pattern: str) -> str:

        if len(pattern) > 500:
            return ""

        dangerous_patterns = [
            r"\(\.\*\)\+",
            r"\(\.\+\)\+",
            r"\(\.\*\)\*",
            r"\(\.\+\)\*",
            r"\(\.\*\)\{",
            r"\(\.\+\)\{",
        ]

        for dangerous in dangerous_patterns:
            if re.search(dangerous, pattern):
                return ""

        try:
            re.compile(pattern)
            return pattern
        except re.error:
            return ""

    def _is_safe_path(self, file_path: str) -> bool:

        if not file_path:
            return False

        if file_path.startswith("/"):
            if not file_path.startswith("/tmp"):
                return False

        if ".." in file_path:
            return False

        if "\x00" in file_path:
            return False

        return True

    async def _execute_with_circuit_breaker(
        self,
        func: t.Callable[..., t.Awaitable[t.Any]],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        if not self._circuit_breaker.can_execute():
            self.logger.debug("Circuit breaker is open, skipping operation")
            return []

        try:
            result = await func(*args, **kwargs)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            self.logger.error(f"Operation failed (circuit breaker): {e}")
            raise

    def _get_cached(self, key: str) -> t.Any | None:
        if key in self._cache:
            expiry = self._cache_ttl.get(key, 0)
            if time.time() < expiry:
                return self._cache[key]
            else:
                del self._cache[key]
                self._cache_ttl.pop(key, None)
        return None

    def _set_cached(self, key: str, value: t.Any, ttl: float = 60.0) -> None:
        self._cache[key] = value
        self._cache_ttl[key] = time.time() + ttl

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_ttl.clear()

    async def health_check(self) -> dict[str, t.Any]:
        return {
            "mcp_available": self._mcp is not None,
            "circuit_breaker_open": self._circuit_breaker.is_open,
            "failure_count": self._circuit_breaker.failure_count,
            "cache_size": len(self._cache),
        }
