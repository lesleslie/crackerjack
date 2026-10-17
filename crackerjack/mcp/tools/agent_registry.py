"""Phase 3 server-published agents tools for Crackerjack (per plan §5).

Exposes the ``mcp__crackerjack__crackerjack_list_agents`` and
``mcp__crackerjack__crackerjack_get_agent`` MCP tools that advertise
the server-defined specialist agents to the Phase 3 installer
and the Claude Code picker. Agents live as markdown bodies under
``crackerjack/mcp/agents/<name>.md``.

This module is a thin server-specific wrapper around
:func:`mcp_common.agents_tools.build_register_agents_tools`. The
factory owns the mechanism — the B-4 allowlist, B-6 body
normalization + content-hash, the wire shape, the success/error
envelope, and the tool registration plumbing. Crackerjack owns
the policy: the catalog, where bodies live, the tool name prefix
(``"crackerjack_"``), how the signer is acquired (the
no-lifespan singleton populated at ``create_mcp_server()`` time
and read via ``signer_feed.get_signer_feed_state()``), and the
signing function (canonicalization via crackerjack's local
``canonical_payload_for_signing``).

Security gates (per plan §11):

- **B-1** — every ``get_agent`` response carries an ed25519
  signature over the canonicalized metadata. The Phase 3 installer
  verifies this before any write to
  ``~/.claude/agents/crackerjack-<name>.md``.
- **B-4** — the path-traversal allowlist
  ``^[a-z0-9][a-z0-9._-]{0,62}$`` lives in
  ``mcp_common.canonical_schemas._validators.NAME_OR_SERVER_RE``;
  the factory enforces it at the API boundary. The per-server
  regex copy that used to live here is gone.
- **B-6** — ``get_agent`` returns ``body == system_prompt``. The
  factory computes ``content_hash`` from the stripped body and
  the schema's body-integrity model_validator asserts the hash
  matches the system_prompt bytes.
- **B-7** — each successful tool call invokes ``on_call``, which
  bumps ``SignerFeedState.cycles_total`` via
  :meth:`record_cycle` so the four mandatory feed signals stay
  accurate.

Crackerjack-specific: unlike the other 4 servers, Crackerjack has
no async lifespan. The :class:`SkillsSigner` is built at
``init_signer_feed_state()`` time and read by these tools via
``get_signer_feed_state()``. If the signer has not been
initialized (pre-``create_mcp_server`` or init failure), the
factory surfaces the exception as the standard error envelope
rather than raising.

This file is a structural mirror of
``crackerjack.mcp.tools.skill_registry`` — same imports, same
error envelope shape, same feed wiring; only the catalog
directory, schema class, and tool names differ.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp_common.agents_tools import build_register_agents_tools
from mcp_common.canonical_schemas.agent import AgentCanonicalSchema

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)


# Catalog lives one level up from this module so the agents dir
# matches the project layout (other Bodai components also keep
# their agents under ``<package>/agents/``). Mirrors the
# ``skills_catalog`` layout for Phase 1.
_CATALOG_DIR = Path(__file__).parent.parent / "agents"


# Phase 3: 3 starter specialist agents with real Crackerjack-relevant
# content. Each dict is the body's filename, the agent name, the
# semantic version, the description, the model, the list of tool
# references, and the list of dependencies. The full body is read
# from the markdown file at request time.
#
# Adding a new server-published agent: drop ``<name>.md`` under
# ``agents/`` AND add an entry below. The factory's catalog
# validation runs at module load — a missing file or duplicate
# name fails fast.
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


_SERVER_KEY = "crackerjack"


# Name-indexed view of the static catalog — built once at module
# load so the body loader can do O(1) lookups instead of scanning
# the list.
_STATIC_AGENTS_BY_NAME: dict[str, dict[str, Any]] = {
    entry["name"]: entry for entry in _STATIC_AGENTS
}


# --- Body source (server-specific) ------------------------------------


def _read_body(filename: str) -> str:
    """Load an agent body from the catalog, asserting the file exists."""
    path = _CATALOG_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Agent body {filename!r} missing from catalog at {path}"
        )
    return path.read_text(encoding="utf-8")


def _body_loader(name: str) -> str:
    """Factory's body source: read the file from disk.

    The factory's ``_build_unsigned_metadata`` calls this on demand
    for any catalog entry that doesn't carry ``system_prompt``
    inline. The factory strips the returned string and computes
    the B-6 content_hash from the stripped bytes.
    """
    return _read_body(_STATIC_AGENTS_BY_NAME[name]["body_filename"])


# --- Signing policy (server-specific) ---------------------------------


def _sign(metadata: AgentCanonicalSchema) -> AgentCanonicalSchema:
    """Apply an ed25519 signature using the no-lifespan singleton signer.

    The factory hands the unsigned metadata to this callable and
    receives the signed copy. Acquires the signer via
    :func:`crackerjack.mcp.signer_feed.get_signer_feed_state`
    (no-lifespan singleton populated at
    ``create_mcp_server()`` time), canonicalizes via crackerjack's
    local :func:`canonical_payload_for_signing` (which strips the
    ``signature`` + ``server_pubkey_id`` fields before signing so
    the signature doesn't cover itself), and attaches the result.

    Raises if the signer feed state isn't initialized (pre-
    ``create_mcp_server`` or init failure). The factory converts
    the exception into the standard error envelope.
    """
    from crackerjack.mcp.signer_feed import get_signer_feed_state
    from crackerjack.skills_signer import canonical_payload_for_signing

    state = get_signer_feed_state()
    if state is None or state.signer is None:
        raise RuntimeError("signer not initialized (server may still be starting up)")

    canonical = canonical_payload_for_signing(metadata.to_dict())
    signed = state.signer.sign(canonical)
    return metadata.model_copy(
        update={
            "signature": signed.signature_b64,
            "server_pubkey_id": signed.key_id,
        }
    )


# --- B-7 cycle bump (server-specific) ---------------------------------


def _on_call() -> None:
    """B-7: bump ``SignerFeedState.cycles_total`` on every tool call.

    The factory invokes this at the start of every list_agents and
    get_agent call so the four mandatory feed signals stay
    accurate. No-op if the signer feed state isn't initialized
    yet (matches the pre-refactor behavior).
    """
    from crackerjack.mcp.signer_feed import get_signer_feed_state

    state = get_signer_feed_state()
    if state is not None:
        state.record_cycle()


# --- Tool registration ------------------------------------------------


def register_agent_registry(app: FastMCP) -> None:
    """Register ``crackerjack_list_agents`` and ``crackerjack_get_agent``.

    Idempotent at module level (the static catalog is loaded once
    at import). Calling this twice is safe — FastMCP's
    ``@app.tool`` decorator is idempotent within a single
    ``app`` instance.

    Delegates to :func:`mcp_common.agents_tools.build_register_agents_tools`
    with crackerjack's catalog, body source, signing policy,
    cycle-bump hook, and tool name prefix. The wire shape,
    allowlist enforcement, and envelope contract all live in
    the factory; crackerjack only owns the data, the signer,
    and the prefix.

    The function name is preserved as ``register_agent_registry``
    (not ``register_agents_tools``) for backward compatibility
    with the server registration call site.
    """
    build_register_agents_tools(
        server_key=_SERVER_KEY,
        catalog=_STATIC_AGENTS,
        body_loader=_body_loader,
        sign=_sign,
        on_call=_on_call,
        tool_name_prefix=f"{_SERVER_KEY}_",
        # The hook and any in-flight clients expect the
        # "crackerjack_" prefix on both tool names.
    )(app)


__all__ = ["AgentCanonicalSchema", "register_agent_registry"]
