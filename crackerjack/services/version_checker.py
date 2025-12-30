import subprocess
import typing as t
from dataclasses import dataclass

import aiohttp

from crackerjack.core.retry import retry_api_call


@dataclass
class VersionInfo:
    tool_name: str
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    error: str | None = None


class VersionChecker:
    def __init__(self) -> None:
        self.console = console
        self.tools_to_check = {
            "ruff": self._get_ruff_version,
            "pyright": self._get_pyright_version,
            "uv": self._get_uv_version,
        }

    async def check_tool_updates(self) -> dict[str, VersionInfo]:
        results = {}
        for tool_name, version_getter in self.tools_to_check.items():
            results[tool_name] = await self._check_single_tool(
                tool_name, version_getter
            )
        return results

    async def _check_single_tool(
        self, tool_name: str, version_getter: t.Callable[[], str | None]
    ) -> VersionInfo:
        try:
            current_version = version_getter()
            if current_version:
                latest_version = await self._fetch_latest_version(tool_name)
                return self._create_installed_version_info(
                    tool_name, current_version, latest_version
                )
            else:
                return self._create_missing_tool_info(tool_name)
        except Exception as e:
            return self._create_error_version_info(tool_name, e)

    def _create_installed_version_info(
        self, tool_name: str, current_version: str, latest_version: str | None
    ) -> VersionInfo:
        update_available = (
            latest_version is not None
            and self._version_compare(current_version, latest_version) < 0
        )

        if update_available:
            self.console.print(
                f"[yellow]🔄 {tool_name} update available: "
                f"{current_version} → {latest_version}[/ yellow]"
            )

        return VersionInfo(
            tool_name=tool_name,
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
        )

    def _create_missing_tool_info(self, tool_name: str) -> VersionInfo:
        self.console.print(f"[red]⚠️ {tool_name} not installed[/ red]")
        return VersionInfo(
            tool_name=tool_name,
            current_version="not installed",
            error=f"{tool_name} not found or not installed",
        )

    def _create_error_version_info(
        self, tool_name: str, error: Exception
    ) -> VersionInfo:
        self.console.print(f"[red]❌ Error checking {tool_name}: {error}[/ red]")
        return VersionInfo(
            tool_name=tool_name,
            current_version="unknown",
            error=str(error),
        )

    def _get_ruff_version(self) -> str | None:
        return self._get_tool_version("ruff")

    def _get_pyright_version(self) -> str | None:
        return self._get_tool_version("pyright")

    def _get_uv_version(self) -> str | None:
        return self._get_tool_version("uv")

    def _get_tool_version(self, tool_name: str) -> str | None:
        try:
            result = subprocess.run(
                [tool_name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version_line = result.stdout.strip()
                return version_line.split()[-1] if version_line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    @retry_api_call(max_attempts=3, delay=1.0, backoff=2.0, max_delay=30.0)
    async def _fetch_latest_version(self, tool_name: str) -> str | None:
        try:
            # Fix URLs - remove spaces that were added
            pypi_urls = {
                "ruff": "https://pypi.org/pypi/ruff/json",
                "pyright": "https://pypi.org/pypi/pyright/json",
                "uv": "https://pypi.org/pypi/uv/json",
            }

            url = pypi_urls.get(tool_name)
            if not url:
                return None

            timeout = aiohttp.ClientTimeout(total=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data: dict[str, t.Any] = await response.json()
                    return data.get("info", {}).get("version")

        except Exception:
            return None

    def _version_compare(self, current: str, latest: str) -> int:
        try:
            current_parts, current_len = self._parse_version_parts(current)
            latest_parts, latest_len = self._parse_version_parts(latest)

            normalized_current, normalized_latest = self._normalize_version_parts(
                current_parts, latest_parts
            )

            numeric_result = self._compare_numeric_parts(
                normalized_current, normalized_latest
            )
            if numeric_result != 0:
                return numeric_result

            return self._handle_length_differences(
                current_len, latest_len, normalized_current, normalized_latest
            )

        except (ValueError, AttributeError):
            return 0

    def _parse_version_parts(self, version: str) -> tuple[list[int], int]:
        parts = [int(x) for x in version.split(".")]
        return parts, len(parts)

    def _normalize_version_parts(
        self, current_parts: list[int], latest_parts: list[int]
    ) -> tuple[list[int], list[int]]:
        max_len = max(len(current_parts), len(latest_parts))
        current_normalized = current_parts + [0] * (max_len - len(current_parts))
        latest_normalized = latest_parts + [0] * (max_len - len(latest_parts))
        return current_normalized, latest_normalized

    def _compare_numeric_parts(
        self, current_parts: list[int], latest_parts: list[int]
    ) -> int:
        for current_part, latest_part in zip(current_parts, latest_parts):
            if current_part < latest_part:
                return -1
            if current_part > latest_part:
                return 1
        return 0

    def _handle_length_differences(
        self,
        current_len: int,
        latest_len: int,
        current_parts: list[int],
        latest_parts: list[int],
    ) -> int:
        if current_len == latest_len:
            return 0

        if current_len < latest_len:
            return self._compare_when_current_shorter(
                current_len, latest_len, latest_parts
            )
        return self._compare_when_latest_shorter(latest_len, current_len, current_parts)

    def _compare_when_current_shorter(
        self, current_len: int, latest_len: int, latest_parts: list[int]
    ) -> int:
        extra_parts = latest_parts[current_len:]
        if any(part != 0 for part in extra_parts):
            return -1

        return -1 if current_len > 1 else 0

    def _compare_when_latest_shorter(
        self, latest_len: int, current_len: int, current_parts: list[int]
    ) -> int:
        extra_parts = current_parts[latest_len:]
        if any(part != 0 for part in extra_parts):
            return 1

        return 1 if latest_len > 1 else 0
