"""Pydantic validators for CrackerjackSettings.

Bespoke load-time behaviors that previously lived in
``crackerjack/config/loader.py`` are promoted here so they sit next to the
schema they validate. REQ-004 (timeout reshape) and REQ-003 (unknown
pyproject subtable warning) are implemented as Pydantic v2
``model_validator``s.

These run inside ``CrackerjackSettings`` construction regardless of which
loader path is used, so behavior parity holds across the loader-rewrite in
Phase 2 of the migration plan.
"""

from __future__ import annotations

import logging
import typing as t

logger = logging.getLogger(__name__)


def reshape_adapter_timeouts(data: t.Any) -> t.Any:
    """Reshape top-level ``*_timeout`` scalars into ``adapter_timeouts`` sub-dict.

    REQ-004. Returns the data unchanged when ``data`` is not a dict
    (Pydantic may pass a model instance on validation of nested fields).
    """
    if not isinstance(data, dict):
        return data
    timeouts = {k: v for k, v in data.items() if k.endswith("_timeout")}
    if not timeouts:
        return data
    bucket = data.setdefault("adapter_timeouts", {})
    if not isinstance(bucket, dict):
        # ``adapter_timeouts`` was a Pydantic model instance by then. We can't
        # mutate it from a non-dict; let Pydantic raise to surface the misconfig.
        logger.warning(
            "crackerjack.settings.adapter_timeouts_reshape_skipped: existing "
            "value is not a dict (%s); *_timeout keys will fall through to "
            "the field validator and be rejected",
            type(bucket).__name__,
        )
        return data
    bucket.update(timeouts)
    for k in timeouts:
        data.pop(k, None)
    return data


# _KNOWN_PYPROJECT_SUBTABLES now lives in settings.py (Task 1). Import lazily
# to avoid a circular import.
def warn_unknown_pyproject_subtables(instance: t.Any) -> t.Any:
    """Surface misplaced ``[tool.crackerjack.X]`` blocks at WARNING.

    REQ-003. Reads ``pyproject.toml`` from the CWD and iterates
    ``tool.crackerjack`` sub-tables; any key not in
    ``_KNOWN_PYPROJECT_SUBTABLES`` triggers a WARNING.

    The current ``crackerjack/config/loader.py:78-108`` warns on this
    pre-merge; the validator here runs post-merge, so the warning
    text and observable shape change slightly. See plan §5.3
    "Trade-off accepted".
    """
    from pathlib import Path

    from .settings import _KNOWN_PYPROJECT_SUBTABLES

    try:
        import tomllib
    except ImportError:
        return instance
    pyproject_path = Path.cwd() / "pyproject.toml"
    if not pyproject_path.is_file():
        return instance
    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
    except OSError:
        return instance
    crackerjack_section = data.get("tool", {}).get("crackerjack", {})
    if not isinstance(crackerjack_section, dict):
        return instance
    for key, value in crackerjack_section.items():
        if not isinstance(value, dict):
            continue  # top-level scalar; Pydantic model handles
        if key in _KNOWN_PYPROJECT_SUBTABLES:
            continue
        logger.warning(
            "[tool.crackerjack.%s] block in pyproject.toml is not declared "
            "on CrackerjackSettings. If you meant to configure the %r hook, "
            "check its auto-discovery mechanism (e.g. .betterleaks.toml, "
            ".lycheeignore, .gitleaks.toml) rather than pyproject.toml. "
            "Known [tool.crackerjack.X] sub-tables: %s.",
            key,
            key,
            sorted(_KNOWN_PYPROJECT_SUBTABLES),
        )
    return instance
