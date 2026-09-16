"""Skill metadata schema (Phase 1 of bodai-skill-agent-distribution plan).

Per docs/superpowers/plans/2026-09-14-dhara-mcp-decomposition-implementation.md
Phase 10 task 4, the canonical skill schema now lives in
``mcp_common.canonical_schemas.skill``. This module is a thin re-export
shim that preserves the legacy ``SkillMetadata`` class name. New code
should import directly from ``mcp_common.canonical_schemas``.

The previous version of this module carried an 18-field model with
B-4 path-traversal allowlist validators (``server`` and ``name``),
``extra="forbid"``, ``str_strip_whitespace=True``, and
``validate_assignment=True`` semantics. All of these now live in
:class:`mcp_common.canonical_schemas.skill.SkillCanonicalSchema`. This
shim preserves ``isinstance(x, SkillMetadata)`` for callers that
import the legacy name.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from mcp_common.canonical_schemas.skill import SkillCanonicalSchema
from mcp_common.canonical_schemas._validators import NAME_OR_SERVER_RE

# Backward-compat alias. ``isinstance(x, SkillMetadata)`` resolves to
# ``isinstance(x, SkillCanonicalSchema)`` because Python treats the
# alias as the same class object.
SkillMetadata = SkillCanonicalSchema


__all__ = ["SkillMetadata", "NAME_OR_SERVER_RE"]
