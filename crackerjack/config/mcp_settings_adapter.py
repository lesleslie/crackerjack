"""MCP Server settings adapter for Crackerjack.

Bridges CrackerjackSettings (Pydantic-based) to MCPServerSettings (Pydantic-based)
for Oneiric CLI factory integration.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mcp_common.cli import MCPServerSettings

if TYPE_CHECKING:
    from crackerjack.config.settings import CrackerjackSettings


class CrackerjackMCPSettings(MCPServerSettings):
    """Adapter bridging CrackerjackSettings to Oneiric MCPServerSettings.

    This adapter allows Crackerjack to use mcp-common's MCPServerCLIFactory
    while maintaining its existing Pydantic-based configuration system. It converts
    between the two formats transparently.

    Architecture:
        CrackerjackSettings (Pydantic, 60+ fields) → CrackerjackMCPSettings → MCPServerCLIFactory
        ├─ Preserves app config (hooks, tests, AI, etc.)
        └─ Provides CLI lifecycle config (PID files, health snapshots)

    Example:
        >>> from crackerjack.config import CrackerjackSettings
        >>> cj_settings = CrackerjackSettings.load()
        >>> mcp_settings = CrackerjackMCPSettings.from_crackerjack_settings(cj_settings)
        >>> print(mcp_settings.pid_path())
        .oneiric_cache/mcp_server.pid
    """

    @classmethod
    def from_crackerjack_settings(
        cls,
        settings: CrackerjackSettings,
        server_name: str = "crackerjack",
    ) -> CrackerjackMCPSettings:
        """Convert CrackerjackSettings to MCPServerSettings format.

        Args:
            settings: Loaded CrackerjackSettings instance
            server_name: Server identifier (default: "crackerjack")

        Returns:
            Converted MCPServerSettings compatible with CLI factory

        Example:
            >>> cj_settings = CrackerjackSettings.load()
            >>> mcp_settings = CrackerjackMCPSettings.from_crackerjack_settings(
            ...     cj_settings
            ... )
            >>> assert mcp_settings.server_name == "crackerjack"
        """
        return cls(
            server_name=server_name,
            cache_root=Path(".oneiric_cache"),  # Oneiric standard cache location
            health_ttl_seconds=60.0,  # Default: 1 minute freshness
            log_level="DEBUG" if settings.execution.verbose else "INFO",
            log_file=None,  # Crackerjack uses stdout logging
        )

    @classmethod
    def load_for_crackerjack(
        cls,
        server_name: str = "crackerjack",
    ) -> CrackerjackMCPSettings:
        """Load settings from CrackerjackSettings singleton.

        This method integrates with Crackerjack's existing settings system,
        loading from Pydantic Settings (settings/crackerjack.yaml + settings/local.yaml).

        Args:
            server_name: Server identifier (default: "crackerjack")

        Returns:
            MCPServerSettings loaded from Crackerjack configuration

        Example:
            >>> settings = CrackerjackMCPSettings.load_for_crackerjack()
            >>> print(settings.server_name)
            crackerjack
        """
        from crackerjack.config import load_settings
        from crackerjack.config.settings import CrackerjackSettings

        cj_settings = load_settings(CrackerjackSettings)
        return cls.from_crackerjack_settings(cj_settings, server_name=server_name)


__all__ = ["CrackerjackMCPSettings"]
