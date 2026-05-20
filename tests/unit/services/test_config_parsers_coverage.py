"""Coverage-focused tests for config parsers and registry."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.config_parsers import (
    ConfigParserRegistry,
    JSONParser,
    TOMLParser,
    YAMLParser,
)


def test_registry_basic_operations(tmp_path: Path) -> None:
    original = ConfigParserRegistry._parsers.copy()
    try:
        ConfigParserRegistry._parsers = {}
        json_parser = JSONParser()
        yaml_parser = YAMLParser()
        toml_parser = TOMLParser()

        ConfigParserRegistry.register(json_parser)
        ConfigParserRegistry.register(yaml_parser)
        ConfigParserRegistry.register(toml_parser)
        ConfigParserRegistry.register(json_parser)

        assert ConfigParserRegistry.list_formats() == ["json", "toml", "yaml", "yml"]
        assert ConfigParserRegistry.is_supported(tmp_path / "file.json") is True
        assert ConfigParserRegistry.is_supported(tmp_path / "file.txt") is False
        assert ConfigParserRegistry.get_parser(tmp_path / "file.json") is json_parser
        assert ConfigParserRegistry.get_parser_by_format("yaml") is yaml_parser

        with pytest.raises(ValueError, match="Unsupported config format"):
            ConfigParserRegistry.get_parser(tmp_path / "file.ini")
        with pytest.raises(ValueError, match="Unsupported config format"):
            ConfigParserRegistry.get_parser_by_format("ini")
    finally:
        ConfigParserRegistry._parsers = original


def test_json_and_yaml_parsers_round_trip(tmp_path: Path) -> None:
    json_parser = JSONParser()
    yaml_parser = YAMLParser()

    json_path = tmp_path / "settings.json"
    yaml_path = tmp_path / "settings.yaml"

    json_parser.save({"name": "app"}, json_path)
    yaml_parser.save({"name": "app"}, yaml_path)

    assert json_parser.load(json_path) == {"name": "app"}
    assert yaml_parser.load(yaml_path) == {"name": "app"}

    json_path.write_text("{invalid json")
    yaml_path.write_text("name: [unclosed")

    with pytest.raises(ValueError):
        json_parser.load(json_path)
    with pytest.raises(ValueError):
        yaml_parser.load(yaml_path)


def test_toml_parser_round_trip_and_missing_file(tmp_path: Path) -> None:
    toml_parser = TOMLParser()
    toml_path = tmp_path / "settings.toml"

    with patch.dict(sys.modules, {"tomli_w": MagicMock(dumps=lambda data: "name = \"app\"\n")}, clear=False):
        toml_parser.save({"name": "app"}, toml_path)

    assert toml_parser.load(toml_path)["name"] == "app"

    with pytest.raises(FileNotFoundError):
        toml_parser.load(tmp_path / "missing.toml")

    with patch.object(TOMLParser, "_load_toml_from_text", side_effect=Exception("bad toml")):
        toml_path.write_text("invalid = true")
        with pytest.raises(ValueError):
            toml_parser.load(toml_path)
