import logging
import typing as t
from pathlib import Path

from crackerjack.models.protocols import AdapterFactoryProtocol, AdapterProtocol

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    pass


class DefaultAdapterFactory(AdapterFactoryProtocol):
    def __init__(
        self,
        settings: t.Any | None = None,
        pkg_path: Path | None = None,
    ) -> None:
        self.settings = settings
        self.pkg_path = pkg_path or Path.cwd()

    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> AdapterProtocol:
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

        if adapter_name == "Zuban":
            from crackerjack.adapters.lsp.zuban import ZubanAdapter
            from crackerjack.config.execution import ExecutionContext

            context = ExecutionContext(
                pkg_path=self.pkg_path,
                settings=self.settings,
            )
            return t.cast(AdapterProtocol, ZubanAdapter(context))

        if adapter_name == "Claude AI":
            from crackerjack.adapters.ai.claude import ClaudeCodeFixer

            return t.cast(AdapterProtocol, ClaudeCodeFixer())

        raise ValueError(f"Unknown adapter: {adapter_name}")
