"""Signature verification for Phase 2/6 installers.

This module is the trust boundary. Every Bodai client that materializes
a Skill or Agent from a server-supplied body MUST call
:func:`verify_signature` BEFORE writing to ``~/.claude/skills/`` or
``~/.claude/agents/``. A failed verification means:

- The server's pubkey manifest does not include the claimed ``key_id``
  (the server rotated its key without telling you, or you have a stale
  manifest), OR
- The signature was computed over different bytes (MITM, corruption,
  or a malicious server substituting a tampered body).

In either case, the caller MUST abort the install and surface a clear
error. The installer must NEVER silently fall back to "unsigned but
trust me" — Phase 1.5's whole purpose is to make signing mandatory.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidSignature

from crackerjack.skills_signer.errors import UnknownKeyIdError

if TYPE_CHECKING:
    from crackerjack.skills_signer.manifest import PubkeyManifest, PubkeyManifestEntry

logger = logging.getLogger(__name__)


def verify_signature(
    canonical_payload: bytes,
    signature_b64: str,
    key_id: str,
    manifest: PubkeyManifest,
) -> PubkeyManifestEntry:
    """Verify ``canonical_payload`` against ``signature_b64``.

    Args:
        canonical_payload: canonical UTF-8 JSON bytes (must match what
            the server signed; re-canonicalize on the client side).
        signature_b64: base64-encoded ed25519 signature from the
            server's ``SkillMetadata.signature`` field.
        key_id: the signer's 16-char hex identifier from the server's
            ``SkillMetadata.server_pubkey_id`` field.
        manifest: the server's pubkey manifest (from ``/health``).

    Returns:
        The :class:`PubkeyManifestEntry` whose ``key_id`` matched.
        Callers can then surface the verified entry to the user
        (Phase 2's two-phase confirmation step).

    Raises:
        UnknownKeyIdError: when ``key_id`` is not present in ``manifest``.
        TypeError: when ``signature_b64`` is not a ``str``.
        ValueError: when ``signature_b64`` is malformed base64.
        InvalidSignature: when the signature does not match the
            payload (do NOT catch and continue — abort the install).
    """
    if not isinstance(signature_b64, str):
        raise TypeError(
            f"signature_b64 must be str, not {type(signature_b64).__name__}"
        )

    entry = manifest.get(key_id)
    if entry is None:
        raise UnknownKeyIdError(
            f"key_id {key_id!r} not present in pubkey manifest; "
            "server may have rotated its key. Aborting install."
        )

    try:
        signature_bytes = base64.b64decode(signature_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"signature_b64 is not valid base64: {exc}"
        ) from exc

    try:
        entry.public_key.verify(signature_bytes, canonical_payload)
    except InvalidSignature:
        # NOTE: do NOT wrap this — the caller MUST distinguish a
        # verification failure from any other error and abort.
        # Log at warning (not error) because signature mismatch is an
        # expected client-side state, not an internal fault.
        logger.warning(
            "signature verify failed: key_id=%s manifest_keys=%d",
            entry.key_id,
            len(manifest),
        )
        raise

    return entry


__all__ = ["verify_signature"]
