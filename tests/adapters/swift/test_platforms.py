from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.swift.platforms import PlatformInfo, parse_platforms


def _write_package_swift(tmp_path: Path, body: str) -> Path:
    (tmp_path / "Package.swift").write_text(body)
    return tmp_path


_PACKAGE_SWIFT_MACOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.macOS(.v13)],
    products: [],
    targets: []
)
"""

_PACKAGE_SWIFT_IOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.iOS(.v16)],
    products: [],
    targets: []
)
"""

_PACKAGE_SWIFT_VISIONOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.visionOS(.v1)],
    products: [],
    targets: []
)
"""


def test_parse_platforms_macos_only(tmp_path: Path) -> None:
    _write_package_swift(tmp_path, _PACKAGE_SWIFT_MACOS_ONLY)
    info = parse_platforms(tmp_path / "Package.swift")
    assert info.platforms == ("macos",)
    assert info.requires_ios_destination is False
    assert info.requires_visionos_destination is False


def test_parse_platforms_ios_only(tmp_path: Path) -> None:
    _write_package_swift(tmp_path, _PACKAGE_SWIFT_IOS_ONLY)
    info = parse_platforms(tmp_path / "Package.swift")
    assert "ios" in info.platforms
    assert info.requires_ios_destination is True
    assert info.requires_visionos_destination is False


def test_parse_platforms_visionos_only(tmp_path: Path) -> None:
    """visionOS-only packages would need visionOS-Simulator destination, but
    Phase 2 doesn't support that — documents the limitation."""
    _write_package_swift(tmp_path, _PACKAGE_SWIFT_VISIONOS_ONLY)
    info = parse_platforms(tmp_path / "Package.swift")
    assert "visionos" in info.platforms
    assert info.requires_visionos_destination is True
    assert info.requires_ios_destination is False


def test_parse_platforms_multi_platform_includes_ios(tmp_path: Path) -> None:
    body = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [],
    targets: []
)
"""
    _write_package_swift(tmp_path, body)
    info = parse_platforms(tmp_path / "Package.swift")
    assert "ios" in info.platforms
    assert "macos" in info.platforms
    assert info.requires_ios_destination is True


def test_parse_platforms_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_platforms(tmp_path / "Package.swift")


def test_parse_platforms_no_platforms_directive_defaults_to_macos(tmp_path: Path) -> None:
    body = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    products: [],
    targets: []
)
"""
    _write_package_swift(tmp_path, body)
    info = parse_platforms(tmp_path / "Package.swift")
    assert info.requires_ios_destination is False
    assert info.requires_visionos_destination is False