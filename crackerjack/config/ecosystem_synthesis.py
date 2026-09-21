"""Ecosystem-level publish_url synthesis for cross-repo Bodai orchestration.

When Mahavishnu dispatches ``crackerjack -p minor`` to a per-repo worker, the
worker needs the right ``publish_url`` without each repo having to repeat it
in its own ``settings/local.yaml``. The Bodai ecosystem registry
(``settings/ecosystem.yaml`` in the Mahavishnu repo) is the canonical source
for per-repo publish config — adding ``publish: { url, token_env }`` to a
repo entry there makes that URL flow to that repo's crackerjack invocation
without per-repo configuration duplication.

This module reads that file (when ``BODAI_ECOSYSTEM_CONFIG`` points at it)
and synthesizes the missing ``publishing.publish_url`` setting for the
current repo. Path-matching (against ``Path.cwd()``) identifies the repo;
path-equal resolution is exact so operator typos in ``ecosystem.yaml``
paths won't silently route to a different repo.

Priority (highest → lowest):

1. ``--publish-url`` CLI flag                  [handled by Typer]
2. ``CRACKERJACK_PUBLISH_URL`` env var         [handled by Typer]
3. ecosystem.yaml lookup via this module      [THIS MODULE]
4. ``publishing.publish_url`` in settings YAML [handled by loader]
5. Unset → PyPI default                        [handled by PublishManagerImpl]

The module is intentionally a small, side-effect-free helper called from
``crackerjack.config.loader.load_settings``. The loader invokes it AFTER
merging YAML files but BEFORE the field filter, so the synthesized value
is treated identically to a user-written YAML key. The CLI flag and env
var take precedence over this lookup because Typer writes them to
``Options.publish_url`` BEFORE the loader runs.
"""

from __future__ import annotations

import logging
import os
import typing as t
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

ENV_VAR_NAME = "BODAI_ECOSYSTEM_CONFIG"


def _read_ecosystem_publish_config(
    ecosystem_path: Path, cwd: Path
) -> tuple[str | None, str | None]:
    """Return ``(publish_url, publish_token_env)`` for the cwd-matching repo.

    Both fields default to ``None`` when:

    - the file is unreadable / unparsable,
    - the cwd doesn't match any registered repo,
    - the matched repo has no ``publish`` block, or
    - the operator hasn't filled in the URL yet (token_env is
      optional — URL is the required field for a ``publish`` block
      to be considered "configured").

    Path matching is exact (``Path.resolve()`` of both sides) to avoid
    silently routing to the wrong repo when two repos share a parent
    directory.
    """
    try:
        with ecosystem_path.open() as handle:
            data: t.Any = yaml.safe_load(handle)
    except (yaml.YAMLError, OSError, FileNotFoundError) as exc:
        logger.debug(
            f"BODAI_ECOSYSTEM_CONFIG: failed to read {ecosystem_path}: {exc}",
        )
        return None, None

    if not isinstance(data, dict):
        return None, None

    repos = data.get("repos")
    if not isinstance(repos, list):
        return None, None

    cwd_resolved = cwd.resolve()
    for entry in repos:
        if not isinstance(entry, dict):
            continue
        repo_path_str = entry.get("path")
        if not isinstance(repo_path_str, str):
            continue
        try:
            repo_path = Path(repo_path_str).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            logger.debug(
                f"BODAI_ECOSYSTEM_CONFIG: bad path {repo_path_str!r}: {exc}",
            )
            continue
        if repo_path != cwd_resolved:
            continue

        publish = entry.get("publish")
        if not isinstance(publish, dict):
            return None, None
        url = publish.get("url")
        url_value = url if isinstance(url, str) and url else None
        token_env_raw = publish.get("token_env")
        token_env_value = (
            token_env_raw if isinstance(token_env_raw, str) and token_env_raw else None
        )
        return url_value, token_env_value

    return None, None


def _read_ecosystem_publish_url(ecosystem_path: Path, cwd: Path) -> str | None:
    """Backwards-compat shim returning only the URL.

    Kept so any out-of-tree caller (or older test) still compiles.
    New code should call :func:`_read_ecosystem_publish_config` so it
    can pick up ``token_env`` in the same pass.
    """
    return _read_ecosystem_publish_config(ecosystem_path, cwd)[0]


def apply_ecosystem_publish_synthesis(
    merged_data: dict[str, t.Any],
    cwd: Path,
) -> bool:
    """Synthesize ``publishing.publish_url`` from the ecosystem registry.

    Mutates ``merged_data`` in place: if ``BODAI_ECOSYSTEM_CONFIG`` points at
    an ecosystem file AND the current cwd matches a registered repo's path
    AND that repo's ``publish.url`` is set AND the merged YAML has not
    already populated ``publishing.publish_url``, write the URL into
    ``merged_data["publishing"]["publish_url"]``.

    The settings-YAML value wins over the ecosystem value: if the operator
    has set the URL in their ``local.yaml``, the synthesis skips. This
    preserves the "explicit per-repo config beats ecosystem-wide default"
    invariant that operators expect.

    Returns ``True`` when a value was synthesized, ``False`` otherwise.
    The boolean lets tests assert that the hook ran without coupling to
    the internal merged_data shape.
    """
    env_path_str = os.environ.get(ENV_VAR_NAME)
    if not env_path_str:
        return False

    # Already-set YAML value wins (explicit operator override).
    publishing = merged_data.get("publishing")
    if not isinstance(publishing, dict):
        publishing = {}
        merged_data["publishing"] = publishing
    if publishing.get("publish_url"):
        return False

    ecosystem_path = Path(env_path_str).expanduser()
    if not ecosystem_path.is_file():
        logger.debug(
            f"BODAI_ECOSYSTEM_CONFIG path is not a file: {ecosystem_path}",
        )
        return False

    url, token_env = _read_ecosystem_publish_config(ecosystem_path, cwd)
    if url is None:
        return False

    publishing["publish_url"] = url
    if token_env is not None:
        # Caller-set YAML value still wins — explicit per-repo token_env in
        # ``settings/local.yaml`` overrides the ecosystem default, matching
        # the "explicit beats default" invariant for ``publish_url``.
        if not publishing.get("publish_token_env"):
            publishing["publish_token_env"] = token_env
    logger.debug(
        "BODAI_ECOSYSTEM_CONFIG: synthesized publish_url="
        f"{url} token_env={token_env!r} for cwd={cwd}",
    )
    return True
