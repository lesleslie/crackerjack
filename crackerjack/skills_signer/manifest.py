"""Public-key manifest pinned in each Bodai server's ``/health``.

A :class:`PubkeyManifest` maps ``key_id`` -> :class:`PubkeyManifestEntry`.
Servers publish the manifest under
``/health`` -> ``checks.skills_signer.pubkeys`` so clients can verify
signatures without an out-of-band key-exchange step.

The manifest is intentionally minimal — just the public keys the
server signs with today. Servers that rotate keys emit BOTH the old
and new entries during the grace period (``build_pubkey_manifest``
accepts a list); clients verify the ``key_id`` matches the entry
they accept.

Lifecycle state (counters, timestamps, generation tokens) lives in
``crackerjack.mcp.signer_feed.SignerFeedState``, NOT here. This keeps the
manifest a pure data structure that replicates identically across
the 5 Bodai servers.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives import serialization

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from crackerjack.skills_signer.errors import (
    InvalidManifestAlgorithmError,
    MalformedManifestError,
)
from crackerjack.skills_signer.keys import Keypair, public_key_from_bytes

# Only algorithm currently supported. Reserved for future migration.
SUPPORTED_ALGORITHM: str = "ed25519"


@dataclass(frozen=True, slots=True)
class PubkeyManifestEntry:
    """One public key in the manifest.

    Attributes:
        key_id: 16-char hex identifier (matches ``key_id`` in
            signatures and ``SkillMetadata.server_pubkey_id``).
        public_key: the ed25519 public key (used for verification).
        created_at: unix timestamp when the entry was added.
        algorithm: signing algorithm — always ``"ed25519"`` today.
    """

    key_id: str
    public_key: Ed25519PublicKey
    created_at: float
    algorithm: str = SUPPORTED_ALGORITHM


@dataclass(frozen=True, slots=True)
class PubkeyManifest:
    """The set of public keys a server signs with.

    Use :meth:`get` to look up an entry by ``key_id``; :meth:`as_dict`
    to serialize the manifest data (no lifecycle state — see
    ``SignerFeedState`` for that).
    """

    entries: dict[str, PubkeyManifestEntry] = field(default_factory=dict)

    def get(self, key_id: str) -> PubkeyManifestEntry | None:
        """Return the entry for ``key_id`` or ``None`` if absent."""
        return self.entries.get(key_id)

    def __contains__(self, key_id: str) -> bool:
        return key_id in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def is_empty(self) -> bool:
        """Return True when the manifest has no entries."""
        return len(self.entries) == 0

    def as_dict(self) -> dict[str, Any]:
        """Serialize the manifest data for ``/health``.

        Returns::

            {
              "key_count": N,
              "pubkeys": [
                {
                  "key_id": "<16 hex>",
                  "algorithm": "ed25519",
                  "public_key_b64": "<base64>",
                  "created_at": <unix_ts>
                },
                ...
              ]
            }

        Note:
            Lifecycle signals (``ok``, ``feed_entities_count``,
            ``cycles_total``, ``errors_total``, ``generation``) are
            added by the ``SignerFeedState`` wrapper, NOT here. The
            manifest itself is pure data.
        """
        pubkeys = [
            {
                "key_id": entry.key_id,
                "algorithm": entry.algorithm,
                "public_key_b64": _public_key_to_b64(entry.public_key),
                "created_at": entry.created_at,
            }
            for entry in self.entries.values()
        ]
        return {
            "key_count": len(pubkeys),
            "pubkeys": pubkeys,
        }


def build_pubkey_manifest(
    keypair_or_keypairs: Keypair | list[Keypair],
) -> PubkeyManifest:
    """Build a manifest from one keypair or a list of keypairs.

    Single-keypair usage (Phase 1.5 startup)::

        manifest = build_pubkey_manifest(server_keypair)

    Rotation usage (during the grace period with both old and new keys)::

        manifest = build_pubkey_manifest([old_keypair, new_keypair])

    When a list is provided, duplicate ``key_id``s silently overwrite
    earlier entries. Callers are expected to never construct two
    keypairs with the same ``key_id``; this is enforced by the
    truncation to 64 bits of SHA-256(public_key) — collision risk is
    negligible for any realistic manifest size.

    Args:
        keypair_or_keypairs: one :class:`Keypair` or a list.

    Returns:
        A :class:`PubkeyManifest`.
    """
    if isinstance(keypair_or_keypairs, Keypair):
        keypairs = [keypair_or_keypairs]
    else:
        keypairs = list(keypair_or_keypairs)

    entries: dict[str, PubkeyManifestEntry] = {}
    # Single ``time.time()`` call so all entries share the same
    # timestamp; makes the manifest diff easier to read.
    now = time.time()
    for kp in keypairs:
        entry = PubkeyManifestEntry(
            key_id=kp.key_id,
            public_key=kp.public_key,
            created_at=now,
        )
        entries[entry.key_id] = entry
    return PubkeyManifest(entries=entries)


def merge_manifests(*manifests: PubkeyManifest) -> PubkeyManifest:
    """Combine entries from multiple manifests.

    Used to extend a manifest with additional trusted keys (e.g.
    operator-pinned keys, vendor keys, or keys from a federated
    trust source). When the same ``key_id`` exists in multiple input
    manifests, the LATER manifest wins.

    Args:
        manifests: one or more :class:`PubkeyManifest` instances.

    Returns:
        A new :class:`PubkeyManifest` with merged entries.
    """
    merged: dict[str, PubkeyManifestEntry] = {}
    for manifest in manifests:
        merged.update(manifest.entries)
    return PubkeyManifest(entries=merged)


def _public_key_to_b64(public_key: Ed25519PublicKey) -> str:
    """Encode a public key in base64 for JSON transport."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def manifest_entry_from_dict(data: dict[str, Any]) -> PubkeyManifestEntry:
    """Deserialize a manifest entry from a ``/health`` JSON payload.

    Args:
        data: one entry from the ``pubkeys`` array in the manifest.

    Returns:
        A :class:`PubkeyManifestEntry`.

    Raises:
        MalformedManifestError: when required fields are missing.
        ValueError: when ``public_key_b64`` is malformed.
        InvalidManifestAlgorithmError: when ``algorithm`` is not
            ``"ed25519"``. Defense-in-depth for future algorithm
            migration; prevents downgrade attacks.
    """
    required = ("key_id", "algorithm", "public_key_b64", "created_at")
    missing = [k for k in required if k not in data]
    if missing:
        raise MalformedManifestError(
            f"manifest entry missing fields: {missing}"
        )

    algorithm = data["algorithm"]
    if algorithm != SUPPORTED_ALGORITHM:
        raise InvalidManifestAlgorithmError(
            f"unsupported manifest algorithm: {algorithm!r} "
            f"(only {SUPPORTED_ALGORITHM!r} supported)"
        )

    raw = base64.b64decode(data["public_key_b64"], validate=True)
    public_key = public_key_from_bytes(raw)
    return PubkeyManifestEntry(
        key_id=data["key_id"],
        public_key=public_key,
        created_at=float(data["created_at"]),
        algorithm=algorithm,
    )


def manifest_from_dict(data: dict[str, Any]) -> PubkeyManifest:
    """Deserialize a full :class:`PubkeyManifest` from JSON payload.

    Raises:
        MalformedManifestError: when an entry is missing required fields.
        InvalidManifestAlgorithmError: when an entry claims a
            non-ed25519 algorithm.
    """
    pubkeys = data.get("pubkeys", [])
    entries: dict[str, PubkeyManifestEntry] = {}
    for entry_data in pubkeys:
        entry = manifest_entry_from_dict(entry_data)
        entries[entry.key_id] = entry
    return PubkeyManifest(entries=entries)


__all__ = [
    "SUPPORTED_ALGORITHM",
    "PubkeyManifest",
    "PubkeyManifestEntry",
    "build_pubkey_manifest",
    "manifest_entry_from_dict",
    "manifest_from_dict",
    "merge_manifests",
]
