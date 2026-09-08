from __future__ import annotations

from crackerjack.adapters.base import Hook


def python_hooks() -> tuple[Hook, ...]:
    """Return the canonical Python hook set.

    Phase 1 maps to existing crackerjack hook categories. Each entry
    is a logical hook — ``crackerjack run`` invokes the full category,
    with per-tool sub-hooks aggregated into the parent by the runner
    via ``Hook.name`` lookup (see ``crackerjack/managers/hook_manager.py``).

    ``cli_command`` for each hook names a real invocation that
    crackerjack exposes today:

    * ``crackerjack run-tests`` for the test/coverage category (the
      actual subcommand; coverage is bundled via pytest-cov).
    * ``crackerjack run --tool <name>`` with a representative tool
      from each remaining category. The runner uses ``Hook.name`` to
      expand to the full set of tools in that category; the
      ``cli_command`` here is a concrete, invocable anchor.
    """
    return (
        Hook(
            name="python.lint",
            cli_command=("crackerjack", "run", "--tool", "ruff-check"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.format",
            cli_command=("crackerjack", "run", "--tool", "ruff-format"),
            timeout_seconds=300,
            autofix=True,
        ),
        Hook(
            name="python.test",
            cli_command=("crackerjack", "run-tests"),
            timeout_seconds=900,
        ),
        Hook(
            name="python.type-check",
            cli_command=("crackerjack", "run", "--tool", "ty"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.security",
            cli_command=("crackerjack", "run", "--tool", "semgrep"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.complexity",
            cli_command=("crackerjack", "run", "--tool", "complexipy"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.coverage",
            cli_command=("crackerjack", "run-tests"),
            timeout_seconds=600,
        ),
    )
