"""Version-aware binary resolution.

``shutil.which`` returns only the FIRST match on PATH, so an outdated
binary in an unrelated project's venv shadows a usable one installed
elsewhere. ``preferred_binary_command_with_min_version`` walks every
candidate and picks the first whose reported version satisfies the floor.
"""

from __future__ import annotations

import pytest

from crackerjack.config import tool_commands


class TestParseVersion:
    def test_extracts_dotted_version(self) -> None:
        assert tool_commands._parse_version("pyscn version 1.33.0") == (1, 33, 0)

    def test_extracts_two_component_version(self) -> None:
        assert tool_commands._parse_version("ruff 0.16.0") == (0, 16, 0)

    def test_returns_none_without_a_version(self) -> None:
        assert tool_commands._parse_version("no version here") is None


class TestVersionAtLeast:
    def test_newer_minor_satisfies_floor(self) -> None:
        assert tool_commands._version_at_least((1, 33, 0), (1, 30))

    def test_older_minor_does_not_satisfy_floor(self) -> None:
        assert not tool_commands._version_at_least((1, 5, 0), (1, 30))

    def test_equal_version_satisfies_floor(self) -> None:
        assert tool_commands._version_at_least((1, 30, 0), (1, 30))

    def test_shorter_reported_version_is_padded(self) -> None:
        assert tool_commands._version_at_least((1, 30), (1, 30, 0))

    def test_major_version_dominates(self) -> None:
        assert tool_commands._version_at_least((2, 0, 0), (1, 30))


class TestPreferredBinaryCommandWithMinVersion:
    def test_skips_candidate_below_the_floor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidates = ["/venvs/old/bin/pyscn", "/usr/local/bin/pyscn"]
        versions = {
            "/venvs/old/bin/pyscn": (1, 5, 0),
            "/usr/local/bin/pyscn": (1, 33, 0),
        }
        monkeypatch.setattr(tool_commands, "_binary_candidates", lambda _t: candidates)
        monkeypatch.setattr(
            tool_commands, "_probe_tool_version", lambda binary: versions[binary]
        )

        cmd = tool_commands.preferred_binary_command_with_min_version(
            "pyscn", "1.30", "analyze", "."
        )

        assert cmd == ["/usr/local/bin/pyscn", "analyze", "."]

    def test_prefers_the_first_qualifying_candidate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidates = ["/a/bin/pyscn", "/b/bin/pyscn"]
        versions = {"/a/bin/pyscn": (1, 33, 0), "/b/bin/pyscn": (2, 0, 0)}
        monkeypatch.setattr(tool_commands, "_binary_candidates", lambda _t: candidates)
        monkeypatch.setattr(
            tool_commands, "_probe_tool_version", lambda binary: versions[binary]
        )

        cmd = tool_commands.preferred_binary_command_with_min_version(
            "pyscn", "1.30", "check"
        )

        assert cmd == ["/a/bin/pyscn", "check"]

    def test_raises_and_names_every_inspected_candidate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidates = ["/venvs/old/bin/pyscn", "/opt/bin/pyscn"]
        versions = {"/venvs/old/bin/pyscn": (1, 5, 0), "/opt/bin/pyscn": (1, 2, 0)}
        monkeypatch.setattr(tool_commands, "_binary_candidates", lambda _t: candidates)
        monkeypatch.setattr(
            tool_commands, "_probe_tool_version", lambda binary: versions[binary]
        )

        with pytest.raises(RuntimeError) as excinfo:
            tool_commands.preferred_binary_command_with_min_version("pyscn", "1.30")

        message = str(excinfo.value)
        assert "pyscn >= 1.30 is required" in message
        assert "/venvs/old/bin/pyscn (version 1.5.0)" in message
        assert "/opt/bin/pyscn (version 1.2.0)" in message

    def test_rejects_an_unparseable_floor(self) -> None:
        with pytest.raises(ValueError, match="Invalid minimum version"):
            tool_commands.preferred_binary_command_with_min_version(
                "pyscn", "not-a-ver"
            )


class TestPyscnHookUsesVersionAwareResolution:
    @staticmethod
    def _pyscn_hook_command() -> list[str]:
        from crackerjack.config.tool_commands import get_tool_command

        try:
            return get_tool_command("pyscn")
        except RuntimeError as exc:
            pytest.skip(f"no pyscn >= 1.30 installed: {exc}")

    def test_pyscn_hook_resolves_to_an_absolute_path(self) -> None:
        cmd = self._pyscn_hook_command()

        assert cmd[0].endswith("pyscn"), f"expected a pyscn binary; got {cmd[0]!r}"
        assert cmd[0] != "pyscn", (
            "pyscn must resolve to an absolute path, not the bare name, so the "
            "version floor can be enforced"
        )

    def test_pyscn_hook_keeps_its_analysis_arguments(self) -> None:
        cmd = self._pyscn_hook_command()

        assert cmd[1:] == [
            "analyze",
            "--select",
            "complexity,deadcode",
            "--json",
            "--min-complexity",
            "5",
            "crackerjack",
        ]
