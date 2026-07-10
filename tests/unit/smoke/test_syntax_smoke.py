"""Smoke tests that import previously-syntactically-broken modules.

Regression coverage for the family of empty-class-body / empty-def-body
``IndentationError``s that periodically appear after partial writes. The
two named modules had pre-existing ``IndentationError``s that broke
``crackerjack``'s import chain (and thus blocked every CLI invocation).

These tests are intentionally trivial: just import the module and assert
the symbol exists. If the module cannot be imported, pytest will report
collection failure with the original ``IndentationError``.
"""

from __future__ import annotations


def test_ai_fix_llm_codegen_imports() -> None:
    from crackerjack.ai_fix import llm_codegen

    assert hasattr(llm_codegen, "PromotionDisabled")


def test_mahavishnu_workflows_progress_imports() -> None:
    from crackerjack.mahavishnu.workflows import progress

    assert hasattr(progress, "ProgressSnapshot")
    assert hasattr(progress, "InMemoryRecorder")
