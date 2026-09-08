from __future__ import annotations

import shutil
from pathlib import Path
from unittest import mock

from crackerjack.adapters.swift.hooks import swift_hooks


def _write_package_swift(tmp_path: Path, body: str) -> Path:
    (tmp_path / "Package.swift").write_text(body)
    return tmp_path


_MACOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(name: "Demo", platforms: [.macOS(.v13)], products: [], targets: [])
"""
_IOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(name: "Demo", platforms: [.iOS(.v16)], products: [], targets: [])
"""


def test_swift_hooks_returns_nonempty_tuple(tmp_path: Path) -> None:
    _write_package_swift(tmp_path, _MACOS_ONLY)
    hooks = swift_hooks(tmp_path / "Package.swift")
    assert len(hooks) > 0


def test_swift_hooks_names_are_distinct(tmp_path: Path) -> None:
    _write_package_swift(tmp_path, _MACOS_ONLY)
    names = [h.name for h in swift_hooks(tmp_path / "Package.swift")]
    assert len(names) == len(set(names))
    for required in (
        "swift.test",
        "swift.build",
        "swift.format",
        "swift.package.update",
    ):
        assert required in names


def test_swift_hooks_does_not_include_destination_flag(tmp_path: Path) -> None:
    """Per BLOCKER B1: swift test does NOT accept -destination (xcodebuild-only).

    iOS-only packages fail at runtime when run via swift test. We document this
    limitation rather than passing an invalid flag.
    """
    _write_package_swift(tmp_path, _IOS_ONLY)
    hooks = swift_hooks(tmp_path / "Package.swift")
    for hook in hooks:
        joined = " ".join(hook.cli_command)
        assert "destination" not in joined.lower(), (
            f"Hook {hook.name!r} includes 'destination' — but swift test "
            f"doesn't support this flag. iOS-only packages need xcodebuild test."
        )


def test_swift_format_hook_autofix(tmp_path: Path) -> None:
    _write_package_swift(tmp_path, _MACOS_ONLY)
    hooks = swift_hooks(tmp_path / "Package.swift")
    format_hook = next(h for h in hooks if h.name == "swift.format")
    assert format_hook.autofix is True


def test_swift_package_update_hook_not_autofix(tmp_path: Path) -> None:
    """Per spec Swift F3: package update is autofix=false (modifies Package.resolved)."""
    _write_package_swift(tmp_path, _MACOS_ONLY)
    hooks = swift_hooks(tmp_path / "Package.swift")
    update_hook = next(h for h in hooks if h.name == "swift.package.update")
    assert update_hook.autofix is False


def test_swift_format_hook_prefers_third_party_when_available(tmp_path: Path) -> None:
    """If `swift-format` (third-party) is installed, the hook uses it.

    If not, falls back to built-in `swift format` with a warning.
    """
    _write_package_swift(tmp_path, _MACOS_ONLY)

    with mock.patch.object(shutil, "which", return_value="/usr/local/bin/swift-format"):
        hooks = swift_hooks(tmp_path / "Package.swift")
    format_hook = next(h for h in hooks if h.name == "swift.format")
    assert format_hook.cli_command[0] == "swift-format"


def test_swift_format_hook_falls_back_to_builtin(tmp_path: Path) -> None:
    """If swift-format is not installed, fall back to `swift format`."""
    _write_package_swift(tmp_path, _MACOS_ONLY)

    with mock.patch.object(shutil, "which", return_value=None):
        hooks = swift_hooks(tmp_path / "Package.swift")
    format_hook = next(h for h in hooks if h.name == "swift.format")
    assert format_hook.cli_command[0] == "swift"
    assert "format" in format_hook.cli_command
