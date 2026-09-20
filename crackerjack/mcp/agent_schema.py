"""Agent metadata schema (Phase 3 of bodai-skill-agent-distribution plan).

Per docs/superpowers/plans/2026-09-14-dhara-mcp-decomposition-implementation.md
Phase 10 task 4, the canonical agent schema now lives in
``mcp_common.canonical_schemas.agent``. This module is a thin re-export
shim that preserves the legacy ``AgentMetadata`` class name and adds
crackerjack-specific validators on top.

Crackerjack-specific additions (kept local; not in canonical):

- ``_validate_system_prompt`` (non-empty) — B-6 contract per plan §11.
  The canonical schema allows empty ``system_prompt`` (the
  agents_tools layer normally rejects empty bodies before signing);
  crackerjack's stricter contract requires the body at the schema
  layer so a server cannot accidentally advertise a body-less agent.
- ``_validate_last_reviewed`` (YYYY-MM-DD) — optional ISO date format
  on the audit field.

The local tests (which exercise both validators) keep their legacy
behavior via this subclass. Other components that don't enforce these
invariants at the schema layer can import
``AgentCanonicalSchema`` directly.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

from mcp_common.canonical_schemas._validators import NAME_OR_SERVER_RE
from mcp_common.canonical_schemas.agent import AgentCanonicalSchema
from pydantic import field_validator


class AgentMetadata(AgentCanonicalSchema):
    """Crackerjack's strict variant of the canonical AgentCanonicalSchema.

    Adds two crackerjack-specific validators on top of the canonical
    schema. The B-4 allowlist + id-shape validators are inherited from
    the canonical schema; only the system-prompt non-empty check and
    the last_reviewed ISO-date check are local.
    """

    @field_validator("system_prompt")
    @classmethod
    def _validate_system_prompt(cls, value: str) -> str:
        """B-6 (crackerjack): ``system_prompt`` must be non-empty.

        The Phase 3 plan's critical fix — without a body, the
        installed agent is non-functional. We enforce non-empty here
        at the schema layer so a server cannot accidentally advertise
        a body-less agent.
        """
        if not value.strip():
            raise ValueError("system_prompt must be non-empty")
        return value

    @field_validator("last_reviewed")
    @classmethod
    def _validate_last_reviewed(cls, value: str | None) -> str | None:
        """``last_reviewed`` must look like YYYY-MM-DD when set.

        We don't use ``datetime`` because the field is intentionally
        date-only (no timezone, no time component). The validator
        only fires when the field is non-None.
        """
        if value is None:
            return value
        # YYYY-MM-DD — strict length + dash positions.
        if len(value) != 10 or value[4] != "-" or value[7] != "-":
            raise ValueError(f"last_reviewed {value!r} must be ISO date YYYY-MM-DD")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        """Crackerjack strict contract: ``description`` must be non-empty.

        The canonical schema permits an empty description (the
        agents_tools layer normally rejects empty descriptions before
        signing); crackerjack's stricter contract requires non-empty
        at the schema layer so a server cannot advertise a
        description-less agent.
        """
        if not value.strip():
            raise ValueError("description must be non-empty")
        return value

    @field_validator("id")
    @classmethod
    def _validate_id_shape(cls, value: str) -> str:
        """Crackerjack strict contract: ``id`` must be non-empty AND valid.

        Adds the canonical id-shape checks (3 colon-separated parts;
        server_key + name match the B-4 allowlist; version is a
        non-empty / non-``..`` substring) on top of the canonical
        envelope. The canonical schema permits an empty ``id``; we
        reject it here so a server cannot advertise a key-less agent.
        """
        if not value:
            raise ValueError("id must be non-empty")
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"id {value!r} must be 'server_key:name:version' "
                "(exactly 3 colon-separated parts)"
            )
        server_key, name, version = parts
        if not NAME_OR_SERVER_RE.fullmatch(server_key):
            raise ValueError(
                f"id {value!r} has invalid server_key segment {server_key!r}"
            )
        if not NAME_OR_SERVER_RE.fullmatch(name):
            raise ValueError(f"id {value!r} has invalid name segment {name!r}")
        if not version or "/" in version or ".." in version:
            raise ValueError(f"id {value!r} has invalid version segment {version!r}")
        return value


__all__ = ["NAME_OR_SERVER_RE", "AgentCanonicalSchema", "AgentMetadata"]
