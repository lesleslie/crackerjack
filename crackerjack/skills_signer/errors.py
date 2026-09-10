"""Exception hierarchy for the skills_signer package.

The verify boundary is the trust anchor for Phase 2/6 installers — when
verification fails, the caller must distinguish why so it can take the
right action. The hierarchy mirrors the failure modes:

- :class:`UnknownKeyIdError` — the key_id is not in the manifest. Likely
  cause: the server rotated its key without telling you. Action:
  re-fetch ``/health`` and retry; if still missing, fail-closed.

- :class:`MalformedManifestError` — the manifest data itself is wrong
  (missing fields, bad base64, unsupported algorithm). This is either
  a client bug (serializing wrong fields) or a server bug (sending a
  partial entry). Action: fail-closed; do not retry.

- :class:`SkillsSignerError` — base class. Catching this catches every
  signer failure, which is useful at the install boundary but loses
  the ability to dispatch by failure mode.

The hierarchy intentionally does NOT inherit from ``KeyError`` —
``UnknownKeyIdError`` is its own type so callers cannot accidentally
catch a ``KeyError`` raised by an inner ``dict`` lookup and treat it
as a manifest error. Installers must catch each type explicitly.
"""

from __future__ import annotations


class SkillsSignerError(Exception):
    """Base class for all skills_signer exceptions."""


class UnknownKeyIdError(SkillsSignerError):
    """The key_id is not present in the manifest.

    Raised by :func:`crackerjack.skills_signer.verify.verify_signature` when
    the manifest does not contain the claimed key_id. The most common
    cause is server-side key rotation: the client holds a stale manifest
    and the server has published a new key. Action: re-fetch ``/health``
    and retry; if still missing, fail-closed.
    """


class MalformedManifestError(SkillsSignerError):
    """A manifest entry is missing required fields or has invalid data.

    Raised by :func:`crackerjack.skills_signer.manifest.manifest_entry_from_dict`
    when the input dict is not a well-formed manifest entry. This is
    either a client bug (serializing wrong fields) or a server bug
    (sending a partial entry). Action: fail-closed; do not retry.
    """


class InvalidManifestAlgorithmError(MalformedManifestError):
    """The algorithm field is not the supported ``"ed25519"``.

    Raised by :func:`crackerjack.skills_signer.manifest.manifest_entry_from_dict`
    when the entry claims a signing algorithm other than ed25519.
    Currently a no-op since only ed25519 is supported, but the check
    is defense-in-depth against a future algorithm migration that
    could introduce downgrade attacks.
    """


__all__ = [
    "InvalidManifestAlgorithmError",
    "MalformedManifestError",
    "SkillsSignerError",
    "UnknownKeyIdError",
]
