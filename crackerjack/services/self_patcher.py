from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    from crackerjack.services.improvement_generator import ImprovementProposal

logger = get_logger(__name__)


SELFPATCHER_DENY_PATHS: frozenset[str] = frozenset(
    {
        "crackerjack/config/hooks.py",
        "crackerjack/services/self_patcher.py",
        "crackerjack/services/improvement_generator.py",
        "crackerjack/services/failure_recorder.py",
        "crackerjack/core/secure_subprocess.py",
        "crackerjack/core/input_validator.py",
        "failure_metrics_repository.py",
        "constitution.py",
        "overseer.py",
        "hooks.py",
        "config/",
        "security/",
        "settings/",
        "mcp_server",
        ".env",
        "pyproject.toml",
        "settings/crackerjack.yaml",
        ".github/",
    }
)

_BANNED_DIFF_PATTERNS = [
    "GIT binary patch",
    "new mode 120000",
    "old mode 120000",
    "rename from ",
    "rename to ",
    ".git/",
]


def _path_matches_deny(path: str, deny: str) -> bool:

    if deny.endswith("/"):
        return path.startswith(deny) or f"/{deny}" in f"/{path}"

    basename = path.rsplit("/", 1)[-1]
    if basename == deny:
        return True

    if path == deny:
        return True

    if path.startswith(deny):
        return True

    if deny in path:
        return True
    return False


def _diff_touches_deny_path(diff: str) -> str | None:
    for line in diff.splitlines():
        if not line.startswith(("--- ", "+++ ")):
            continue
        path = line[4:].strip()

        if path.startswith(("a/", "b/")):
            path = path[2:]
        for deny in SELFPATCHER_DENY_PATHS:
            if _path_matches_deny(path, deny):
                return deny
    return None


def _diff_contains_banned_pattern(diff: str) -> str | None:
    for pat in _BANNED_DIFF_PATTERNS:
        if pat in diff:
            if "120000" in pat:
                return "symlink mode change detected"
            if "binary" in pat.lower():
                return "binary patch detected"
            return f"banned pattern: {pat!r}"
    return None


class SelfPatcher:
    def __init__(
        self,
        repo_root: Path,
        shadow_mode: bool = True,
        validation_timeout_seconds: int = 300,
    ) -> None:
        self._root = repo_root
        self._shadow_mode = shadow_mode
        self._timeout = validation_timeout_seconds

    @property
    def sentinel_path(self) -> Path:
        return self._root / ".crackerjack" / "self_patch.lock"

    def validate_diff(self, proposal: ImprovementProposal) -> tuple[bool, str]:
        banned = _diff_contains_banned_pattern(proposal.diff)
        if banned:
            return False, banned

        deny = _diff_touches_deny_path(proposal.diff)
        if deny:
            return False, f"diff touches deny-listed path: {deny}"

        return True, "ok"

    def _write_sentinel(self, improvement_id: str) -> None:
        self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        self.sentinel_path.write_text(improvement_id, encoding="utf-8")

    def _delete_sentinel(self) -> None:
        with __import__("contextlib").suppress(OSError):
            self.sentinel_path.unlink()

    def _apply_diff_to_working_tree(self, diff: str) -> None:
        result = subprocess.run(
            ["git", "apply", "--check"],
            input=diff,
            cwd=str(self._root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(f"git apply --check failed: {result.stderr}")
        subprocess.run(
            ["git", "apply"],
            input=diff,
            cwd=str(self._root),
            capture_output=True,
            text=True,
            check=True,
        )

    def _git_revert_working_tree(self) -> None:
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=str(self._root),
            capture_output=True,
        )

    def _git_commit(self, improvement_id: str) -> None:
        msg = (
            f"self-improvement: apply {improvement_id}\n\n"
            f"Improvement-Id: {improvement_id}"
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(self._root),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(self._root),
            capture_output=True,
            check=True,
        )

    async def _run_validation(self) -> tuple[bool, str]:
        proc = await asyncio.create_subprocess_exec(
            "crackerjack",
            "run",
            "--fast",
            cwd=str(self._root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        passed = proc.returncode == 0
        return passed, stdout.decode()

    async def startup_check(self) -> None:
        if not self.sentinel_path.exists():
            return
        logger.warning(
            "SelfPatcher crash sentinel found at %s — reverting working tree",
            self.sentinel_path,
        )
        self._git_revert_working_tree()
        self._delete_sentinel()

    async def apply(self, proposal: ImprovementProposal) -> dict[str, Any]:
        is_safe, reason = self.validate_diff(proposal)
        if not is_safe:
            return {
                "applied": False,
                "reverted": False,
                "committed": False,
                "shadow_mode": self._shadow_mode,
                "error": reason,
            }

        self._write_sentinel(proposal.improvement_id)
        try:
            self._apply_diff_to_working_tree(proposal.diff)
        except Exception as exc:
            self._delete_sentinel()
            return {
                "applied": False,
                "reverted": False,
                "committed": False,
                "shadow_mode": self._shadow_mode,
                "error": str(exc),
            }

        if self._shadow_mode:
            self._git_revert_working_tree()
            self._delete_sentinel()
            logger.info(
                "SelfPatcher shadow mode: proposal %s validated, not committed",
                proposal.improvement_id,
            )
            return {
                "applied": True,
                "reverted": True,
                "committed": False,
                "shadow_mode": True,
            }

        try:
            passed, _ = await asyncio.wait_for(
                self._run_validation(),
                timeout=float(self._timeout),
            )
        except TimeoutError:
            logger.error(
                "SelfPatcher: validation timed out after %ds — reverting",
                self._timeout,
            )
            self._git_revert_working_tree()
            self._delete_sentinel()
            return {
                "applied": True,
                "reverted": True,
                "committed": False,
                "shadow_mode": False,
                "error": "validation_timeout",
            }

        if not passed:
            self._git_revert_working_tree()
            self._delete_sentinel()
            return {
                "applied": True,
                "reverted": True,
                "committed": False,
                "shadow_mode": False,
            }

        self._git_commit(proposal.improvement_id)
        self._delete_sentinel()
        return {
            "applied": True,
            "reverted": False,
            "committed": True,
            "shadow_mode": False,
        }
