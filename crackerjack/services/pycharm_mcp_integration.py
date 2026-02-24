"""PyCharm MCP Integration Service.

This service provides integration with PyCharm via the Model Context Protocol (MCP).
It enables IDE-level capabilities like code search, refactoring, and diagnostics.

Security: All inputs are sanitized before use.
Performance: Circuit breaker prevents cascading failures.
"""

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
    """State for circuit breaker pattern."""

    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False

    # Configuration
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def record_success(self) -> None:
        """Record a success and reset the circuit."""
        self.failure_count = 0
        self.is_open = False

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if not self.is_open:
            return True

        # Check if recovery timeout has passed
        elapsed = time.time() - self.last_failure_time
        if elapsed >= self.recovery_timeout:
            logger.info("Circuit breaker entering half-open state")
            return True

        return False


@dataclass
class SearchResult:
    """Result from a search operation."""

    file_path: str
    line_number: int
    column: int
    match_text: str
    context_before: str | None = None
    context_after: str | None = None


class PyCharmMCPAdapter:
    """Adapter for PyCharm MCP server integration.

    This adapter provides a safe, circuit-breaker-protected interface
    to the PyCharm MCP server for IDE-level operations.

    Features:
    - Circuit breaker for fault tolerance
    - Input sanitization for security
    - Timeout handling for responsiveness
    - Caching for performance

    Example:
        adapter = PyCharmMCPAdapter(mcp_client)
        results = await adapter.search_regex(r"# type: ignore")
        for result in results:
            print(f"{result.file_path}:{result.line_number}")
    """

    def __init__(
        self,
        mcp_client: t.Any | None = None,
        timeout: float = 30.0,
        max_results: int = 100,
    ) -> None:
        """Initialize the PyCharm MCP adapter.

        Args:
            mcp_client: The MCP client for communicating with PyCharm.
            timeout: Maximum time to wait for operations (seconds).
            max_results: Maximum number of results to return from searches.
        """
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
        """Search for a regex pattern in the codebase.

        Args:
            pattern: Regex pattern to search for.
            file_pattern: Optional glob pattern to filter files.

        Returns:
            List of search results with file, line, column info.
        """
        # Sanitize pattern
        sanitized_pattern = self._sanitize_regex(pattern)
        if not sanitized_pattern:
            self.logger.warning(f"Invalid regex pattern rejected: {pattern[:50]}")
            return []

        # Check cache
        cache_key = f"search:{sanitized_pattern}:{file_pattern}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Execute search with circuit breaker
        results = await self._execute_with_circuit_breaker(
            self._search_regex_impl,
            sanitized_pattern,
            file_pattern,
        )

        # Cache results
        self._set_cached(cache_key, results, ttl=60.0)

        return results

    async def replace_text_in_file(
        self,
        file_path: str,
        search_text: str,
        replace_text: str,
    ) -> bool:
        """Replace text in a file.

        Args:
            file_path: Path to the file to modify.
            search_text: Text to search for.
            replace_text: Text to replace with.

        Returns:
            True if replacement was successful.
        """
        # Validate file path (no path traversal)
        if not self._is_safe_path(file_path):
            self.logger.warning(f"Unsafe file path rejected: {file_path}")
            return False

        # Execute replacement with circuit breaker
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
        """Get IDE diagnostics for a file.

        Args:
            file_path: Path to the file to check.
            errors_only: If True, only return errors (not warnings).

        Returns:
            List of diagnostic problems.
        """
        # Validate file path
        if not self._is_safe_path(file_path):
            return []

        # Check cache (shorter TTL for diagnostics)
        cache_key = f"problems:{file_path}:{errors_only}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Execute with circuit breaker
        problems = await self._execute_with_circuit_breaker(
            self._get_file_problems_impl,
            file_path,
            errors_only,
        )

        # Cache for short time
        self._set_cached(cache_key, problems, ttl=10.0)

        return problems

    async def reformat_file(self, file_path: str) -> bool:
        """Reformat a file using IDE formatter.

        Args:
            file_path: Path to the file to reformat.

        Returns:
            True if reformatting was successful.
        """
        if not self._is_safe_path(file_path):
            return False

        return await self._execute_with_circuit_breaker(
            self._reformat_file_impl,
            file_path,
        )

    # Implementation methods (protected by circuit breaker)

    async def _search_regex_impl(
        self,
        pattern: str,
        file_pattern: str | None,
    ) -> list[SearchResult]:
        """Implementation of regex search."""
        if not self._mcp:
            return self._fallback_search(pattern, file_pattern)

        try:
            # Call MCP tool
            results = await asyncio.wait_for(
                self._mcp.search_regex(
                    pattern=pattern,
                    file_pattern=file_pattern,
                ),
                timeout=self._timeout,
            )

            # Convert to SearchResult objects
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
        """Implementation of text replacement."""
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
        """Implementation of getting file problems."""
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
        """Implementation of file reformatting."""
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

    # Fallback methods (when MCP is not available)

    def _fallback_search(
        self,
        pattern: str,
        file_pattern: str | None,
    ) -> list[SearchResult]:
        """Fallback search using grep when MCP is not available."""
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
        """Fallback replacement using file I/O when MCP is not available."""
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

    # Utility methods

    def _sanitize_regex(self, pattern: str) -> str:
        """Sanitize a regex pattern to prevent ReDoS.

        Args:
            pattern: The regex pattern to sanitize.

        Returns:
            Sanitized pattern, or empty string if invalid.
        """
        # Reject patterns that are too long
        if len(pattern) > 500:
            return ""

        # Reject patterns with obvious ReDoS patterns
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

        # Try to compile the pattern to verify it's valid
        try:
            re.compile(pattern)
            return pattern
        except re.error:
            return ""

    def _is_safe_path(self, file_path: str) -> bool:
        """Check if a file path is safe (no path traversal).

        Args:
            file_path: The file path to check.

        Returns:
            True if the path is safe.
        """
        # Reject empty paths
        if not file_path:
            return False

        # Reject absolute paths outside project
        if file_path.startswith("/"):
            # Only allow /tmp for testing
            if not file_path.startswith("/tmp"):
                return False

        # Reject path traversal attempts
        if ".." in file_path:
            return False

        # Reject paths with null bytes
        if "\x00" in file_path:
            return False

        return True

    async def _execute_with_circuit_breaker(
        self,
        func: t.Callable[..., t.Awaitable[t.Any]],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute a function with circuit breaker protection.

        Args:
            func: The async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The function result, or default value on failure.
        """
        if not self._circuit_breaker.can_execute():
            self.logger.debug("Circuit breaker is open, skipping operation")
            return []  # Default empty result

        try:
            result = await func(*args, **kwargs)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            self.logger.error(f"Operation failed (circuit breaker): {e}")
            raise

    # Cache methods

    def _get_cached(self, key: str) -> t.Any | None:
        """Get a cached value if not expired."""
        if key in self._cache:
            expiry = self._cache_ttl.get(key, 0)
            if time.time() < expiry:
                return self._cache[key]
            else:
                # Remove expired entry
                del self._cache[key]
                self._cache_ttl.pop(key, None)
        return None

    def _set_cached(self, key: str, value: t.Any, ttl: float = 60.0) -> None:
        """Set a cached value with TTL."""
        self._cache[key] = value
        self._cache_ttl[key] = time.time() + ttl

    def clear_cache(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._cache_ttl.clear()

    # Health check

    async def health_check(self) -> dict[str, t.Any]:
        """Check the health of the MCP connection.

        Returns:
            Dictionary with health status information.
        """
        return {
            "mcp_available": self._mcp is not None,
            "circuit_breaker_open": self._circuit_breaker.is_open,
            "failure_count": self._circuit_breaker.failure_count,
            "cache_size": len(self._cache),
        }
