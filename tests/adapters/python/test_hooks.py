from __future__ import annotations

from crackerjack.adapters.python.hooks import python_hooks


def test_python_hooks_returns_nonempty_tuple() -> None:
    hooks = python_hooks()
    assert len(hooks) > 0


def test_python_hooks_are_immutable_dataclass_instances() -> None:
    for hook in python_hooks():
        assert hook.name
        assert hook.cli_command  # argv list, not empty
        assert isinstance(hook.cli_command, tuple)


def test_python_hooks_have_unique_names() -> None:
    names = [h.name for h in python_hooks()]
    assert len(names) == len(set(names))
