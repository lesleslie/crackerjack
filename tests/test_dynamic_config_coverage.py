from pathlib import Path

import pytest

from crackerjack.dynamic_config import (
    CONFIG_MODES,
    HOOKS_REGISTRY,
    DynamicConfigGenerator,
    HookMetadata,
    add_experimental_hook,
    generate_config_for_mode,
    get_available_modes,
    remove_experimental_hook,
)


@pytest.fixture
def config_generator():
    return DynamicConfigGenerator()


class TestDynamicConfigGenerator:
    def test_init(self, config_generator) -> None:
        assert hasattr(config_generator, "template")
        assert hasattr(config_generator, "generate_config")

    def test_should_include_hook_tier_not_in_config(self, config_generator) -> None:
        hook: HookMetadata = {
            "id": "test - hook",
            "name": "test - hook",
            "repo": "https: / / example.com",
            "rev": "v1.0.0",
            "tier": 3,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        }
        config = CONFIG_MODES["fast"]

        result = config_generator._should_include_hook(hook, config, [])
        assert result is False

    def test_should_include_hook_experimental_disabled(self, config_generator) -> None:
        hook: HookMetadata = {
            "id": "test - hook",
            "name": "test - hook",
            "repo": "https: / / example.com",
            "rev": "v1.0.0",
            "tier": 1,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": True,
        }
        config = CONFIG_MODES["fast"]

        result = config_generator._should_include_hook(hook, config, [])
        assert result is False

    def test_should_include_hook_experimental_selective(self, config_generator) -> None:
        hook: HookMetadata = {
            "id": "test - hook",
            "name": "test - hook",
            "repo": "https: / / example.com",
            "rev": "v1.0.0",
            "tier": 1,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": True,
        }
        config = CONFIG_MODES["experimental"]
        enabled_experimental = ["other - hook"]

        result = config_generator._should_include_hook(
            hook,
            config,
            enabled_experimental,
        )
        assert result is False

    def test_should_include_hook_time_exceeded(self, config_generator) -> None:
        hook: HookMetadata = {
            "id": "slow - hook",
            "name": "slow - hook",
            "repo": "https: / / example.com",
            "rev": "v1.0.0",
            "tier": 1,
            "time_estimate": 10.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        }
        config = CONFIG_MODES["fast"]

        result = config_generator._should_include_hook(hook, config, [])
        assert result is False

    def test_filter_hooks_for_mode(self, config_generator) -> None:
        result = config_generator.filter_hooks_for_mode("fast")

        assert isinstance(result, list)
        assert len(result) > 0

        for hook in result:
            assert hook["tier"] in [1, 2]
            assert hook["time_estimate"] <= 5.0
            assert not hook["experimental"]

    def test_filter_hooks_for_mode_with_experimental(self, config_generator) -> None:
        result = config_generator.filter_hooks_for_mode("experimental", ["pyrefly"])

        assert isinstance(result, list)

        experimental_hooks = [h for h in result if h["experimental"]]
        if experimental_hooks:
            assert any(h["id"] == "pyrefly" for h in experimental_hooks)

    def test_group_hooks_by_repo(self, config_generator) -> None:
        hooks = [
            {
                "id": "hook1",
                "name": "hook1",
                "repo": "https: / / example.com / repo1",
                "rev": "v1.0.0",
                "tier": 1,
                "time_estimate": 1.0,
                "stages": None,
                "args": None,
                "files": None,
                "exclude": None,
                "additional_dependencies": None,
                "types_or": None,
                "language": None,
                "entry": None,
                "experimental": False,
            },
            {
                "id": "hook2",
                "name": "hook2",
                "repo": "https: / / example.com / repo1",
                "rev": "v1.0.0",
                "tier": 1,
                "time_estimate": 1.0,
                "stages": None,
                "args": None,
                "files": None,
                "exclude": None,
                "additional_dependencies": None,
                "types_or": None,
                "language": None,
                "entry": None,
                "experimental": False,
            },
        ]

        result = config_generator.group_hooks_by_repo(hooks)

        assert isinstance(result, dict)
        assert len(result) == 1
        key = ("https: / / example.com / repo1", "v1.0.0")
        assert key in result
        assert len(result[key]) == 2

    def test_get_repo_comment_known_repos(self, config_generator) -> None:
        result = config_generator._get_repo_comment(
            "https://github.com/pre-commit/pre-commit-hooks",
        )
        assert result == "File structure and format validators"

        result = config_generator._get_repo_comment("local")
        assert result == "Local tools and custom hooks"

    def test_get_repo_comment_security_keywords(self, config_generator) -> None:
        result = config_generator._get_repo_comment(
            "https://github.com/PyCQA/bandit",
        )
        assert result == "Security checks"

    def test_get_repo_comment_formatting_keywords(self, config_generator) -> None:
        result = config_generator._get_repo_comment(
            "https://github.com/astral-sh/ruff-pre-commit",
        )
        assert result == "Code formatting and quality"

    def test_get_repo_comment_unknown(self, config_generator) -> None:
        result = config_generator._get_repo_comment(
            "https://github.com/unknown/repo",
        )
        assert result is None

    def test_merge_configs(self, config_generator) -> None:
        base_config = {"project": {"name": "test"}, "existing": "value"}
        new_config = {"project": {"version": "1.0.0"}, "new": "value"}

        result = config_generator._merge_configs(base_config, new_config)

        assert result["project"]["name"] == "test"
        assert result["project"]["version"] == "1.0.0"
        assert result["existing"] == "value"
        assert result["new"] == "value"

    def test_generate_config(self, config_generator) -> None:
        result = config_generator.generate_config("fast")

        assert isinstance(result, str)
        assert "repos: " in result
        assert "- repo: " in result
        assert "hooks: " in result

    def test_create_temp_config(self, config_generator) -> None:
        result = config_generator.create_temp_config("fast")

        assert isinstance(result, Path)
        assert result.exists()
        assert result.suffix == ".yaml"
        assert "crackerjack - fast -" in result.name

        content = result.read_text()
        assert "repos: " in content

        result.unlink()


