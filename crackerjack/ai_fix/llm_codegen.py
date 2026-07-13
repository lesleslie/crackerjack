from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.agents.iterative_fix_agent import DispatchResult

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE: str = """You are generating a Python mechanical fixer for the crackerjack ai-fix system.


{signature}


{original_error}


{skill_diff}


Write a single Python file (no markdown fences) that defines a module exposing a function `apply(signature: str, issue: object) -> object`.

The function should:
1. Validate `signature` matches the signature above (return a result object indicating "no-op" if it doesn't match — do not crash).
2. Validate `issue` is a non-None object with the expected shape (the cached skill is for issues with file/line/message attributes).
3. Apply the fix and return a result object with `success=True`, `confidence=1.0`, `files_modified=[<the file path>]`.
4. On any error, return `success=False`, `confidence=0.0`, `remaining_issues=[<the error>]`.

The fixer must be pure-Python stdlib only (no third-party imports beyond what the project already uses). Keep it minimal — the goal is to reproduce the skill's behaviour mechanically, not to reimplement the LLM's reasoning.

Output the file contents, nothing else."""  # noqa: E501


class PromotionDisabled(RuntimeError):
    pass


class StubLLMCodegen:
    def __init__(self, canned_response: str = "# stub fixer\n") -> None:
        self._canned = canned_response
        self.last_signature: str | None = None
        self.last_original_error: str | None = None
        self.last_skill_diff: str | None = None
        self.call_count: int = 0

    async def generate_fixer(
        self,
        *,
        signature: str,
        original_error: str,
        skill_diff: str,
    ) -> str:
        self.call_count += 1
        self.last_signature = signature
        self.last_original_error = original_error
        self.last_skill_diff = skill_diff
        return self._canned


class ClaudeLLMCodegen:
    def __init__(
        self,
        *,
        enabled: bool = False,
        timeout_seconds: int = 600,
    ) -> None:
        self.enabled = enabled
        self._timeout_seconds = timeout_seconds

    async def generate_fixer(
        self,
        *,
        signature: str,
        original_error: str,
        skill_diff: str,
    ) -> str:
        if not self.enabled:
            raise PromotionDisabled(
                "ClaudeLLMCodegen is disabled. Pass --ai-fix-auto-promote "
                "to enable promotion."
            )

        from crackerjack.agents.iterative_fix_agent import LocalClaudeSubprocess

        prompt = PROMPT_TEMPLATE.format(
            signature=signature,
            original_error=original_error,
            skill_diff=skill_diff,
        )

        import asyncio

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            self._sync_dispatch,
            LocalClaudeSubprocess,
            prompt,
        )
        if not result.success:
            raise RuntimeError(
                f"claude --print failed for signature={signature}: {result.message}"
            )
        return self._strip_code_fences(result.diff or result.message)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        import re

        if "```" not in text:
            return text
        match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
        return match.group(1) if match else text

    @staticmethod
    def _sync_dispatch(subprocess_cls: type, prompt: str) -> DispatchResult:
        worker = subprocess_cls()
        return worker.dispatch(
            prompt=prompt,
            working_directory=None,  # type: ignore[arg-type]
            timeout_seconds=600,
        )


__all__ = [
    "ClaudeLLMCodegen",
    "PROMPT_TEMPLATE",
    "PromotionDisabled",
    "StubLLMCodegen",
]
