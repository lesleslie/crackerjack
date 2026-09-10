"""Skill metadata schema (Phase 1 of bodai-skill-agent-distribution plan).

Defines :class:`SkillMetadata`, the canonical Pydantic v2 model for skill
metadata advertised by every Bodai MCP server. The model is identical
across all 5 replicas (akosha, mahavishnu, session-buddy, dhara,
crackerjack) and is the wire shape returned by ``mcp__<server>__list_skills``
and embedded in ``mcp__<server>__get_skill`` responses.

Schema ownership
----------------

Per plan §10.3.5, the schema is canonical across all 5 servers. Two valid
ownership models are documented in the plan: cross-repo import (each
server depends on ``akosha>=0.15.1`` and imports
``from akosha.mcp.skill_schema import SkillMetadata``) or per-server copy.
This file IS the canonical source (sed-replicated from akosha commit
``4951ee8`` 2026-09-10); other servers either import it directly or
copy its contents verbatim.

Path-traversal allowlist (B-4)
-----------------------------

Per plan §5 task #4 and §11 B-4, ``name`` and ``server`` fields are
constrained to a strict allowlist that prevents path-traversal attacks
via server-supplied metadata. The regex forbids:

- ``/`` (anywhere)
- leading ``.`` (cannot start with a dot)
- uppercase characters
- any character outside ``[a-z0-9._-]``
- total length > 63 (the regex ``{0,62}`` after the first char)

The brief additionally requires forbidding the literal substring ``..``
defense-in-depth, so the validator runs an extra explicit check for
that pattern.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Strict allowlist regex per B-4 / plan §5 task #4. Anchored to the
# full string. The first character is one lowercase letter or digit;
# the remaining 0..62 characters are drawn from ``[a-z0-9._-]``. Total
# length is therefore 1..63 characters (the brief's unit test asserts
# that 64 chars is rejected).
_NAME_OR_SERVER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


class SkillMetadata(BaseModel):
    """Canonical skill metadata advertised by every Bodai MCP server.

    The schema is identical across all 5 Bodai servers (akosha,
    mahavishnu, session-buddy, dhara, crackerjack). It carries:

    - identity (``id``, ``server``, ``name``, ``version``)
    - routing hints (``tool_refs``, ``dependencies``, ``allowed_tools``)
    - body integrity (``content_hash``, ``body_size``, ``body_format``)
    - content classification (``content_type``, ``description``)
    - signing payload (``signature``, ``server_pubkey_id``)
    - audit (``timestamp``)

    The ``signature`` and ``server_pubkey_id`` fields are populated by
    :mod:`crackerjack.mcp.tools.skill_registry` AFTER signing. The
    canonical signing payload is the model_dump of this model with those
    two fields stripped (see ``canonical_payload_for_signing``).
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        # ``validate_assignment`` lets us re-validate when the tool
        # code sets ``metadata.signature`` after construction. Pydantic
        # v2 keeps this opt-in because it has a small cost; here the
        # cost is worth the safety.
        validate_assignment=True,
    )

    schema_version: Literal[1] = 1

    # ``id`` is the globally unique skill identifier — ``{server}:{name}:{version}``.
    # The validator below enforces the allowlist on the constituent fields;
    # ``id`` itself is built from them and is therefore constrained transitively.
    id: str

    server: str
    name: str
    description: str = Field(max_length=1024)
    version: str

    tool_refs: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    content_type: Literal["skill", "agent", "prompt"] = "skill"

    # Body integrity. ``content_hash`` is the lowercase hex SHA-256 of
    # the body bytes; ``body_size`` is the byte length. Both are
    # asserted by the client before write (B-1 / plan §11 B-1).
    content_hash: str
    body_size: int
    body_format: Literal["yaml-frontmatter+markdown"] = "yaml-frontmatter+markdown"

    allowed_tools: list[str] = Field(default_factory=list)

    # Signing payload. Both fields are populated by the tool handler
    # AFTER signing; ``signature`` carries the base64 ed25519 signature
    # and ``server_pubkey_id`` is the 16-char hex ``key_id`` from the
    # server's pubkey manifest.
    signature: str | None = None
    server_pubkey_id: str | None = None

    timestamp: float

    @field_validator("server", "name")
    @classmethod
    def _validate_allowlist(cls, value: str) -> str:
        """Enforce B-4 path-traversal allowlist on ``name`` and ``server``.

        Forbids ``/``, leading ``.``, uppercase characters, any character
        outside ``[a-z0-9._-]``, total length > 63, and the literal
        substring ``..`` (defense-in-depth, since the regex already
        forbids leading ``.`` but does not forbid ``..`` in the middle).
        """
        if not _NAME_OR_SERVER_RE.fullmatch(value):
            raise ValueError(
                f"value {value!r} does not match allowlist regex "
                r"'^[a-z0-9][a-z0-9._-]{0,62}$' "
                "(forbidden: '/', uppercase, leading '.', length > 63)"
            )
        if ".." in value:
            raise ValueError(
                f"value {value!r} contains forbidden substring '..'"
            )
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        """Description must be non-empty after stripping whitespace."""
        if not value.strip():
            raise ValueError("description must be non-empty")
        return value

    @field_validator("id")
    @classmethod
    def _validate_id_shape(cls, value: str) -> str:
        """``id`` must be ``{server}:{name}:{version}`` with no leading dot or slash.

        The constituent fields are individually validated by their own
        validators; this check ensures the composite matches the
        documented format and disallows extra colons in unexpected places.
        """
        if not value:
            raise ValueError("id must be non-empty")
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"id {value!r} must be 'server:name:version' (exactly 3 colon-separated parts)"
            )
        # Re-use the allowlist check on the server + name substrings;
        # the version substring uses the same character class but allows
        # a leading ``v`` (e.g. ``v1.0.0``) — so we only check for
        # obviously-forbidden characters.
        server, name, version = parts
        if not _NAME_OR_SERVER_RE.fullmatch(server):
            raise ValueError(f"id {value!r} has invalid server segment {server!r}")
        if not _NAME_OR_SERVER_RE.fullmatch(name):
            raise ValueError(f"id {value!r} has invalid name segment {name!r}")
        if not version or "/" in version or ".." in version:
            raise ValueError(f"id {value!r} has invalid version segment {version!r}")
        return value


__all__ = ["SkillMetadata"]
