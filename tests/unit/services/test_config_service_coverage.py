"""Coverage-focused tests for ConfigService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError

from crackerjack.services.config_service import ConfigService


class SampleConfigModel(BaseModel):
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    enabled: bool = True


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        ConfigService.load_config(tmp_path / "missing.json")


def test_load_config_and_save_config(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{}")
    parser = MagicMock()
    parser.load.return_value = {"name": "app"}
    parser.save.return_value = None

    with patch(
        "crackerjack.services.config_service.ConfigParserRegistry.get_parser",
        return_value=parser,
    ), patch(
        "crackerjack.services.config_service.ConfigParserRegistry.get_parser_by_format",
        return_value=parser,
    ):
        config = ConfigService.load_config(path)
        ConfigService.save_config({"name": "app"}, path)
        ConfigService.save_config({"name": "app"}, tmp_path / "override.txt", format="json")

    assert config == {"name": "app"}
    parser.load.assert_called_once_with(path)
    assert parser.save.call_count == 2


@pytest.mark.asyncio
async def test_load_config_async_cleans_up_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text("name: app\n")
    parser = MagicMock()
    temp_path_holder: dict[str, Path] = {}

    def load_side_effect(temp_path: Path) -> dict[str, str]:
        temp_path_holder["path"] = temp_path
        assert temp_path.exists()
        return {"name": "app"}

    parser.load.side_effect = load_side_effect

    with patch(
        "crackerjack.services.config_service.ConfigParserRegistry.get_parser",
        return_value=parser,
    ), patch(
        "crackerjack.services.file_io_service.FileIOService.read_text_file",
        new=AsyncMock(return_value="name: app\n"),
    ):
        config = await ConfigService.load_config_async(path)

    assert config == {"name": "app"}
    temp_path = temp_path_holder["path"]
    assert not temp_path.exists()
    parser.load.assert_called_once()


def test_validate_config_success_and_failure() -> None:
    valid = {"name": "app", "version": "1.2.3"}
    model = ConfigService.validate_config(valid, SampleConfigModel)
    assert model.name == "app"

    with pytest.raises(ValidationError):
        ConfigService.validate_config({"name": "app", "version": "bad"}, SampleConfigModel)


def test_merge_configs_recurses_nested_dicts() -> None:
    base = {"name": "app", "nested": {"keep": True, "value": 1}}
    override = {"nested": {"value": 2, "new": "x"}, "enabled": True}

    result = ConfigService.merge_configs(base, override)

    assert result == {
        "name": "app",
        "nested": {"keep": True, "value": 2, "new": "x"},
        "enabled": True,
    }
