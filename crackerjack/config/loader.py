from __future__ import annotations

import asyncio
import logging
import os
import typing as t
from pathlib import Path
from typing import TypeVar

from pydantic.main import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def crackerjack_env_overlay[T: BaseModel](settings_class: type[T]) -> dict[str, t.Any]:
    """Convert ``CRACKERJACK_*`` env vars into a nested-dict overlay.

    Mirrors Mahavishnu's ``_mahavishnu_env_overlay`` at
    ``mahavishnu/core/config.py:3209`` (REQ-006). Returns only top-level keys
    that exist in ``settings_class.model_fields``. Nested keys (separated
    by ``__``) are merged into per-section sub-dicts.
    """
    overlay: dict[str, t.Any] = {}
    for key, value in os.environ.items():
        if not key.startswith("CRACKERJACK_"):
            continue
        suffix = key[len("CRACKERJACK_") :]
        if "__" in suffix:
            section, leaf = suffix.split("__", 1)
            section_lower = section.lower()
            if section_lower in settings_class.model_fields:
                sub = overlay.setdefault(section_lower, {})
                if isinstance(sub, dict):
                    sub[leaf.lower()] = value
            continue
        flat = suffix.lower()
        if flat in settings_class.model_fields:
            overlay[flat] = value
    return overlay


def _merge_env_overlay(merged: dict[str, t.Any], env_overlay: dict[str, t.Any]) -> None:
    """Merge per-key for nested sections (avoid clobbering YAML siblings)."""
    for key, value in env_overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key].update(value)
        else:
            merged[key] = value


def load_settings_for_project[T: BaseModel](
    project_root: Path,
    settings_class: type[T],
) -> T:
    """Resolve ``settings_class`` via Oneiric with an explicit ``project_root``.

    Use this when the caller is not CWD'd at the project root. The
    one-pass-CWD ``load_settings(settings_class)`` is the common path;
    this sibling covers lifecycle adapters and worker-pool dispatchers
    that need an explicit anchor (R6.3 follow-up to the pre-1.0
    ``settings_dir`` removal).

    Precedence (highest -> lowest):

    1. ``CRACKERJACK_*`` env vars (applied last via ``crackerjack_env_overlay``)
    2. ``publishing.publish_url`` synthesised from
       ``$BODAI_ECOSYSTEM_CONFIG`` (when ``project_root`` matches a
       registered repo) - REQ-005
    3. XDG user-local override (via Oneiric's ``load_settings``)
    4. XDG user config (via Oneiric's ``load_settings``)
    5. ``<project_root>/settings/local.yaml`` (via Oneiric)
    6. ``<project_root>/settings/{project_name}.yaml`` (via Oneiric)
    7. Code defaults

    Falls back to a defaults-only construction when Oneiric is unavailable
    (early import or test setup without the dependency); see plan sec 6.5.
    """
    merged: dict[str, t.Any] = {}
    try:
        from oneiric.core.config import load_settings as _oneiric_load

        oneiric_obj = _oneiric_load(
            project_name="crackerjack",
            project_root=project_root,
        )
        # ``extras`` only contains keys NOT declared on ``OneiricSettings``
        # (declared fields like ``adapters``, ``services``, ``tasks`` live
        # on the OneiricSettings instance itself). The
        # ``extra="ignore"`` on ``CrackerjackSettings`` (via
        # ``OneiricMCPConfig``) drops anything not in
        # ``CrackerjackSettings.model_fields``, so forwarding ALL extras
        # is safe. Critically, this lets top-level ``*_timeout`` keys
        # reach the ``_reshape_adapter_timeouts`` validator (REQ-004) —
        # dropping them in the per-key filter would silently lose the
        # timeout value (R6.2). The ``if v is not None`` check still
        # strips spurious nulls.
        extras = getattr(oneiric_obj, "__pydantic_extra__", None) or {}
        merged = {k: v for k, v in extras.items() if v is not None}
    except Exception:
        # Oneiric unavailable (early import, test setup without the
        # dependency). Mirror Mahavishnu's fallback at
        # ``mahavishnu/core/config.py:3192-3199`` - never raise purely on a
        # missing loader; pydantic-settings still reads env vars natively.
        logger.exception("crackerjack.config.oneiric_loader_failed_falling_back")

    # Ecosystem publish-url synthesis sits between Oneiric's resolution
    # and the CRACKERJACK_* env overlay (REQ-005). Slot rationale: CLI
    # flag and env var beat this; YAML beats this; this sits between.
    from .ecosystem_synthesis import apply_ecosystem_publish_synthesis

    apply_ecosystem_publish_synthesis(merged, project_root)

    # Apply CRACKERJACK_* env vars as final overlay (REQ-006).
    env_overlay = crackerjack_env_overlay(settings_class)
    _merge_env_overlay(merged, env_overlay)

    return settings_class(**merged)


def load_settings[T: BaseModel](
    settings_class: type[T],
) -> T:
    """CWD-relative entry point; delegate to ``load_settings_for_project``.

    Pre-migration this function accepted ``settings_dir: Path | None``.
    That argument is dropped per pre-1.0 policy
    (`~/.claude/.../feedback-no-backwards-compat-pre-1.0.md`); callers
    that need a specific anchor use ``load_settings_for_project``.
    """
    return load_settings_for_project(Path.cwd(), settings_class)


async def load_settings_async[T: BaseModel](
    settings_class: type[T],
) -> T:
    # Body-rebind guard for ty: ``asyncio.to_thread(load_settings, ...)``
    # returns ``T@load_settings``, which ty cannot unify with this
    # function's outer ``T`` even though they're bound to the same
    # ``settings_class`` input. The inner closure's explicit ``-> T``
    # gives ty a single concrete return type to bind, which then
    # propagates through ``to_thread``. See feedback-ty-narrowing-pattern.
    def _load() -> T:
        return load_settings(settings_class)

    return await asyncio.to_thread(_load)
