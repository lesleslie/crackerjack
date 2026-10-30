"""XDG Base Directory resolution for Session-Buddy owned runtime data.

Session-Buddy's runtime data used to live under ``~/.claude/data`` — a
Claude-Code-specific directory.  Storing it there asserts that Claude Code
owns the data, but Session-Buddy is harness-agnostic.  These helpers resolve
the XDG Base Directory locations instead:

* ``$XDG_DATA_HOME/session-buddy``   — persistent data
* ``$XDG_STATE_HOME/session-buddy``  — state
* ``$XDG_CACHE_HOME/session-buddy``  — regenerable caches
* ``$XDG_CONFIG_HOME/session-buddy`` — settings

The data owner is always ``session-buddy``, even in a repository that merely
consumes Session-Buddy's data — the consuming repository's own app name is
never used for Session-Buddy's files.

Every repository carries its own copy of this module.  crackerjack,
session-buddy and mahavishnu are released (non-editable) installs of one
another, so a cross-repo import would need a publish first; duplicating a
~20 line module is the accepted cost of not gating the move on a release.

The module is dependency-free and side-effect free: importing it creates no
directories and writes nothing.  Paths are resolved on every call, so a test
can override ``HOME`` and the ``XDG_*`` variables at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["cache_dir", "config_dir", "data_dir", "state_dir"]


def _xdg_root(env_var: str, fallback: str) -> Path:
    """Resolve one XDG base directory root.

    Args:
        env_var: Name of the environment variable holding the root.
        fallback: Home-relative fallback used when the variable is unset.

    Returns:
        The configured root, or the expanded fallback.  ``os.path.expanduser``
        is used rather than ``Path.home()`` so that overriding ``HOME`` in a
        test moves the fallback with it.
    """
    configured = os.environ.get(env_var)
    if configured:
        return Path(os.path.expanduser(configured))
    return Path(os.path.expanduser(fallback))


def data_dir(app: str = "session-buddy") -> Path:
    """Return the XDG data directory for *app*.

    Args:
        app: The data owner's application name.

    Returns:
        ``$XDG_DATA_HOME/<app>``, falling back to ``~/.local/share/<app>``.
    """
    return _xdg_root("XDG_DATA_HOME", "~/.local/share") / app


def state_dir(app: str = "session-buddy") -> Path:
    """Return the XDG state directory for *app*.

    Args:
        app: The data owner's application name.

    Returns:
        ``$XDG_STATE_HOME/<app>``, falling back to ``~/.local/state/<app>``.
    """
    return _xdg_root("XDG_STATE_HOME", "~/.local/state") / app


def cache_dir(app: str = "session-buddy") -> Path:
    """Return the XDG cache directory for *app*.

    Args:
        app: The data owner's application name.

    Returns:
        ``$XDG_CACHE_HOME/<app>``, falling back to ``~/.cache/<app>``.
    """
    return _xdg_root("XDG_CACHE_HOME", "~/.cache") / app


def config_dir(app: str = "session-buddy") -> Path:
    """Return the XDG config directory for *app*.

    Args:
        app: The data owner's application name.

    Returns:
        ``$XDG_CONFIG_HOME/<app>``, falling back to ``~/.config/<app>``.
    """
    return _xdg_root("XDG_CONFIG_HOME", "~/.config") / app