class TestModuleFunctions:
    def test_generate_config_for_mode(self) -> None:
        result = generate_config_for_mode("fast")

        assert isinstance(result, Path)
        assert result.exists()
        assert result.suffix == ".yaml"

        result.unlink()

    def test_get_available_modes(self) -> None:
        result = get_available_modes()

        assert isinstance(result, list)
        assert "fast" in result
        assert "comprehensive" in result
        assert "experimental" in result

    def test_add_experimental_hook(self) -> None:
        original_count = len(HOOKS_REGISTRY["experimental"])

        test_hook: HookMetadata = {
            "id": "test - experimental",
            "name": "test - experimental",
            "repo": "https: / / example.com",
            "rev": "v1.0.0",
            "tier": 3,
            "time_estimate": 2.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        }

        add_experimental_hook("test - experimental", test_hook)

        assert len(HOOKS_REGISTRY["experimental"]) == original_count + 1
        added_hook = next(
            h
            for h in HOOKS_REGISTRY["experimental"]
            if h["id"] == "test - experimental"
        )
        assert added_hook["experimental"] is True

    def test_remove_experimental_hook(self) -> None:
        test_hook: HookMetadata = {
            "id": "test - remove",
            "name": "test - remove",
            "repo": "https: / / example.com",
            "rev": "v1.0.0",
            "tier": 3,
            "time_estimate": 2.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": True,
        }
        HOOKS_REGISTRY["experimental"].append(test_hook)

        original_count = len(HOOKS_REGISTRY["experimental"])

        remove_experimental_hook("test - remove")

        assert len(HOOKS_REGISTRY["experimental"]) == original_count - 1
        assert not any(
            h["id"] == "test - remove" for h in HOOKS_REGISTRY["experimental"]
        )
