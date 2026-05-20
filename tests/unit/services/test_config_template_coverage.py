from pathlib import Path

from rich.console import Console

from crackerjack.services.config_template import (
    ConfigTemplateService,
    ConfigUpdateInfo,
    ConfigVersion,
)


def make_service(tmp_path: Path) -> ConfigTemplateService:
    return ConfigTemplateService(Console(), tmp_path)


def test_dataclasses_and_template_registry(tmp_path):
    service = make_service(tmp_path)

    update = ConfigUpdateInfo(
        config_type="pyproject",
        current_version="1.0.0",
        latest_version="1.2.0",
        needs_update=True,
    )
    template = ConfigVersion(version="1.2.0", config_data={"tool": {}})

    assert update.diff_preview == ""
    assert template.dependencies == []
    assert service.templates["pyproject"].version == "1.2.0"
    assert service.get_template("pyproject") is not None
    assert service.get_template("pyproject", version="1.2.0") is not None
    assert service.get_template("pyproject", version="0.0.1") is None
    assert service.get_template("missing") is None
    assert service.list_available_templates() == {
        "pyproject": "Modern Python project configuration with Ruff and pytest",
    }


def test_version_compare_and_current_versions(tmp_path):
    service = make_service(tmp_path)
    version_file = tmp_path / ".crackerjack-config.yaml"

    assert service._version_compare("1.0.0", "1.0.1") == -1
    assert service._version_compare("1.2.0", "1.2.0") == 0
    assert service._version_compare("2.0.0", "1.9.9") == 1
    assert service._load_current_versions(tmp_path / "missing.yaml") == {}

    version_file.write_text("not-a-mapping")
    assert service._load_current_versions(version_file) == {}

    version_file.write_text("configs: []")
    assert service._load_current_versions(version_file) == {}

    version_file.write_text(
        "configs:\n"
        "  pyproject:\n"
        "    version: 1.0.0\n"
        "  invalid: 1\n"
    )
    assert service._load_current_versions(version_file) == {"pyproject": "1.0.0"}


def test_collect_and_diff_helpers(tmp_path, monkeypatch):
    service = make_service(tmp_path)

    changes: list[str] = []
    service._collect_config_changes(
        {"tool": {"ruff": {"line-length": 80}, "remove": True}},
        {"tool": {"ruff": {"line-length": 88}, "new": "value"}},
        changes,
    )

    assert "+ Add tool.new: value" in changes
    assert "~ Change tool.ruff.line-length: 80 → 88" in changes
    assert "- Remove tool.remove" in changes
    assert service._create_config_diff(
        {"tool": {"ruff": {"line-length": 88}}},
        {"tool": {"ruff": {"line-length": 88}}},
    ) == "No changes detected"

    monkeypatch.setattr(
        service,
        "_collect_config_changes",
        lambda current, new, changes, path="": changes.extend(["line 1", "line 2"]),
    )
    assert service._create_config_diff({}, {}) == "line 1\nline 2"


def test_generate_diff_preview_branches(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    pyproject = tmp_path / "pyproject.toml"

    assert (
        service._generate_diff_preview("missing-type", tmp_path)
        == "Diff preview not available for this config type"
    )
    assert service._generate_diff_preview("pyproject", tmp_path) == (
        "Would create new pyproject.toml file"
    )

    pyproject.write_text("[build-system]\nrequires = []\n")
    monkeypatch.setattr(service, "get_template", lambda config_type, version=None: None)
    assert service._generate_diff_preview("pyproject", tmp_path) == "Template not found"

    monkeypatch.setattr(
        service,
        "get_template",
        lambda config_type, version=None: ConfigVersion(version="1.2.0", config_data={"tool": {}}),
    )
    monkeypatch.setattr(service, "_create_config_diff", lambda current, new: "preview")
    assert service._generate_diff_preview("pyproject", tmp_path) == "preview"

    pyproject.write_text("not toml")
    preview = service._generate_diff_preview("pyproject", tmp_path)
    assert preview.startswith("Error generating diff preview:")


def test_apply_update_and_version_tracking(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool]\nfoo = 1\n")

    monkeypatch.setattr(service, "_confirm_update", lambda: False)
    assert service.apply_update("pyproject", tmp_path, interactive=True) is False

    monkeypatch.setattr(service, "_confirm_update", lambda: True)
    assert service.apply_update("unknown", tmp_path) is False

    assert service.apply_update("pyproject", tmp_path) is True
    updated = pyproject.read_text()
    assert "target-version = \"py313\"" in updated

    tracking = tmp_path / ".crackerjack-config.yaml"
    tracking_text = tracking.read_text()
    assert "pyproject:" in tracking_text
    assert "version: 1.2.0" in tracking_text

    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    assert service.apply_update("pyproject", missing_dir) is False


def test_confirm_update_and_hashing(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("hello world")

    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    assert service._confirm_update() is True

    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert service._confirm_update() is False

    def raise_eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert service._confirm_update() is False
    assert service.get_config_hash(tmp_path / "missing.toml") == ""
    assert service.get_config_hash(config_path) == "b94d27b9934d3e08"
