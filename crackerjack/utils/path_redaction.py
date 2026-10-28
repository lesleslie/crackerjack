"""Home-directory redaction for user-facing path output.

Deliberately dependency-free: this module imports nothing from
``crackerjack`` so that *any* layer can use it. A helper that lived
alongside the display formatters would drag ``crackerjack.config`` in with
it, and ``crackerjack.config`` reaches back into modules that want to log
paths — a cycle waiting to happen across a fleet-wide sweep.
"""

from __future__ import annotations

from pathlib import Path


def redact_path(path: object) -> str:
    """Render a filesystem path for output without disclosing the account name.

    Paths inside the current user's home directory are rewritten with a
    leading ``~`` (``/Users/example/Projects/oneiric`` -> ``~/Projects/oneiric``)
    so console output and log lines do not leak the OS account name. The
    result stays shell-expandable, so an operator can paste it straight
    into a shell.

    Paths outside the home directory, and relative paths, are returned
    unchanged — they carry no account information.

    The parameter is typed ``object`` because this helper is applied to
    whatever a log or console message happens to interpolate, and that is
    not always a path (``None`` for "no file", an int for a count). A
    non-path value is rendered verbatim — matching what the f-string would
    have produced on its own — so wrapping never changes the message.

    Args:
        path: The value to render.

    Returns:
        The home-relative form when the path is under the home directory,
        otherwise the value rendered as a string.
    """
    text = str(path)
    try:
        candidate = Path(text)
    except ValueError:
        # Embedded null byte or similar — render verbatim.
        return text

    try:
        home = Path.home()
    except RuntimeError:
        # No resolvable home directory — nothing to redact against.
        return text

    try:
        relative = candidate.relative_to(home)
    except ValueError:
        # Not under the home directory, or a relative path.
        return text

    if not relative.parts:
        return "~"
    return f"~/{relative}"
