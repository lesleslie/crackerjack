"""Refurb must run with Mypy flags that keep it from type-checking the world.

Refurb drives Mypy internally (Mypy is a hard dependency, not a pluggable
backend), so Mypy's own flags are its only speed lever. Without them the
hook analyzes the whole third-party dependency graph -- ~8,100 modules to lint
~120 files -- costing 120s to 670s per run.

Refurb *replaces* the config-file ``mypy_args`` when flags are given on the
command line, so the flags Crackerjack passes have to come from the
repository's own ``[tool.refurb].mypy_args``. That config is authoritative
when present -- including when it is explicitly empty, which is how a
repository opts out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.config.refurb_args import (
    DEFAULT_REFURB_MYPY_ARGS,
    build_refurb_mypy_args,
    build_refurb_mypy_args_for_file_list,
    read_repo_refurb_mypy_args,
    resolve_refurb_mypy_args,
    resolve_refurb_mypy_args_for_file_list,
)


def _write_pyproject(repo_root: Path, body: str) -> None:
    (repo_root / "pyproject.toml").write_text(body, encoding="utf-8")


class TestReadRepoRefurbMypyArgs:
    def test_returns_none_when_no_pyproject(self, tmp_path: Path) -> None:
        assert read_repo_refurb_mypy_args(tmp_path) is None

    def test_none_repo_root_falls_back_to_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """None means "the repo I am running in", not "no repo"."""
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--from-cwd"]\n',
        )
        monkeypatch.chdir(tmp_path)

        assert read_repo_refurb_mypy_args(None) == ["--from-cwd"]

    def test_returns_none_when_pyproject_has_no_refurb_table(
        self, tmp_path: Path
    ) -> None:
        _write_pyproject(tmp_path, '[project]\nname = "demo"\n')
        assert read_repo_refurb_mypy_args(tmp_path) is None

    def test_reads_configured_args(self, tmp_path: Path) -> None:
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--follow-imports=normal"]\n',
        )
        assert read_repo_refurb_mypy_args(tmp_path) == ["--follow-imports=normal"]

    def test_explicit_empty_list_is_distinguishable_from_absent(
        self, tmp_path: Path
    ) -> None:
        _write_pyproject(tmp_path, "[tool.refurb]\nmypy_args = []\n")
        assert read_repo_refurb_mypy_args(tmp_path) == []

    def test_unparseable_pyproject_is_ignored(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, "this is not valid toml [[[")
        assert read_repo_refurb_mypy_args(tmp_path) is None

    def test_non_list_mypy_args_is_ignored(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, '[tool.refurb]\nmypy_args = "nope"\n')
        assert read_repo_refurb_mypy_args(tmp_path) is None

    def test_non_table_tool_section_is_ignored(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, 'tool = "not-a-table"\n')
        assert read_repo_refurb_mypy_args(tmp_path) is None

    def test_non_table_refurb_section_is_ignored(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, "[tool]\nrefurb = 5\n")
        assert read_repo_refurb_mypy_args(tmp_path) is None


class TestResolveRefurbMypyArgs:
    def test_defaults_apply_when_repo_has_no_config(self, tmp_path: Path) -> None:
        assert resolve_refurb_mypy_args(tmp_path) == list(DEFAULT_REFURB_MYPY_ARGS)

    def test_repo_config_replaces_the_defaults(self, tmp_path: Path) -> None:
        """One knob controls the flags: the repository's own config."""
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--follow-imports=normal"]\n',
        )
        resolved = resolve_refurb_mypy_args(tmp_path)
        assert resolved == ["--follow-imports=normal"]

    def test_repo_can_opt_out_with_an_empty_list(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, "[tool.refurb]\nmypy_args = []\n")
        assert resolve_refurb_mypy_args(tmp_path) == []

    def test_explicit_defaults_are_used_when_repo_has_no_config(
        self, tmp_path: Path
    ) -> None:
        resolved = resolve_refurb_mypy_args(tmp_path, defaults=["--only-this"])
        assert resolved == ["--only-this"]

    def test_repo_config_wins_over_explicit_defaults(self, tmp_path: Path) -> None:
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--repo-flag"]\n',
        )
        resolved = resolve_refurb_mypy_args(tmp_path, defaults=["--default-flag"])
        assert resolved == ["--repo-flag"]


