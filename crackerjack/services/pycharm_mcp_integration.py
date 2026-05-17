import asyncio
import logging
import os
import re
import time
import typing as t
from contextlib import suppress
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
        allowed_roots: t.Sequence[str | Path] | None = None,
    ) -> None:
        self._mcp = mcp_client
        self._timeout = timeout
        self._max_results = max_results
        self._circuit_breaker = CircuitBreakerState()
        self._cache: dict[str, t.Any] = {}
        self._cache_ttl: dict[str, float] = {}
        self._allowed_roots = self._normalize_allowed_roots(allowed_roots)
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

        if ".." in file_path:
            return False

        if "\x00" in file_path:
            return False

        try:
            candidate = Path(file_path).expanduser().resolve(strict=False)
        except Exception:
            return False

        return any(candidate.is_relative_to(root) for root in self._allowed_roots)

    def _normalize_allowed_roots(
        self,
        allowed_roots: t.Sequence[str | Path] | None,
    ) -> tuple[Path, ...]:
        roots: list[Path] = []

        if allowed_roots is None:
            env_roots = os.environ.get("CRACKERJACK_PYCHARM_ALLOWED_ROOTS", "")
            if env_roots:
                allowed_roots = [
                    Path(root) for root in env_roots.split(os.pathsep) if root
                ]
            else:
                allowed_roots = [Path.cwd(), Path("/tmp")]

        for root in allowed_roots:
            try:
                roots.append(Path(root).expanduser().resolve(strict=False))
            except Exception:
                continue

        return tuple(roots)

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


class MahavishnuPycharmMCPClient:
    def __init__(
        self,
        server_url: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.server_url = (
            server_url
            or os.environ.get("CRACKERJACK_PYCHARM_MCP_URL")
            or "http://localhost: 8680"
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: t.Any | None = None
        self._session: t.Any | None = None
        self._connected = False

    async def connect(self) -> bool:
        if self._connected:
            return True

        try:
            from mcp import ClientSession
            from mcp.client.streamablehttp import streamablehttp_client

            self._client = streamablehttp_client(url=f"{self.server_url}/mcp")
            self._session = ClientSession(self._client)  # type: ignore[call-arg]
            await self._session.__aenter__()
            self._connected = True
            return True
        except Exception as e:
            logger.debug("Failed to connect to Mahavishnu PyCharm MCP: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._session is not None:
            with suppress(Exception):
                await self._session.__aexit__(None, None, None)
        self._session = None
        self._client = None
        self._connected = False

    async def health_check(self) -> dict[str, t.Any]:
        connected = await self.connect()
        server_status: dict[str, t.Any] = {}
        if connected:
            with suppress(Exception):
                server_status = await self._call_tool("pycharm_health", {})
        available = bool(server_status.get("mcp_available", connected))
        return {
            "mcp_available": available,
            "circuit_breaker_open": False,
            "failure_count": 0,
            "cache_size": 0,
            **server_status,
        }

    async def search_regex(
        self,
        pattern: str,
        file_pattern: str | None = None,
    ) -> list[dict[str, t.Any]]:
        payload = await self._call_tool(
            "pycharm_search_in_project",
            {"pattern": pattern, "file_pattern": file_pattern},
        )
        return self._extract_list(payload, "results")

    async def replace_text_in_file(
        self,
        file_path: str,
        search_text: str,
        replace_text: str,
    ) -> bool:
        payload = await self._call_tool(
            "pycharm_replace_in_file",
            {
                "file_path": file_path,
                "search_text": search_text,
                "replace_text": replace_text,
            },
        )
        return bool(payload.get("replaced", False))

    async def get_file_problems(
        self,
        file_path: str,
        errors_only: bool = False,
    ) -> list[dict[str, t.Any]]:
        payload = await self._call_tool(
            "pycharm_run_diagnostics",
            {"file_path": file_path, "errors_only": errors_only},
        )
        return self._extract_list(payload, "problems")

    async def reformat_file(self, file_path: str) -> bool:
        payload = await self._call_tool(
            "pycharm_reformat_file",
            {"file_path": file_path},
        )
        return bool(payload.get("reformatted", False))

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        if not await self.connect():
            raise RuntimeError("Mahavishnu PyCharm MCP server is unavailable")

        if self._session is None:
            raise RuntimeError("Mahavishnu PyCharm MCP session is unavailable")

        result = await asyncio.wait_for(
            self._session.call_tool(tool_name, arguments),
            timeout=self.timeout_seconds,
        )
        return self._normalize_result(result)

    def _normalize_result(self, result: t.Any) -> dict[str, t.Any]:
        if result is None:
            return {}
        if isinstance(result, dict):
            return result
        if hasattr(result, "content"):
            content = getattr(result, "content", None)
            if isinstance(content, list):
                import json

                for item in content:
                    text = getattr(item, "text", None)
                    if not text:
                        continue
                    with suppress(Exception):
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed
                if content:
                    return {"content": content}
        return {"result": result}

    def _extract_list(
        self, payload: dict[str, t.Any], key: str
    ) -> list[dict[str, t.Any]]:
        value = payload.get(key, [])
        return value if isinstance(value, list) else []
