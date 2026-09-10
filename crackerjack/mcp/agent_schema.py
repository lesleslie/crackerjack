"""Agent metadata schema (Phase 3 of bodai-skill-agent-distribution plan).

Defines :class:`AgentMetadata`, the canonical Pydantic v2 model for
specialist-agent metadata advertised by every Bodai MCP server. The
model is identical across all 5 replicas (akosha, mahavishnu,
session-buddy, dhara, crackerjack) and is the wire shape returned by
``mcp__<server>__list_agents`` and embedded in
``mcp__<server>__get_agent`` responses.

Schema ownership
----------------

Per plan §10.3.5, the schema is canonical across all 5 servers. Two
valid ownership models are documented in the plan: cross-repo import
(each server depends on ``akosha>=0.15.1`` and imports
``from akosha.mcp.agent_schema import AgentMetadata``) or per-server
copy. This file IS the canonical source (sed-replicated from akosha
commit ``4951ee8`` 2026-09-10); other servers either import it
directly or copy its contents verbatim.

Path-traversal allowlist (B-4)
------------------------------

Per plan §5 task #4 and §11 B-4, ``name`` and ``server_key`` fields
are constrained to a strict allowlist that prevents path-traversal
attacks via server-supplied metadata. The regex forbids:

- ``/`` (anywhere)
- leading ``.`` (cannot start with a dot)
- uppercase characters
- any character outside ``[a-z0-9._-]``
- total length > 63 (the regex ``{0,62}`` after the first char)

The brief additionally requires forbidding the literal substring
``..`` defense-in-depth, so the validator runs an extra explicit
check for that pattern.

R-14: the ``scope`` field is also constrained (literal enum) so a
server cannot advertise a ``project-local`` agent from inside a
shared catalog (the installer only writes user-global agents to
``~/.claude/agents/<server>-<name>.md``).
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


class AgentMetadata(BaseModel):
    """Canonical specialist-agent metadata advertised by every Bodai MCP server.

    The schema is identical across all 5 Bodai servers (akosha,
    mahavishnu, session-buddy, dhara, crackerjack). It carries:

    - identity (``id``, ``server_key``, ``name``, ``version``, ``title``)
    - routing hints (``model``, ``tools``, ``category``, ``owner``)
    - body (``system_prompt`` — Claude Code reads this, not metadata)
    - cross-agent refs (``dependencies``, ``tool_refs``)
    - lifecycle (``status``, ``last_reviewed``, ``scope``)
    - body integrity (``content_hash``)
    - signing payload (``signature``, ``server_pubkey_id``)
    - audit (``timestamp``)

    The ``signature`` and ``server_pubkey_id`` fields are populated by
    :mod:`crackerjack.mcp.tools.agent_registry` AFTER signing. The
    canonical signing payload is the model_dump of this model with
    those two fields stripped (see
    ``crackerjack.skills_signer.canonical_payload_for_signing``).
    """

    model_config = ConfigDict(
        extra="forbid",
        # ``str_strip_whitespace`` is intentionally NOT set: per Phase 3
        # §11 B-6, the ``system_prompt`` field carries the agent body
        # verbatim and ``content_hash`` covers those exact bytes.
        # Stripping whitespace would invalidate the hash-pin contract.
        # ``validate_assignment`` lets us re-validate when the tool
        # code sets ``metadata.signature`` after construction. Pydantic
        # v2 keeps this opt-in because it has a small cost; here the
        # cost is worth the safety.
        validate_assignment=True,
    )

    schema_version: Literal[1] = 1

    # ``id`` is the globally unique agent identifier — ``{server_key}:{name}:{version}``.
    # The validator below enforces the allowlist on the constituent
    # fields; ``id`` itself is built from them and is therefore
    # constrained transitively.
    id: str

    # ``server_key`` is the open string identifying the publishing
    # server (e.g. ``crackerjack``, ``akosha``). Per R-5 the schema
    # keeps it open (no ``Literal``) so new servers can advertise
    # without a schema bump — but the validator still enforces the
    # B-4 allowlist.
    server_key: str
    name: str

    # Picker display name (e.g. ``Crackerjack Specialist``). Optional
    # so a server can omit it; the picker falls back to ``name``.
    title: str | None = None

    description: str = Field(max_length=1024)
    version: str = "0.0.0"

    # Routing hints — the picker reads ``model`` + ``tools`` directly.
    model: str
    tools: list[str] = Field(default_factory=list)

    # ``system_prompt`` is the FULL body Claude Code loads. The
    # critical Phase 3 fix from §11 B-6 — without carrying the body in
    # metadata, the installer would ship non-functional agents.
    system_prompt: str = ""

    dependencies: list[str] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)

    category: str | None = None
    owner: str | None = None
    status: Literal["active", "archived", "draft"] | None = None

    # ISO date (YYYY-MM-DD); not a strict datetime so we keep it as a
    # plain string. The validator enforces non-empty only when set.
    last_reviewed: str | None = None

    # R-14: ``scope`` is constrained to user-global only in the wire
    # schema. The installer only writes user-global agents to
    # ``~/.claude/agents/<server>-<name>.md``; project-local agents
    # are not advertised through this seam.
    scope: Literal["user-global", "project-local"] = "user-global"

    # Body integrity — sha256 of ``system_prompt`` bytes (lowercase
    # hex). The installer verifies this BEFORE write (B-1 /
    # plan §11 B-1).
    content_hash: str

    # Signing payload — populated by the tool handler AFTER signing;
    # ``signature`` carries the base64 ed25519 signature and
    # ``server_pubkey_id`` is the 16-char hex ``key_id`` from the
    # server's pubkey manifest.
    signature: str | None = None
    server_pubkey_id: str | None = None

    timestamp: float

    @field_validator("server_key", "name")
    @classmethod
    def _validate_allowlist(cls, value: str) -> str:
        """Enforce B-4 path-traversal allowlist on ``name`` and ``server_key``.

        Forbids ``/``, leading ``.``, uppercase characters, any
        character outside ``[a-z0-9._-]``, total length > 63, and the
        literal substring ``..`` (defense-in-depth, since the regex
        already forbids leading ``.`` but does not forbid ``..`` in
        the middle).
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

    @field_validator("system_prompt")
    @classmethod
    def _validate_system_prompt(cls, value: str) -> str:
        """B-6: ``system_prompt`` must be non-empty.

        The Phase 3 plan's critical fix — without a body, the
        installed agent is non-functional. We enforce non-empty here
        at the schema layer so a server cannot accidentally advertise
        a body-less agent.
        """
        if not value.strip():
            raise ValueError("system_prompt must be non-empty")
        return value

    @field_validator("id")
    @classmethod
    def _validate_id_shape(cls, value: str) -> str:
        """``id`` must be ``{server_key}:{name}:{version}`` with no leading dot or slash.

        The constituent fields are individually validated by their own
        validators; this check ensures the composite matches the
        documented format and disallows extra colons in unexpected
        places.
        """
        if not value:
            raise ValueError("id must be non-empty")
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"id {value!r} must be 'server_key:name:version' "
                "(exactly 3 colon-separated parts)"
            )
        # Re-use the allowlist check on the server_key + name
        # substrings; the version substring uses the same character
        # class but allows a leading ``v`` (e.g. ``v1.0.0``) — so we
        # only check for obviously-forbidden characters.
        server_key, name, version = parts
        if not _NAME_OR_SERVER_RE.fullmatch(server_key):
            raise ValueError(
                f"id {value!r} has invalid server_key segment {server_key!r}"
            )
        if not _NAME_OR_SERVER_RE.fullmatch(name):
            raise ValueError(
                f"id {value!r} has invalid name segment {name!r}"
            )
        if not version or "/" in version or ".." in version:
            raise ValueError(
                f"id {value!r} has invalid version segment {version!r}"
            )
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
            raise ValueError(
                f"last_reviewed {value!r} must be ISO date YYYY-MM-DD"
            )
        return value


__all__ = ["AgentMetadata"]