"""LLM-backed code generation for the promotion pipeline.

The pipeline asks an LLM to derive a mechanical fixer from a
cached skill. Two implementations ship:

* :class:`StubLLMCodegen` — for tests and for ``promotion_enabled=False``
  (the pipeline never invokes it, but the attribute must be settable
  so type checks pass).
* :class:`ClaudeLLMCodegen` — real implementation, uses the
  ``LocalClaudeSubprocess`` from
  :mod:`crackerjack.agents.iterative_fix_agent` to spawn
  ``claude --print`` and return the generated source.

The Claude impl is gated behind ``enabled=True`` because spawning
``claude`` is expensive (~30-60s per call) and because the user
must explicitly opt in via ``--ai-fix-auto-promote``. With
``enabled=False``, ``generate_fixer`` raises :class:`PromotionDisabled`
so the pipeline's gate-2 (LLM call) returns a clear
``reason="llm_error:PromotionDisabled"`` rather than silently doing
nothing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# The prompt template for asking the LLM to derive a mechanical fixer
# from a cached skill. Kept here (not inside ClaudeLLMCodegen) so
# tests can assert on the prompt structure without spawning a
# subprocess.
PROMPT_TEMPLATE: str = """You are generating a Python mechanical fixer for the crackerjack ai-fix system.

# Signature (the pattern this fixer addresses)
{signature}

# Original error (the ty/refurb/etc. message that triggered the cached fix)
{original_error}

# Skill diff (the diff a Claude session produced to fix this issue; your fixer should produce the same behaviour)
{skill_diff}

# Output contract
Write a single Python file (no markdown fences) that defines a module exposing a function `apply(signature: str, issue: object) -> object`.

The function should:
1. Validate `signature` matches the signature above (return a result object indicating "no-op" if it doesn't match — do not crash).
2. Validate `issue` is a non-None object with the expected shape (the cached skill is for issues with file/line/message attributes).
3. Apply the fix and return a result object with `success=True`, `confidence=1.0`, `files_modified=[<the file path>]`.
4. On any error, return `success=False`, `confidence=0.0`, `remaining_issues=[<the error>]`.

The fixer must be pure-Python stdlib only (no third-party imports beyond what the project already uses). Keep it minimal — the goal is to reproduce the skill's behaviour mechanically, not to reimplement the LLM's reasoning.

Output the file contents, nothing else."""


class PromotionDisabled(RuntimeError):
    """Raised by :class:`ClaudeLLMCodegen` when ``enabled=False``."""


class StubLLMCodegen:
    """Test double for :class:`LLMCodegen`.

    Returns a canned string. Tests that need to assert on the prompt
    can read :attr:`last_prompt` to inspect what was sent.
    """

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
    """Real :class:`LLMCodegen` using ``LocalClaudeSubprocess``.

    The class wraps the existing ``LocalClaudeSubprocess`` worker
    from :mod:`crackerjack.agents.iterative_fix_agent` rather than
    spawning ``claude`` itself. The subprocess is sync (it calls
    ``subprocess.run`` internally); we offload to a thread so the
    async pipeline can await it without blocking the event loop.

    Like :class:`PromotionPipeline`, the class is gated on
    ``enabled``. With ``enabled=False``, ``generate_fixer`` raises
    immediately so the pipeline's gate-2 fails fast with a clear
    ``PromotionDisabled`` reason.
    """

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
        # LocalClaudeSubprocess.dispatch() is sync; offload so the
        # asyncio loop stays responsive.
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
        """LLMs often wrap code in ```python ... ``` fences. Strip them."""
        import re

        if "```" not in text:
            return text
        match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
        return match.group(1) if match else text

    @staticmethod
    def _sync_dispatch(subprocess_cls: type, prompt: str) -> object:
        """Off-thread ``claude --print`` invocation."""
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
