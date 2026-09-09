"""Kotlin/Gradle hooks and task probing for crackerjack.

Per spec Kotlin F2: probes with ``./gradlew tasks --all`` before emitting a
hook. Tasks that are absent in the project's plugin set are filtered
out with a ``logger.warning()`` so the user knows the hook is skipped.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import Hook

logger = logging.getLogger(__name__)


class GradleTaskProbe:
    """Detect whether a Gradle task exists before invoking it.

    Per spec Kotlin F2: probe with ``./gradlew tasks --all -q --no-daemon
    --no-configuration-cache`` before invoking any Gradle task.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def has_task(self, task_name: str) -> bool:
        try:
            result = subprocess.run(
                ["./gradlew", "tasks", "--all", "-q", "--no-daemon", "--no-configuration-cache"],
                cwd=self._project_root, capture_output=True, text=True,
            )
        except FileNotFoundError:
            # gradlew not present in this environment (e.g. tests, minimal
            # install). Can't probe — assume present so capability wiring
            # still exposes the hook; runtime invocation will surface the
            # actual failure if the task is truly absent.
            logger.warning(
                "`./gradlew` not found in %s; assuming %r is present.",
                self._project_root,
                task_name,
            )
            return True
        if result.returncode != 0:
            logger.warning(
                "gradlew tasks --all failed (exit %d); treating %r as absent. "
                "stderr: %s",
                result.returncode,
                task_name,
                result.stderr.strip(),
            )
            return False
        return bool(re.search(rf"^{re.escape(task_name)}\s+", result.stdout, re.MULTILINE))


_HOOK_TASK_MAP: dict[str, str] = {
    "kotlin.ktlint": "ktlintCheck",
    "kotlin.detekt": "detekt",
}


def _build_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Build the three Kotlin hooks, filtering out absent tasks with a warning.

    Per spec Kotlin F2: skip-with-warning if the task is absent.
    ``kotlin.test`` is always emitted (every Kotlin project has the ``test``
    task if the kotlin/jvm plugin is applied; absence here is a plugin
    error, not a hook concern).
    """
    probe = GradleTaskProbe(project_root)
    gradlew = ("./gradlew",)
    hooks: list[Hook] = []
    for hook_name, task_name in _HOOK_TASK_MAP.items():
        if probe.has_task(task_name):
            hooks.append(Hook(name=hook_name, cli_command=(*gradlew, task_name)))
        else:
            logger.warning(
                "Skipping %s hook: `%s` task absent (add the plugin that provides it).",
                hook_name,
                task_name,
            )
    hooks.append(Hook(name="kotlin.test", cli_command=(*gradlew, "test")))
    return tuple(hooks)


def kotlin_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Return the three Kotlin hooks for a Gradle project root.

    Tasks that are absent in the project's plugin set are filtered out
    with a ``logger.warning()``. ``kotlin.test`` is always emitted.
    """
    return _build_hooks(project_root)
