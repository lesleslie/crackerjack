"""CrackerjackCLI — BodaiCLIBase subclass for the crackerjack CLI entrypoint.

Adopts oneiric 0.19.0's :class:`oneiric.cli.base.BodaiCLIBase` as the
foundation for the crackerjack CLI. Adds REAL ``_doctor_checks()`` and
``_health_probe()`` implementations that call into crackerjack's existing
health surface (``crackerjack.cli.handlers.health``) — not stub returns.

This file deliberately avoids ``logging.Logger.exception(component=...)`` —
``ty`` strict type checker rejects the kwarg. We use ``extra={"component":
self.component_name}`` per project CLAUDE.md guidance.
"""

from __future__ import annotations

import logging
import typing as t
from pathlib import Path
from typing import Any

from mcp_common.cli import MCPServerCLIFactory
from oneiric.cli.base import BodaiCLIBase

logger = logging.getLogger(__name__)


class CrackerjackCLI(BodaiCLIBase):
    """BodaiCLIBase subclass for the crackerjack CLI.

    Wires in version/doctor/health global commands from :class:`BodaiCLIBase`
    and the legacy MCP server lifecycle commands (start/stop/restart/status)
    from :class:`MCPServerCLIFactory`. Doctor and health checks are real — they
    delegate to ``crackerjack.cli.handlers.health`` instead of stubbing.
    """

    def __init__(
        self,
        *,
        start_handler: t.Callable[[], None] | None = None,
        stop_handler: t.Callable[..., None] | None = None,
        health_probe_handler: t.Callable[[], Any] | None = None,
        help: str | None = "Crackerjack MCP Server CLI",
        **kwargs: Any,
    ) -> None:
        super().__init__(component_name="crackerjack", help=help, **kwargs)
        self._register_lifecycle_commands(
            start_handler=start_handler,
            stop_handler=stop_handler,
            health_probe_handler=health_probe_handler,
        )

    # ------------------------------------------------------------------
    # Lifecycle commands (start/stop/restart/status) inherited from
    # MCPServerCLIFactory. We compose rather than copy the factory so
    # upstream bug fixes flow through automatically.
    # ------------------------------------------------------------------
    def _register_lifecycle_commands(
        self,
        *,
        start_handler: t.Callable[[], None] | None,
        stop_handler: t.Callable[..., None] | None,
        health_probe_handler: t.Callable[[], Any] | None,
    ) -> None:
        factory = MCPServerCLIFactory(
            server_name="crackerjack",
            start_handler=start_handler,
            stop_handler=stop_handler,
            health_probe_handler=health_probe_handler,
        )
        lifecycle_app = factory.create_app()

        # BodaiCLIBase already provides `health` (calls our _health_probe
        # override). Drop the factory's `health` command to avoid the
        # Typer duplicate-command error.
        for typer_info in getattr(lifecycle_app, "registered_commands", []):
            # Skip the factory's "health" command so BodaiCLIBase's is canonical.
            if getattr(typer_info, "name", None) == "health":
                continue
            self.registered_commands.append(typer_info)

        for typer_info in getattr(lifecycle_app, "registered_groups", []):
            self.registered_groups.append(typer_info)

    # ------------------------------------------------------------------
    # BodaiCLIBase subclass hooks — REAL checks, not stubs.
    # ------------------------------------------------------------------
    def _doctor_checks(self) -> dict[str, Any]:
        """Run doctor checks via the existing crackerjack health handlers.

        Returns a non-empty dict with one entry per category
        (adapters/managers/services). Each entry contains a ``status`` and
        ``detail`` field that the global ``doctor`` command renders.
        """
        from crackerjack.cli.handlers.health import (
            _check_adapters,
            _check_managers,
            _check_services,
        )

        pkg_path = Path.cwd()
        checks: dict[str, Any] = {}

        for label, fn in (
            ("adapters", _check_adapters),
            ("managers", _check_managers),
            ("services", _check_services),
        ):
            try:
                health = fn(pkg_path)
            except Exception as exc:
                logger.exception(
                    "doctor-category-failed",
                    extra={"component": self.component_name, "category": label},
                )
                checks[label] = {
                    "status": "unhealthy",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
                continue
            checks[label] = {
                "status": str(health.overall_status.value),
                "detail": (
                    f"total={health.total} healthy={health.healthy} "
                    f"degraded={health.degraded} unhealthy={health.unhealthy}"
                ),
                "total": health.total,
                "healthy": health.healthy,
                "degraded": health.degraded,
                "unhealthy": health.unhealthy,
            }
        return checks

    def _health_probe(self) -> dict[str, Any]:
        """Probe crackerjack runtime health via the existing handler.

        Returns a real snapshot (not the UNAVAILABLE-stub from
        :class:`BodaiCLIBase`). The ``status`` field reflects whether the
        underlying handle_health_check returned a zero exit code.
        """
        from crackerjack.cli.handlers.health import handle_health_check

        pkg_path = Path.cwd()
        try:
            exit_code = handle_health_check(pkg_path=pkg_path, quiet=True)
        except Exception as exc:
            logger.exception(
                "health-probe-failed",
                extra={"component": self.component_name},
            )
            return {
                "status": "unhealthy",
                "component": self.component_name,
                "version": self.component_version,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "status": "healthy" if exit_code == 0 else "degraded",
            "exit_code": exit_code,
            "component": self.component_name,
            "version": self.component_version,
        }


__all__ = ["CrackerjackCLI"]
