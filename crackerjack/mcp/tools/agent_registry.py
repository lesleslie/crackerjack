"""Phase 3 server-published agents tools for Crackerjack (per plan §5).

Exposes the ``mcp__crackerjack__crackerjack_list_agents`` and
``mcp__crackerjack__crackerjack_get_agent`` MCP tools that advertise the
server-defined specialist agents to the Phase 3 installer and the
Claude Code picker. Agents live as markdown bodies under
``crackerjack/mcp/agents/<name>.md``; this module reads them at request
time and signs the metadata via the no-lifespan singleton populated at
``create_mcp_server()`` time.

Security gates (per plan §11):

- **B-1** — every ``get_agent`` response carries an ed25519 signature
  over the canonicalized metadata (Phase 3's installer verifies this
  before any write to ``~/.claude/agents/``).
- **B-4** — path-traversal allowlist ``^[a-z0-9][a-z0-9._-]{0,62}$``
  is enforced on the ``name`` parameter at the API boundary BEFORE
  the metadata model re-validates it. An unknown / forbidden ``name``
  returns an error envelope rather than raising past the MCP
  boundary.
- **B-6** — the full body is returned in ``get_agent`` so the
  installer can write a functional agent (without this, the installer
  ships non-functional agents with empty ``system_prompt``).
- **B-7** — each successful tool call bumps
  ``SignerFeedState.cycles_total`` via :meth:`record_cycle` so the
  four mandatory feed signals stay accurate.

Crackerjack-specific: unlike the other 4 servers Crackerjack has no
async lifespan. The SkillsSigner is built at
``init_signer_feed_state()`` time and read by these tools via
``get_signer_feed_state()``. If the signer has not been initialized
(pre-``create_mcp_server`` or init failure), both tools return an
informative error envelope rather than raising.

This file is a structural mirror of
``crackerjack.mcp.tools.skill_registry`` — same imports, same error
envelope shape, same feed wiring; only the catalog directory, schema
class, and tool names differ.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from crackerjack.mcp.agent_schema import AgentMetadata
from crackerjack.skills_signer import canonical_payload_for_signing

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)


# Allowlist mirror — see B-4 / plan §5 task #4. Duplicated here so the
# API boundary rejects forbidden ``name`` values BEFORE constructing the
# Pydantic model (avoids letting a path-traversal payload reach the
# validator).
_NAME_ALLOWLIST_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


# Catalog lives next to this module so deployment paths stay
# self-contained. Mirrors the ``skills_catalog`` layout for Phase 1.
_CATALOG_DIR = Path(__file__).parent.parent / "agents"


# Phase 3: 3 starter specialist agents with real Crackerjack-relevant
# content. Each dict is the body's filename, the agent name, the
# semantic version, the description, the model, the list of tool
# references (MCP tool names the agent may invoke), and the list of
# dependencies (other agent names). The full body is read from the
# markdown file at request time.
_STATIC_AGENTS: list[dict[str, Any]] = [
    {
        "name": "crackerjack-specialist",
        "body_filename": "crackerjack-specialist.md",
        "version": "1.0.0",
        "description": (
            "Use proactively for Crackerjack quality-gate operations: "
            "full 47-tool Crackerjack surface (pyright, ty, bandit, "
            "complexipy, ruff, pytest, semantic, otel, pycharm, "
            "language, monitoring), autoconfigure "
            "(`crackerjack --autoconfig -p <level>`), hook ordering, "
            "and quality-gate triage. Adjacent to "
            "mcp-integration-expert; this agent adds "
            "Crackerjack-specific tool selection, autoconfigure, and "
            "quality-gate triage."
        ),
        "model": "sonnet",
        "category": "quality",
        "owner": "crackerjack",
        "status": "active",
        "last_reviewed": "2026-09-10",
        "scope": "user-global",
        "tool_refs": [
            "mcp__crackerjack__crackerjack_run",
            "mcp__crackerjack__get_comprehensive_status",
        ],
        "dependencies": ["mcp-integration-expert"],
    },
    {
        "name": "quality-strategist",
        "body_filename": "quality-strategist.md",
        "version": "1.0.0",
        "description": (
            "Use proactively when the user asks 'what should our "
            "quality floor be?', 'which hooks should we enable?', or "
            "'how strict should mypy/pyright be for this project?'. "
            "Decides min-score thresholds and hook ordering for "
            "projects before invoking Crackerjack."
        ),
        "model": "sonnet",
        "category": "strategy",
        "owner": "crackerjack",
        "status": "active",
        "last_reviewed": "2026-09-10",
        "scope": "user-global",
        "tool_refs": [
            "mcp__crackerjack__list_quality_hooks",
            "mcp__crackerjack__autoconfig",
        ],
        "dependencies": ["crackerjack-specialist"],
    },
    {
        "name": "bump-strategist",
        "body_filename": "bump-strategist.md",
        "version": "1.0.0",
        "description": (
            "Use proactively when the user asks 'should this be a "
            "patch or a minor?', 'is this a breaking change?', or "
            "'what's the right bump level for this PR?'. Picks the "
            "semver bump level and the right PyPI publish path for "
            "Crackerjack."
        ),
        "model": "sonnet",
        "category": "release",
        "owner": "crackerjack",
        "status": "active",
        "last_reviewed": "2026-09-10",
        "scope": "user-global",
        "tool_refs": [
            "mcp__crackerjack__bump_version",
            "mcp__crackerjack__release",
        ],
        "dependencies": ["crackerjack-specialist"],
    },
]


_SERVER_NAME = "crackerjack"


# Name-indexed view of the static catalog — built once at module load
# so the tool handlers can do O(1) lookups instead of scanning the
# list.
_STATIC_AGENTS_BY_NAME: dict[str, dict[str, Any]] = {
    entry["name"]: entry for entry in _STATIC_AGENTS
}


def _read_body(filename: str) -> str:
    """Load an agent body from the catalog, asserting the file exists."""
    path = _CATALOG_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Agent body {filename!r} missing from catalog at {path}"
        )
    return path.read_text(encoding="utf-8")


def _build_unsigned_metadata(name: str) -> AgentMetadata:
    """Build an :class:`AgentMetadata` for the named static agent.

    The metadata has ``signature=None`` and ``server_pubkey_id=None``;
    those fields are populated by :func:`_sign_metadata` after signing.
    Raises :class:`KeyError` if ``name`` is not a known static agent.
    """
    entry = _STATIC_AGENTS_BY_NAME.get(name)
    if entry is None:
        msg = f"unknown agent {name!r}"
        raise KeyError(msg)
    body = _read_body(entry["body_filename"])
    body_bytes = body.encode("utf-8")
    content_hash = hashlib.sha256(body_bytes).hexdigest()
    version = entry["version"]
    return AgentMetadata(
        id=f"{_SERVER_NAME}:{name}:{version}",
        server_key=_SERVER_NAME,
        name=name,
        description=entry["description"],
        version=version,
        model=entry["model"],
        tool_refs=list(entry["tool_refs"]),
        dependencies=list(entry["dependencies"]),
        system_prompt=body,
        category=entry["category"],
        owner=entry["owner"],
        status=entry["status"],
        last_reviewed=entry["last_reviewed"],
        scope=entry["scope"],
        content_hash=content_hash,
        timestamp=datetime.now(UTC).timestamp(),
    )


def _sign_metadata(metadata: AgentMetadata, signer: Any) -> AgentMetadata:
    """Apply an ed25519 signature to a copy of ``metadata``.

    The canonical payload strips ``signature`` and ``server_pubkey_id``
    BEFORE canonicalization so the signature doesn't cover itself (per
    ``canonical_payload_for_signing`` docstring + plan §10.1.3).
    """
    unsigned_dict = metadata.model_dump(mode="json")
    canonical = canonical_payload_for_signing(unsigned_dict)
    signed = signer.sign(canonical)
    return metadata.model_copy(
        update={
            "signature": signed.signature_b64,
            "server_pubkey_id": signed.key_id,
        }
    )


def _is_allowlisted(name: str) -> bool:
    """B-4 API-boundary check on the ``name`` parameter."""
    return bool(_NAME_ALLOWLIST_RE.fullmatch(name)) and ".." not in name


def register_agent_registry(app: FastMCP) -> None:
    """Register ``crackerjack_list_agents`` and ``crackerjack_get_agent``.

    Idempotent at module level (the static catalog is loaded once at
    import). Both tools access the no-lifespan singleton
    :class:`SkillsSigner` via ``get_signer_feed_state()``; if the
    signer has not been initialized (pre-``create_mcp_server`` or init
    failure), the tools return an error envelope rather than raising.
    """

    @app.tool(name="crackerjack_list_agents")
    async def crackerjack_list_agents() -> list[dict[str, Any]]:
        """Return metadata for specialist agents this server publishes.

        Returns at least 3 entries (one per static agent). The
        ``signature`` and ``server_pubkey_id`` fields are ``None``
        here — those are populated by ``crackerjack_get_agent`` since
        the signature is over the canonical payload WITHOUT the
        signing fields themselves.
        """
        from crackerjack.mcp.signer_feed import get_signer_feed_state

        state = get_signer_feed_state()
        if state is not None:
            state.record_cycle()

        out: list[dict[str, Any]] = []
        for entry in _STATIC_AGENTS:
            try:
                metadata = _build_unsigned_metadata(entry["name"])
            except (FileNotFoundError, ValidationError, KeyError) as exc:
                logger.exception(
                    "crackerjack_list_agents: failed to build metadata for %s: %s",
                    entry["name"],
                    exc,
                )
                continue
            out.append(metadata.model_dump(mode="json"))
        return out

    @app.tool(name="crackerjack_get_agent")
    async def crackerjack_get_agent(name: str) -> dict[str, Any]:
        """Return the signed metadata + body for one specialist agent.

        Validates ``name`` against the B-4 allowlist BEFORE
        constructing the metadata. Signs the metadata via the
        no-lifespan singleton :class:`SkillsSigner`. The body is the
        raw markdown text from ``agents/<name>.md`` — the client
        (Phase 3 installer) writes this verbatim to
        ``~/.claude/agents/crackerjack-<name>.md``.
        """
        from crackerjack.mcp.signer_feed import get_signer_feed_state

        if not _is_allowlisted(name):
            return {
                "success": False,
                "error": (
                    f"name {name!r} violates path-traversal allowlist "
                    "(B-4): must match ^[a-z0-9][a-z0-9._-]{0,62}$ "
                    "with no '..' substring"
                ),
            }

        state = get_signer_feed_state()
        if state is None:
            return {
                "success": False,
                "error": "signer not initialized (server may still be starting up)",
            }
        state.record_cycle()

        try:
            unsigned = _build_unsigned_metadata(name)
        except KeyError:
            return {
                "success": False,
                "error": f"agent {name!r} not found on this server",
            }
        except FileNotFoundError as exc:
            return {"success": False, "error": str(exc)}
        except ValidationError as exc:
            return {"success": False, "error": f"metadata validation failed: {exc}"}

        signed = _sign_metadata(unsigned, state.signer)
        body = _read_body(_STATIC_AGENTS_BY_NAME[name]["body_filename"])
        return {
            "success": True,
            "metadata": signed.model_dump(mode="json"),
            "body": body,
        }


__all__ = ["register_agent_registry"]
