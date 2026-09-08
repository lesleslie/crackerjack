from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import LanguageAdapter
from crackerjack.adapters.swift import SwiftAdapter


def test_swift_adapter_is_a_language_adapter() -> None:
    assert isinstance(SwiftAdapter(), LanguageAdapter)


def test_swift_adapter_detects_package_swift(tmp_path: Path) -> None:
    (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9\n")
    assert SwiftAdapter().detect(tmp_path) is True


def test_swift_adapter_skips_projects_without_package_swift(tmp_path: Path) -> None:
    """No Package.swift, no detection. No git init needed."""
    assert SwiftAdapter().detect(tmp_path) is False


def test_swift_adapter_capabilities_includes_lifecycle_and_hooks_and_version_source(tmp_path: Path) -> None:
    (tmp_path / "Package.swift").write_text(
        """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(name: "Demo", platforms: [.macOS(.v13)], products: [], targets: [])
"""
    )
    caps = SwiftAdapter().capabilities(tmp_path)

    assert caps.has_lifecycle is True
    assert caps.version_source is not None
    assert len(caps.hooks) > 0
    hook_names = [h.name for h in caps.hooks]
    assert "swift.test" in hook_names
    assert "swift.build" in hook_names
    assert "swift.format" in hook_names
    assert "swift.package.update" in hook_names
