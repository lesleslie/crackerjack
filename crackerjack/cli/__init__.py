from .coverage_ratchet_cli import app as coverage_ratchet_app
from .handlers import (
    handle_interactive_mode,
    handle_standard_mode,
)
from .options import CLI_OPTIONS, BumpOption, Options, create_options
from .version import get_package_version

__all__ = [
    "CLI_OPTIONS",
    "BumpOption",
    "Options",
    "coverage_ratchet_app",
    "create_options",
    "get_package_version",
    "handle_interactive_mode",
    "handle_standard_mode",
]


def __getattr__(name: str):
    """Lazily expose the umbrella Typer app.

    Phase 5.1: the Bodai ecosystem discovers CLI apps via the
    ``bodai.apps`` entry-point group. The canonical ``app`` object lives in
    ``crackerjack.__main__`` (where the legacy ``[project.scripts]`` runner
    picks it up). Lazy-importing here avoids a hard
    ``crackerjack.cli <-> crackerjack.__main__`` cycle at module-import time.
    """
    if name == "app":
        from crackerjack.__main__ import app as _umbrella_app

        return _umbrella_app
    raise AttributeError(name)
