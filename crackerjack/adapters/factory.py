"""Default adapter factory for crackerjack.

This module provides the factory implementation for creating adapter instances,
following the protocol-based architecture.
"""

import logging
import typing as t
from pathlib import Path

from crackerjack.models.protocols import AdapterFactoryProtocol, AdapterProtocol

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from crackerjack.config.settings import CrackerjackSettings


class DefaultAdapterFactory(AdapterFactoryProtocol):
    """Default factory for creating adapter instances.

    This factory creates adapter instances by name, providing a single
    point of control for adapter instantiation and enabling dependency injection.

    Thread Safety:
        Thread-safe for adapter creation.

    Example:
        ```python
        factory = DefaultAdapterFactory()
        ruff = factory.create_adapter("Ruff", settings)
        await ruff.init()
        ```
    """

    def __init__(
        self,
        settings: t.Any | None = None,
        pkg_path: Path | None = None,
    ) -> None:
        """Initialize the adapter factory.

        Args:
            settings: Optional settings for adapter configuration.
            pkg_path: Optional package path for adapter context.

        Example:
            ```python
            factory = DefaultAdapterFactory(settings=settings, pkg_path=Path.cwd())
            ```
        """
        self.settings = settings
        self.pkg_path = pkg_path or Path.cwd()

    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> AdapterProtocol:
        """Create an adapter instance by name.

        Args:
            adapter_name: Name of the adapter to create.
            settings: Optional settings for the adapter.

        Returns:
            An adapter instance.

        Raises:
            ValueError: If adapter name is unknown.

        Example:
            ```python
            adapter = factory.create_adapter("Ruff", ruff_settings)
            assert isinstance(adapter, AdapterProtocol)
            ```
        """
        # QA Tool Adapters (BaseToolAdapter subclasses)
        if adapter_name == "Ruff":
            from crackerjack.adapters.format.ruff import RuffAdapter

            return RuffAdapter(settings)
        if adapter_name == "Bandit":
            from crackerjack.adapters.sast.bandit import BanditAdapter

            return BanditAdapter(settings)
        if adapter_name == "Semgrep":
            from crackerjack.adapters.sast.semgrep import SemgrepAdapter

            return SemgrepAdapter(settings)
        if adapter_name == "Refurb":
            from crackerjack.adapters.refactor.refurb import RefurbAdapter

            return RefurbAdapter(settings)
        if adapter_name == "Skylos":
            from crackerjack.adapters.refactor.skylos import SkylosAdapter

            return SkylosAdapter(settings)

        # LSP Adapters (BaseRustToolAdapter subclasses - need context)
        if adapter_name == "Zuban":
            from crackerjack.adapters.lsp.zuban import ZubanAdapter
            from crackerjack.config.execution import ExecutionContext

            # LSP adapters require execution context
            context = ExecutionContext(
                pkg_path=self.pkg_path,
                settings=self.settings,
            )
            return t.cast(AdapterProtocol, ZubanAdapter(context))

        # AI Adapters (BaseCodeFixer subclasses)
        if adapter_name == "Claude AI":
            from crackerjack.adapters.ai.claude import ClaudeCodeFixer

            return t.cast(AdapterProtocol, ClaudeCodeFixer(settings))

        raise ValueError(f"Unknown adapter: {adapter_name}")
