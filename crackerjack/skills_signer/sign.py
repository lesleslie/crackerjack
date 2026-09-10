"""Signing API for Bodai skill/agent metadata.

A :class:`SkillsSigner` wraps a single :class:`Keypair` and provides
:meth:`sign` for callers (Phase 1 ``get_skill`` / ``get_agent`` MCP
tool handlers). The signer also exposes :meth:`pubkey_manifest`
for publication in ``/health``.

Signatures are over canonicalized UTF-8 JSON bytes (see
:mod:`skills_signer.canonicalize`). The caller is responsible for
canonicalization; this module does NOT canonicalize internally so
that callers can sign pre-canonicalized payloads efficiently (e.g.
when the canonical bytes are already cached).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

from crackerjack.skills_signer.keys import Keypair
from crackerjack.skills_signer.manifest import PubkeyManifest, build_pubkey_manifest


@dataclass(frozen=True, slots=True)
class SkillsSigner:
    """A signer bound to one ed25519 private key.

    Use :meth:`sign` to produce a base64-encoded signature + key_id
    pair. Use :meth:`pubkey_manifest` to publish the public key for
    client verification.

    Attributes:
        key_id: stable 16-char hex identifier for the bound keypair.
        private_key: the ed25519 private key (held in process memory).
        public_key: the ed25519 public key (also exposed via
            :meth:`pubkey_manifest`).
    """

    key_id: str
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @classmethod
    def from_keypair(cls, keypair: Keypair) -> SkillsSigner:
        """Wrap a :class:`Keypair` as a :class:`SkillsSigner`."""
        return cls(
            key_id=keypair.key_id,
            private_key=keypair.private_key,
            public_key=keypair.public_key,
        )

    def pubkey_manifest(self) -> PubkeyManifest:
        """Return the public-key half of this signer as a manifest.

        Convenience for callers that wire the manifest into ``/health``.
        Equivalent to :func:`build_pubkey_manifest` applied to a fresh
        :class:`Keypair` carrying this signer's keys.
        """
        kp = Keypair(
            key_id=self.key_id,
            private_key=self.private_key,
            public_key=self.public_key,
        )
        return build_pubkey_manifest(kp)

    def sign(self, canonical_payload: bytes) -> SignedPayload:
        """Sign ``canonical_payload`` (must already be canonical bytes).

        Args:
            canonical_payload: canonical UTF-8 JSON bytes (see
                :func:`skills_signer.canonicalize.canonicalize_payload`).

        Returns:
            :class:`SignedPayload` with the base64-encoded signature
            and the signer's ``key_id``. Clients MUST verify against
            the same ``key_id`` in the server's pubkey manifest.
        """
        signature_bytes = self.private_key.sign(canonical_payload)
        return SignedPayload(
            signature_b64=base64.b64encode(signature_bytes).decode("ascii"),
            key_id=self.key_id,
        )


@dataclass(frozen=True, slots=True)
class SignedPayload:
    """The result of a successful sign operation.

    Attributes:
        signature_b64: base64-encoded ed25519 signature over the
            canonicalized payload.
        key_id: the 16-char hex identifier of the signing key (clients
            MUST look this up in the server's pubkey manifest before
            accepting the signature).
    """

    signature_b64: str
    key_id: str


__all__ = ["SignedPayload", "SkillsSigner"]
