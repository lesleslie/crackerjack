from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mcp_common.cli import MCPServerSettings

if TYPE_CHECKING:
    from crackerjack.config.settings import CrackerjackSettings


class CrackerjackMCPSettings(MCPServerSettings):
    @classmethod
    def from_crackerjack_settings(
        cls,
        settings: CrackerjackSettings,
        server_name: str = "crackerjack",
    ) -> CrackerjackMCPSettings:
        return cls(
            server_name=server_name,
            cache_root=Path(".oneiric_cache"),
            health_ttl_seconds=60.0,
            log_level="DEBUG" if settings.execution.verbose else "INFO",
            log_file=None,
        )

    @classmethod
    def load_for_crackerjack(
        cls,
        server_name: str = "crackerjack",
    ) -> CrackerjackMCPSettings:
        from crackerjack.config import load_settings
        from crackerjack.config.settings import CrackerjackSettings

        cj_settings = load_settings(CrackerjackSettings)
        return cls.from_crackerjack_settings(cj_settings, server_name=server_name)


__all__ = ["CrackerjackMCPSettings"]