class TestBuildRefurbMypyArgs:
    def test_emits_separator_before_flags(self, tmp_path: Path) -> None:
        args = build_refurb_mypy_args(tmp_path)
        assert args[0] == "--"
        assert "--follow-imports=skip" in args

    def test_empty_defaults_yields_no_separator(self, tmp_path: Path) -> None:
        assert build_refurb_mypy_args(tmp_path, defaults=[]) == []


class TestRefurbHookCommand:
    def test_hook_command_carries_mypy_flags(self, tmp_path: Path) -> None:
        from crackerjack.config.tool_commands import get_tool_command

        cmd = get_tool_command("refurb", pkg_path=tmp_path)

        assert "--" in cmd, f"refurb command must pass Mypy flags; got {cmd!r}"
        separator = cmd.index("--")
        assert "--follow-imports=skip" in cmd[separator:]
        assert "--ignore-missing-imports" in cmd[separator:]

    def test_hook_command_uses_repo_config_authoritatively(
        self, tmp_path: Path
    ) -> None:
        """A repo that configures mypy_args controls the flags outright."""
        from crackerjack.config.tool_commands import get_tool_command

        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--follow-imports=normal"]\n',
        )
        cmd = get_tool_command("refurb", pkg_path=tmp_path)
        tail = cmd[cmd.index("--") :]

        assert "--follow-imports=normal" in tail, (
            f"repo's own Mypy flags must survive; got {cmd!r}"
        )
        assert "--follow-imports=skip" not in tail, (
            f"the repo's config replaces the defaults; got {cmd!r}"
        )

    def test_repo_can_opt_out_with_empty_mypy_args(self, tmp_path: Path) -> None:
        """An explicitly empty list is how a repo turns the flags off."""
        from crackerjack.config.tool_commands import get_tool_command

        _write_pyproject(tmp_path, "[tool.refurb]\nmypy_args = []\n")
        cmd = get_tool_command("refurb", pkg_path=tmp_path)

        assert "--follow-imports=skip" not in cmd, f"got {cmd!r}"

    def test_other_hooks_are_unaffected(self, tmp_path: Path) -> None:
        from crackerjack.config.tool_commands import get_tool_command

        cmd = get_tool_command("ruff-check", pkg_path=tmp_path)

        assert "--follow-imports=skip" not in cmd


