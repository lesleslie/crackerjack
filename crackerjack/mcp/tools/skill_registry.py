"""Phase 1 server-published skills tools for Crackerjack (per plan §6).

Exposes the ``mcp__crackerjack__crackerjack_list_skills`` and
``mcp__crackerjack__crackerjack_get_skill`` MCP tools that advertise the
server-defined skills to Phase 2's installer and the Claude Code picker.
Skills live as markdown bodies under
``crackerjack/mcp/skills_catalog/<name>.md``; this module reads them at
request time and signs the metadata via the no-lifespan singleton
populated at ``create_mcp_server()`` time.

Security gates (per plan §11):

- **B-1** — every ``get_skill`` response carries an ed25519 signature over
  the canonicalized metadata (Phase 2's installer verifies this before
  any write to ``~/.claude/skills/``).
- **B-4** — path-traversal allowlist ``^[a-z0-9][a-z0-9._-]{0,62}$`` is
  enforced on the ``name`` parameter at the API boundary BEFORE the
  metadata model re-validates it. An unknown / forbidden ``name`` returns
  an error envelope rather than raising past the MCP boundary.
- **B-7** — each successful tool call bumps
  ``SignerFeedState.cycles_total`` via :meth:`record_cycle` so the four
  mandatory feed signals stay accurate.

Crackerjack-specific: unlike the other 4 servers Crackerjack has no
async lifespan. The SkillsSigner is built at
``init_signer_feed_state()`` time and read by these tools via
``get_signer_feed_state()``. If the signer has not been initialized (pre-
``create_mcp_server`` or init failure), both tools return an informative
error envelope rather than raising.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from crackerjack.mcp.skill_schema import SkillMetadata
from crackerjack.skills_signer import canonical_payload_for_signing

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)


# Allowlist mirror — see B-4 / plan §5 task #4. Duplicated here so the
# API boundary rejects forbidden ``name`` values BEFORE constructing the
# Pydantic model (avoids letting a path-traversal payload reach the
# validator).
_NAME_ALLOWLIST_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


# Catalog lives next to this module so deployment paths stay self-contained.
_CATALOG_DIR = Path(__file__).parent.parent / "skills_catalog"


# Phase 1: 3 starter skills with real Crackerjack-relevant content.
# Each tuple is the body's filename, the semantic version, the
# description that goes in both SkillMetadata AND the frontmatter,
# the list of MCP tool names the skill may invoke, and the
# dependency list (other skill names).
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
]


_SERVER_NAME = "crackerjack"


# Name-indexed view of the static catalog — built once at module load so
# the tool handlers can do O(1) lookups instead of scanning the list.
_STATIC_SKILLS_BY_NAME: dict[str, dict[str, Any]] = {
    entry["name"]: entry for entry in _STATIC_SKILLS
}


def _read_body(filename: str) -> str:
    """Load a skill body from the catalog, asserting the file exists."""
    path = _CATALOG_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Skill body {filename!r} missing from catalog at {path}"
        )
    return path.read_text(encoding="utf-8")


def _build_unsigned_metadata(name: str) -> SkillMetadata:
    """Build a :class:`SkillMetadata` for the named static skill.

    The metadata has ``signature=None`` and ``server_pubkey_id=None``;
    those fields are populated by :func:`_sign_metadata` after signing.
    Raises :class:`KeyError` if ``name`` is not a known static skill.
    """
    entry = _STATIC_SKILLS_BY_NAME.get(name)
    if entry is None:
        msg = f"unknown skill {name!r}"
        raise KeyError(msg)
    body = _read_body(entry["body_filename"])
    body_bytes = body.encode("utf-8")
    content_hash = hashlib.sha256(body_bytes).hexdigest()
    version = entry["version"]
    return SkillMetadata(
        id=f"{_SERVER_NAME}:{name}:{version}",
        server=_SERVER_NAME,
        name=name,
        description=entry["description"],
        version=version,
        tool_refs=list(entry["tool_refs"]),
        dependencies=list(entry["dependencies"]),
        content_type="skill",
        content_hash=content_hash,
        body_size=len(body_bytes),
        body_format="yaml-frontmatter+markdown",
        allowed_tools=list(entry["allowed_tools"]),
        timestamp=datetime.now(UTC).timestamp(),
    )


def _sign_metadata(metadata: SkillMetadata, signer: Any) -> SkillMetadata:
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


def register_skill_registry(app: FastMCP) -> None:
    """Register ``crackerjack_list_skills`` and ``crackerjack_get_skill``.

    Idempotent at module level (the static catalog is loaded once at
    import). Both tools access the no-lifespan singleton
    :class:`SkillsSigner` via ``get_signer_feed_state()``; if the
    signer has not been initialized (pre-``create_mcp_server`` or init
    failure), the tools return an error envelope rather than raising.
    """

    @app.tool(name="crackerjack_list_skills")
    async def crackerjack_list_skills() -> list[dict[str, Any]]:
        """Return metadata for skills this server publishes.

        Returns at least 3 entries (one per static skill). The
        ``signature`` and ``server_pubkey_id`` fields are ``None`` here
        — those are populated by ``crackerjack_get_skill`` since the
        signature is over the canonical payload WITHOUT the signing
        fields themselves.
        """
        from crackerjack.mcp.signer_feed import get_signer_feed_state

        state = get_signer_feed_state()
        if state is not None:
            state.record_cycle()

        out: list[dict[str, Any]] = []
        for entry in _STATIC_SKILLS:
            try:
                metadata = _build_unsigned_metadata(entry["name"])
            except (FileNotFoundError, ValidationError, KeyError) as exc:
                logger.exception(
                    "crackerjack_list_skills: failed to build metadata for %s: %s",
                    entry["name"],
                    exc,
                )
                continue
            out.append(metadata.model_dump(mode="json"))
        return out

    @app.tool(name="crackerjack_get_skill")
    async def crackerjack_get_skill(name: str) -> dict[str, Any]:
        """Return the signed metadata + body for one skill.

        Validates ``name`` against the B-4 allowlist BEFORE constructing
        the metadata. Signs the metadata via the no-lifespan singleton
        :class:`SkillsSigner`. The body is the raw markdown text from
        ``skills_catalog/<name>.md`` — the client (Phase 2 installer)
        writes this verbatim to
        ``~/.claude/skills/crackerjack-<name>/SKILL.md``.
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
                "error": f"skill {name!r} not found on this server",
            }
        except FileNotFoundError as exc:
            return {"success": False, "error": str(exc)}
        except ValidationError as exc:
            return {"success": False, "error": f"metadata validation failed: {exc}"}

        signed = _sign_metadata(unsigned, state.signer)
        body = _read_body(_STATIC_SKILLS_BY_NAME[name]["body_filename"])
        return {
            "success": True,
            "metadata": signed.model_dump(mode="json"),
            "body": body,
        }


__all__ = ["register_skill_registry"]
