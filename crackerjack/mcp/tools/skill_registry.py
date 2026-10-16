"""Phase 1 server-published skills tools for Crackerjack (per plan §6).

Exposes the ``mcp__crackerjack__crackerjack_list_skills`` and
``mcp__crackerjack__crackerjack_get_skill`` MCP tools that advertise
the server-defined skills to Phase 2's installer and the Claude Code
picker. Skills live as markdown bodies under
``crackerjack/mcp/skills_catalog/<name>.md``.

This module is a thin server-specific wrapper around
:func:`mcp_common.skills_tools.build_register_skills_tools`. The
factory owns the mechanism — the B-4 allowlist, the B-6 body
normalization + content-hash, the wire shape, the success/error
envelope, and the registration plumbing. Crackerjack owns the
policy: the catalog, where bodies live, the tool name prefix
(``"crackerjack_"``), how the signer is acquired (the no-lifespan
singleton populated at ``create_mcp_server()`` time and read via
``signer_feed.get_signer_feed_state()``), and the signing function
(canonicalization via crackerjack's local
``canonical_payload_for_signing``).

Security gates (per plan §11):

- **B-1** — every ``get_skill`` response carries an ed25519 signature
  over the canonicalized metadata. The Phase 2 installer verifies
  this before any write to ``~/.claude/skills/``.
- **B-4** — the path-traversal allowlist
  ``^[a-z0-9][a-z0-9._-]{0,62}$`` lives in
  ``mcp_common.canonical_schemas._validators.NAME_OR_SERVER_RE``;
  the factory enforces it at the API boundary. The per-server regex
  copy that used to live here is gone.
- **B-6** — ``content_hash`` is the lowercase hex SHA-256 of the
  stripped body bytes. The factory computes it from the body so
  clients can verify against the same canonical content.
- **B-7** — each successful tool call invokes ``on_call``,
  which bumps ``SignerFeedState.cycles_total`` via
  :meth:`record_cycle` so the four mandatory feed signals stay
  accurate.

Crackerjack-specific: unlike the other 4 servers, Crackerjack has
no async lifespan. The :class:`SkillsSigner` is built at
``init_signer_feed_state()`` time and read by these tools via
``get_signer_feed_state()``. If the signer has not been initialized
(pre-``create_mcp_server`` or init failure), the factory surfaces
the exception as the standard error envelope rather than raising.

This file is a structural mirror of
``crackerjack.mcp.tools.agent_registry`` — same imports, same
error envelope shape, same feed wiring; only the catalog
directory, schema class, and tool names differ.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp_common.canonical_schemas.skill import SkillCanonicalSchema
from mcp_common.skills_tools import build_register_skills_tools

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)


# Catalog lives one level up from this module so the catalog dir
# matches the project layout (other Bodai components also keep their
# skills under ``<package>/skills_catalog/``). Mirrors the
# ``agents/`` layout for Phase 3.
_CATALOG_DIR = Path(__file__).parent.parent / "skills_catalog"


# Phase 1: 4 starter skills with real Crackerjack-relevant content.
# Each dict is the body's filename, the skill name, the semantic
# version, the description that goes in both the picker description
# AND the canonical SkillCanonicalSchema, the list of MCP tool names
# the skill may invoke, and the dependency list (other skill names).
#
# Adding a new server-published skill: drop ``<name>.md`` under
# ``skills_catalog/`` AND add an entry below. The factory's catalog
# validation runs at module load — a missing file or duplicate
# name fails fast.
_STATIC_SKILLS: list[dict[str, Any]] = [
    {
        "name": "run-quality-checks",
        "body_filename": "run-quality-checks.md",
        "version": "1.0.0",
        "description": (
            "Use ONLY when the user explicitly types "
            "`/crackerjack:run-quality-checks` or selects this Skill "
            "from the picker to run the full Crackerjack quality "
            "workflow (ruff + mypy + pyright + bandit + pytest). "
            "Do not auto-trigger. Routes through "
            "`mcp__crackerjack__crackerjack_run`."
        ),
        "tool_refs": ["mcp__crackerjack__crackerjack_run"],
        "allowed_tools": [
            "mcp__crackerjack__crackerjack_run",
            "mcp__crackerjack__get_comprehensive_status",
            "Read",
        ],
        "dependencies": [],
    },
    {
        "name": "smart-error-analysis",
        "body_filename": "smart-error-analysis.md",
        "version": "1.0.0",
        "description": (
            "Use ONLY when the user explicitly types "
            "`/crackerjack:smart-error-analysis` or selects this Skill "
            "from the picker to surface common fix-failure patterns. "
            "Do not auto-trigger. Routes through "
            "`mcp__crackerjack__smart_error_analysis` with use_cache."
        ),
        "tool_refs": ["mcp__crackerjack__smart_error_analysis"],
        "allowed_tools": [
            "mcp__crackerjack__smart_error_analysis",
            "Read",
        ],
        "dependencies": [],
    },
    {
        "name": "version-bump",
        "body_filename": "version-bump.md",
        "version": "1.0.0",
        "description": (
            "Use ONLY when the user explicitly types "
            "`/crackerjack:version-bump` or selects this Skill from the "
            "picker to bump the Crackerjack version. Do not auto-trigger. "
            "Routes through `mcp__crackerjack__crackerjack_run -p {major,"
            "minor,patch}` after explicit user confirmation of the bump "
            "level."
        ),
        "tool_refs": ["mcp__crackerjack__crackerjack_run"],
        "allowed_tools": [
            "mcp__crackerjack__crackerjack_run",
            "mcp__crackerjack__suggest_patterns",
            "Read",
        ],
        "dependencies": [],
    },
    {
        "name": "review-pr",
        "body_filename": "review-pr.md",
        "version": "1.0.0",
        "description": (
            "Use ONLY when the user explicitly types "
            "`/crackerjack:review-pr` or selects this Skill from the "
            "picker to wire the C-13 review-pr trigger into a running "
            "session. Do not auto-trigger. The skill subscribes to the "
            "Akosha pattern `ecosystem.event.received{source='git-monitor'}` "
            "(NOT a Mahavishnu webhook), fetches the PR diff via the "
            "`CRACKERJACK_GITHUB_TOKEN` env var, dispatches a code-review "
            "prompt to Mahavishnu's `pool-route-execute` (with "
            "idempotency), and posts the review back as a PR comment. "
            "Routes through `crackerjack.skills.review_pr.on_akosha_pattern`."
        ),
        "tool_refs": [],
        "allowed_tools": [
            "mcp__crackerjack__crackerjack_list_skills",
            "mcp__crackerjack__crackerjack_get_skill",
            "Read",
        ],
        "dependencies": [],
    },
]


_SERVER_KEY = "crackerjack"


# Name-indexed view of the static catalog — built once at module load
# so the body loader can do O(1) lookups instead of scanning the list.
_STATIC_SKILLS_BY_NAME: dict[str, dict[str, Any]] = {
    entry["name"]: entry for entry in _STATIC_SKILLS
}


# --- Body source (server-specific) ----------------------------------


def _read_body(filename: str) -> str:
    """Load a skill body from the catalog, asserting the file exists."""
    path = _CATALOG_DIR / filename
    if not path.is_file():
        msg = f"Skill body {filename!r} missing from catalog at {path}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8")


def _body_loader(name: str) -> str:
    """Factory's body source: read the file from disk.

    The factory's ``_build_unsigned_metadata`` calls this on demand
    for any catalog entry that names a body. The factory strips the
    returned string and computes the B-6 content_hash from the
    stripped bytes.
    """
    return _read_body(_STATIC_SKILLS_BY_NAME[name]["body_filename"])


# --- Signing policy (server-specific) ---------------------------------


def _sign(metadata: SkillCanonicalSchema) -> SkillCanonicalSchema:
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
    if state is None:
        msg = "signer not initialized (server may still be starting up)"
        raise RuntimeError(msg)

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

    The factory invokes this at the start of every list_skills and
    get_skill call so the four mandatory feed signals stay
    accurate. No-op if the signer feed state isn't initialized
    yet (matches the pre-refactor behavior).
    """
    from crackerjack.mcp.signer_feed import get_signer_feed_state

    state = get_signer_feed_state()
    if state is not None:
        state.record_cycle()


# --- Tool registration ------------------------------------------------


def register_skill_registry(app: FastMCP) -> None:
    """Register ``crackerjack_list_skills`` and ``crackerjack_get_skill``.

    Idempotent at module level (the static catalog is loaded once at
    import). Calling this twice is safe — FastMCP's
    ``@app.tool`` decorator is idempotent within a single
    ``app`` instance.

    Delegates to :func:`mcp_common.skills_tools.build_register_skills_tools`
    with crackerjack's catalog, body source, signing policy,
    cycle-bump hook, and tool name prefix. The wire shape,
    allowlist enforcement, and envelope contract all live in
    the factory; crackerjack only owns the data, the signer, and
    the prefix.

    The function name is preserved as ``register_skill_registry``
    (not ``register_skills_tools``) for backward compatibility with
    the server registration call site.
    """
    build_register_skills_tools(
        server_key=_SERVER_KEY,
        catalog=_STATIC_SKILLS,
        body_loader=_body_loader,
        sign=_sign,
        on_call=_on_call,
        tool_name_prefix=f"{_SERVER_KEY}_",
        # The hook and any in-flight clients expect the
        # "crackerjack_" prefix on both tool names.
    )(app)


__all__ = ["register_skill_registry", "SkillCanonicalSchema"]