class TestFileListMypyArgs:
    """The file-list scan path needs its own flags.

    A file-list scan must not skip imports (the sibling modules fall
    outside Mypy's build set and their types degrade to ``Any``), but the
    repository's other flags have to survive: dropping
    ``--ignore-missing-imports`` turns an absent optional dependency into a
    Mypy import error, which Refurb exits 1 on -- and the tool adapter
    treats "exit 1 with output" as success, so the check would report "No
    issues found" while Mypy had actually failed.
    """

    def test_forces_normal_but_keeps_the_other_flags(self, tmp_path: Path) -> None:
        _write_pyproject(
            tmp_path,
            "[tool.refurb]\n"
            'mypy_args = ["--follow-imports=skip", "--ignore-missing-imports"]\n',
        )
        args = resolve_refurb_mypy_args_for_file_list(tmp_path)

        assert args == ["--follow-imports=normal", "--ignore-missing-imports"], (
            f"got {args!r}"
        )

    def test_keeps_other_flags_when_no_follow_imports_configured(
        self, tmp_path: Path
    ) -> None:
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--ignore-missing-imports"]\n',
        )
        args = resolve_refurb_mypy_args_for_file_list(tmp_path)

        assert args == ["--follow-imports=normal", "--ignore-missing-imports"], (
            f"got {args!r}"
        )

    def test_replaces_rather_than_appends_follow_imports(self, tmp_path: Path) -> None:
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--follow-imports=skip"]\n',
        )
        args = resolve_refurb_mypy_args_for_file_list(tmp_path)

        assert args == ["--follow-imports=normal"], f"got {args!r}"
        assert "--follow-imports=skip" not in args, f"got {args!r}"

    def test_handles_the_space_separated_form(self, tmp_path: Path) -> None:
        """Mypy accepts '--follow-imports skip' as well as the '=' form."""
        _write_pyproject(
            tmp_path,
            '[tool.refurb]\nmypy_args = ["--follow-imports", "skip"]\n',
        )
        args = resolve_refurb_mypy_args_for_file_list(tmp_path)

        assert args == ["--follow-imports=normal"], f"got {args!r}"
        assert "skip" not in args, f"got {args!r}"

    def test_space_separated_form_keeps_other_flags(self, tmp_path: Path) -> None:
        _write_pyproject(
            tmp_path,
            "[tool.refurb]\n"
            'mypy_args = ["--follow-imports", "skip", "--ignore-missing-imports"]\n',
        )
        args = resolve_refurb_mypy_args_for_file_list(tmp_path)

        assert args == ["--follow-imports=normal", "--ignore-missing-imports"], (
            f"got {args!r}"
        )

    def test_builds_a_separator_prefixed_tail(self, tmp_path: Path) -> None:
        tail = build_refurb_mypy_args_for_file_list(tmp_path)

        assert tail[0] == "--"
        assert "--follow-imports=normal" in tail


class TestRefurbHookBuildCommand:
    """Regression coverage for the assembled command, not just the base one.

    ``HookDefinition.build_command`` appends source targets to the base
    command. Once the base command ends with the ``--`` separator that
    Refurb forwards to Mypy, an appended path becomes a Mypy argument
    instead of a target, and mypy rejects the whole argv with
    "unrecognized arguments" -- the hook then fails with zero findings,
    silently ceasing to gate anything.
    """

    @staticmethod
    def _refurb_hook() -> object:
        from crackerjack.config import hooks

        return next(h for h in hooks.COMPREHENSIVE_HOOKS if h.name == "refurb")

    def test_no_target_lands_after_the_separator(self) -> None:
        hook = self._refurb_hook()

        cmd = hook.build_command([Path("crackerjack/core/preflight.py")])
        separator = cmd.index("--")
        tail = cmd[separator + 1 :]

        assert tail, "the Mypy flags must still be present"
        for arg in tail:
            assert arg.startswith("-"), (
                f"only Mypy flags may follow the separator; got {arg!r} in {cmd!r}"
            )

    def test_the_package_target_is_not_duplicated(self) -> None:
        """Passing both a package dir and a file inside it is a mypy error."""
        hook = self._refurb_hook()

        cmd = hook.build_command([Path("crackerjack/core/preflight.py")])
        separator = cmd.index("--")
        targets = cmd[3:separator]

        assert targets == ["crackerjack/"], f"got {targets!r}"
        assert len(targets) == len(set(targets)), f"duplicate target in {targets!r}"

    def test_build_command_does_not_mutate_the_cached_command(self) -> None:
        """build_command used to mutate the shared cached list in place."""
        hook = self._refurb_hook()

        before = hook.get_command().copy()
        hook.build_command([Path("crackerjack/core/preflight.py")])

        assert hook.get_command() == before, (
            "build_command must not mutate the cached command"
        )

    def test_assembled_command_parses_under_mypy(self) -> None:
        """The argv Refurb hands to mypy must survive mypy's own parser."""
        from mypy.main import process_options

        hook = self._refurb_hook()
        cmd = hook.build_command([Path("crackerjack/core/preflight.py")])

        # Skip the interpreter and "-m refurb"; what is left is what
        # refurb forwards to mypy: targets then the "--" separated flags.
        argv = cmd[3:]
        separator = argv.index("--")
        mypy_argv = [*argv[:separator], *argv[separator + 1 :]]

        files, _options = process_options(mypy_argv)
        assert files, f"mypy did not pick up the target from {mypy_argv!r}"
