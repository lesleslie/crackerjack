"""Lifespan-owned signer feed state for Crackerjack's ``/health`` aggregator.

The :class:`SignerFeedState` is the source of truth for what the
skills_signer feed reports to ``/health``. It bundles:

- the manifest itself (pure data, lives in :mod:`crackerjack.skills_signer`)
- the four mandatory feed signals required by
  ``mcp-backend-wiring-discipline.md`` (``feed_entities_count``,
  ``feed_last_updated_timestamp``, ``cycles_total``, ``errors_total``)
- a ``generation`` token so concurrent-app teardown checks can
  verify ownership before clearing state

Why this lives in ``crackerjack/mcp/`` (not ``crackerjack/skills_signer/``):

The ``skills_signer`` package is supposed to replicate byte-for-byte
across the 5 Bodai servers. Lifecycle state (counters, timestamps,
generation tokens) is per-server MCP wiring concern. By keeping the
package pure data and adding the feed state here, the cross-server
package stays trivial to copy-paste and the per-server wiring
contract is explicit.

Crackerjack-specific: Crackerjack has a **static 200 ``/health`` route**
at ``crackerjack/mcp/server_core.py:135-141`` with no async lifespan.
This module uses a module-level singleton (mahavishnu's no-lifespan
pattern, per plan §10.3.2 option c) and exposes
:func:`init_signer_feed_state` to be called at the first
``create_mcp_server()`` invocation. ``init_signer_feed_state`` is wrapped
in try/except inside ``create_mcp_server`` so a signer init failure does
NOT crash the static-200 /health route — the route falls back to
returning 503 with ``checks.skills_signer.error = "init failed"``.

The launchd wrapper tolerates up to 120s of warm-up before considering
the process failed.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.skills_signer import PubkeyManifest, SkillsSigner

logger = logging.getLogger(__name__)

# Module-level singleton for the SignerFeedState. Initialized lazily
# inside ``create_mcp_server()`` because crackerjack registers
# ``/health`` before the signer init step (early-probe design).
# Concurrent app instances (tests, hot reload) overwrite this; the
# launchd wrapper tolerates up to 120s of warm-up before considering
# the process failed.
_signer_feed_state: SignerFeedState | None = None


def get_signer_feed_state() -> SignerFeedState | None:
    """Return the current :class:`SignerFeedState` or ``None`` if not
    yet initialized (create_mcp_server hasn't completed the signer init).
    """
    return _signer_feed_state


def init_signer_feed_state() -> SignerFeedState:
    """Load or create the persisted signing keypair, build the manifest,
    and install a fresh :class:`SignerFeedState` as the module singleton.

    Idempotent within a single ``create_mcp_server()`` call (subsequent
    calls overwrite the singleton, bumping the generation token). Tests
    that want a clean slate call :func:`reset_signer_feed_state`.

    Raises:
        OSError: when the persistence path cannot be created.
        ValueError: when the persisted file is not a valid ed25519
            PEM private key.
    """
    from crackerjack.skills_signer import (
        SkillsSigner,
        build_pubkey_manifest,
        load_or_create_keypair,
    )

    global _signer_feed_state

    key_path = _resolve_crackerjack_signer_key_path()
    keypair = load_or_create_keypair(key_path)
    manifest = build_pubkey_manifest(keypair)
    # Phase 1: SkillsSigner wraps the same keypair so list_skills /
    # get_skill MCP tools can produce signatures without re-reading the
    # PEM from disk. Lives only on SignerFeedState; tools read it via
    # get_signer_feed_state().
    signer = SkillsSigner.from_keypair(keypair)

    if _signer_feed_state is not None:
        # Re-init: bump the generation token so the old probe's
        # captured state is invalidated.
        new_state = SignerFeedState(
            manifest=manifest,
            signer=signer,
            generation=_signer_feed_state.generation + 1,
        )
    else:
        new_state = SignerFeedState(manifest=manifest, signer=signer)

    _signer_feed_state = new_state
    logger.info(
        "skills_signer feed state initialized key_id=%s key_path=%s",
        keypair.key_id,
        key_path,
    )
    return new_state


def reset_signer_feed_state() -> None:
    """Clear the module singleton (test helper)."""
    global _signer_feed_state
    _signer_feed_state = None


def _resolve_crackerjack_signer_key_path() -> Path:
    """Resolve the persisted keypair path for Crackerjack.

    Default: ``~/.crackerjack/state/skills_signer/private_key.pem``.
    Override via ``CRACKERJACK_SKILLS_SIGNER_KEY_PATH`` for tests and
    non-standard locations.
    """
    env_path = os.getenv("CRACKERJACK_SKILLS_SIGNER_KEY_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".crackerjack" / "state" / "skills_signer" / "private_key.pem"


@dataclass
class SignerFeedState:
    """Source of truth for the skills_signer ``/health`` feed.

    Constructed at ``create_mcp_server()`` after the keypair is
    loaded/persisted and the manifest is built. Mutation happens
    only via the :meth:`record_cycle` / :meth:`record_error` helpers
    so the ``last_updated_timestamp`` stays consistent with the cycle
    counter.

    Attributes:
        manifest: the :class:`PubkeyManifest` published in ``/health``.
        signer: the :class:`SkillsSigner` for producing Phase 1
            ``get_skill`` / ``get_agent`` response signatures. Built at
            ``init_signer_feed_state`` time from the same keypair that
            produces the manifest.
        last_updated_timestamp: unix timestamp of the most recent update
            (initial creation or last :meth:`record_cycle`).
        cycles_total: count of successful feed update cycles since startup.
        errors_total: count of failed feed update cycles since startup.
        generation: monotonic token so teardown can detect
            cross-app state contamination. Incremented whenever the
            state is rebuilt (e.g., after a key load failure).
    """

    manifest: PubkeyManifest
    signer: SkillsSigner
    last_updated_timestamp: float = field(default_factory=time.time)
    cycles_total: int = 0
    errors_total: int = 0
    generation: int = 0

    def record_cycle(self) -> None:
        """Mark a successful feed update. Bumps ``cycles_total`` and
        ``last_updated_timestamp``.
        """
        self.cycles_total += 1
        self.last_updated_timestamp = time.time()

    def record_error(self) -> None:
        """Mark a failed feed update. Bumps ``errors_total`` and
        ``last_updated_timestamp`` (the timestamp is updated even on
        errors so operators can see the feed is still being polled).
        """
        self.errors_total += 1
        self.last_updated_timestamp = time.time()

    def is_ok(self) -> bool:
        """True when the feed has at least one entry. Empty manifests
        return False so the ``/health`` endpoint returns 503.
        """
        return not self.manifest.is_empty()

    def as_dict(self) -> dict[str, object]:
        """Serialize for the ``/health`` payload.

        Returns a flat dict compatible with the other Crackerjack feed
        entries (``ok``, ``feed_entities_count``, ``feed_last_updated_timestamp``,
        ``cycles_total``, ``errors_total``). The manifest data is
        nested under ``key_count`` / ``pubkeys`` for backwards compat
        with Phase 2/6 installers that already parse those fields.
        """
        manifest_dict = self.manifest.as_dict()
        return {
            "ok": self.is_ok(),
            "feed": "skills_signer",
            "feed_entities_count": manifest_dict["key_count"],
            "feed_last_updated_timestamp": self.last_updated_timestamp,
            "cycles_total": self.cycles_total,
            "errors_total": self.errors_total,
            "generation": self.generation,
            "key_count": manifest_dict["key_count"],
            "pubkeys": manifest_dict["pubkeys"],
        }


__all__ = [
    "SignerFeedState",
    "_resolve_crackerjack_signer_key_path",
    "get_signer_feed_state",
    "init_signer_feed_state",
    "reset_signer_feed_state",
]
