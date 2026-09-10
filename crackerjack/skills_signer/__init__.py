"""ed25519 signing infrastructure for Bodai skill/agent distribution.

Part of Phase 1.5 of `docs/plans/2026-09-09-bodai-skill-agent-distribution.md`.
This package implements the cryptographic layer that gates Phase 2/6
installer primitives (without signing, the installer is a generic
RCE primitive — see plan §11 B-1).

Public surface:

- :func:`generate_keypair` — produce a fresh ed25519 keypair with a
  deterministic 16-char hex ``key_id``.
- :func:`load_or_create_keypair` — load a persisted keypair from PEM,
  or generate + persist a fresh one. Use this at lifespan startup so
  every server restart preserves the same ``key_id``; without
  persistence, every restart breaks all previously installed Skills.
- :class:`Keypair` — the private + public key halves plus ``key_id``.
- :class:`SkillsSigner` — wraps a private key, exposes
  :meth:`SkillsSigner.sign` and :meth:`SkillsSigner.pubkey_manifest`.
- :class:`PubkeyManifest` / :class:`PubkeyManifestEntry` — the set of
  trusted public keys for a server.
- :func:`build_pubkey_manifest` / :func:`merge_manifests` —
  constructors for :class:`PubkeyManifest`. ``build_pubkey_manifest``
  accepts one keypair or a list (rotation); ``merge_manifests``
  combines existing manifests.
- :func:`manifest_from_dict` / :func:`manifest_entry_from_dict` —
  deserialize a manifest from a ``/health`` JSON payload.
- :func:`verify_signature` — pure-function verification against a
  pubkey manifest entry. Used by Phase 2/6 installers before any write
  to ``~/.claude/skills/`` or ``~/.claude/agents/``.
- :func:`canonicalize_payload` — deterministic JSON encoding (sorted
  keys, no whitespace, UTF-8). All signatures are over canonicalized
  bytes.
- :func:`canonical_payload_for_signing` — strips post-signing
  annotation fields (``signature``, ``server_pubkey_id``) before
  canonicalization. Use this for SkillMetadata / AgentMetadata that
  carries its own signature fields.
- Exception hierarchy: :class:`SkillsSignerError`,
  :class:`UnknownKeyIdError`, :class:`MalformedManifestError`,
  :class:`InvalidManifestAlgorithmError`.

Canonicalization is intentionally simple (sorted keys, no whitespace)
rather than RFC 8785 JCS — every server and client uses the same
``json.dumps(obj, sort_keys=True, separators=(",", ":"))`` call, so
byte-equality is trivial to verify. The wire format is the
canonicalized UTF-8 JSON; signatures are over those bytes.
"""

from __future__ import annotations

from crackerjack.skills_signer.canonicalize import (
    SIGNATURE_FIELDS_TO_STRIP,
    canonical_payload_for_signing,
    canonicalize_payload,
)
from crackerjack.skills_signer.errors import (
    InvalidManifestAlgorithmError,
    MalformedManifestError,
    SkillsSignerError,
    UnknownKeyIdError,
)
from crackerjack.skills_signer.keys import (
    KEY_ID_BYTES,
    Keypair,
    generate_keypair,
    load_or_create_keypair,
    public_key_from_bytes,
)
from crackerjack.skills_signer.manifest import (
    SUPPORTED_ALGORITHM,
    PubkeyManifest,
    PubkeyManifestEntry,
    build_pubkey_manifest,
    manifest_entry_from_dict,
    manifest_from_dict,
    merge_manifests,
)
from crackerjack.skills_signer.sign import SignedPayload, SkillsSigner
from crackerjack.skills_signer.verify import verify_signature

__all__ = [  # noqa: RUF022  # grouped with section comments; alphabetical sort would split them
    # Canonicalization
    "canonical_payload_for_signing",
    "canonicalize_payload",
    # Exceptions
    "InvalidManifestAlgorithmError",
    "MalformedManifestError",
    "SkillsSignerError",
    "UnknownKeyIdError",
    # Constants
    "KEY_ID_BYTES",
    "SIGNATURE_FIELDS_TO_STRIP",
    "SUPPORTED_ALGORITHM",
    # Key types and operations
    "Keypair",
    "generate_keypair",
    "load_or_create_keypair",
    "public_key_from_bytes",
    # Manifest types and operations
    "PubkeyManifest",
    "PubkeyManifestEntry",
    "build_pubkey_manifest",
    "manifest_entry_from_dict",
    "manifest_from_dict",
    "merge_manifests",
    # Signer
    "SignedPayload",
    "SkillsSigner",
    # Verification
    "verify_signature",
]
