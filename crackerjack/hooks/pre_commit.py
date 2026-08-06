from __future__ import annotations

import asyncio
import pathlib
import sys

from crackerjack.hooks.skill_coverage import (
    pre_commit_skill_coverage_gate,
)


def main(repo_path: pathlib.Path | None = None) -> int:
    resolved = repo_path if repo_path is not None else pathlib.Path.cwd()
    return asyncio.run(pre_commit_skill_coverage_gate(resolved))


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "pre_commit_skill_coverage_gate"]
