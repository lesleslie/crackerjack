from crackerjack.dynamic_config import (
    HOOKS_REGISTRY,
    DynamicConfigGenerator,
    HookMetadata,
    add_experimental_hook,
    get_available_modes,
    remove_experimental_hook,
)


class TestDynamicConfigGenerator:
    def test_should_include_hook_experimental_disabled(self) -> None:
        generator = DynamicConfigGenerator()
        hook: HookMetadata = {
            "id": "test - hook",
            "name": "test",
            "tier": 1,
            "experimental": True,
            "time_estimate": 5,
            "repo": "https: // github.com / test / test",
            "rev": "v1.0.0",
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
        }
        config = {"tiers": [1], "experimental": False, "max_time": 10.0, "stages": []}
        result = generator._should_include_hook(hook, config, [])
        assert not result

    def test_should_include_hook_experimental_selective(self) -> None:
        generator = DynamicConfigGenerator()
        hook: HookMetadata = {
            "id": "test - hook",
            "name": "test",
            "tier": 1,
            "experimental": True,
            "time_estimate": 5,
            "repo": "https: // github.com / test / test",
            "rev": "v1.0.0",
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
        }
        config = {"tiers": [1], "experimental": True, "max_time": 10.0, "stages": []}
        result = generator._should_include_hook(hook, config, ["other - hook"])
        assert not result
        result = generator._should_include_hook(hook, config, ["test - hook"])
        assert result

    def test_should_include_hook_time_limit_exceeded(self) -> None:
        generator = DynamicConfigGenerator()
        hook: HookMetadata = {
            "id": "slow - hook",
            "name": "slow",
            "tier": 1,
            "experimental": False,
            "time_estimate": 15,
            "repo": "https: // github.com / test / test",
            "rev": "v1.0.0",
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
        }
        config = {"tiers": [1], "experimental": False, "max_time": 10.0, "stages": []}
        result = generator._should_include_hook(hook, config, [])
        assert not result

    def test_get_repo_comment_local_tools(self) -> None:
        generator = DynamicConfigGenerator()
        result = generator._get_repo_comment("local")
        assert result == "Local tools and custom hooks"

    def test_get_repo_comment_unknown(self) -> None:
        generator = DynamicConfigGenerator()
        result = generator._get_repo_comment("https: // github.com / unknown / repo")
        assert result is None


def test_get_available_modes() -> None:
    modes = get_available_modes()
    assert isinstance(modes, list)
    assert modes
    assert "fast" in modes
    assert "comprehensive" in modes


def test_add_experimental_hook() -> None:
    original_count = len(HOOKS_REGISTRY["experimental"])
    test_hook: HookMetadata = {
        "id": "test - experimental",
        "name": "test",
        "tier": 2,
        "experimental": False,
        "time_estimate": 5,
        "repo": "https: // github.com / test / test",
        "rev": "v1.0.0",
        "stages": None,
        "args": None,
        "files": None,
        "exclude": None,
        "additional_dependencies": None,
        "types_or": None,
        "language": None,
        "entry": None,
    }
    add_experimental_hook("test - experimental", test_hook)
    assert len(HOOKS_REGISTRY["experimental"]) == original_count + 1
    assert test_hook["experimental"] is True
    remove_experimental_hook("test - experimental")


def test_remove_experimental_hook() -> None:
    test_hook: HookMetadata = {
        "id": "test - removable",
        "name": "test",
        "tier": 2,
        "experimental": True,
        "time_estimate": 5,
        "repo": "https: // github.com / test / test",
        "rev": "v1.0.0",
        "stages": None,
        "args": None,
        "files": None,
        "exclude": None,
        "additional_dependencies": None,
        "types_or": None,
        "language": None,
        "entry": None,
    }
    add_experimental_hook("test - removable", test_hook)
    original_count = len(HOOKS_REGISTRY["experimental"])
    remove_experimental_hook("test - removable")
    assert len(HOOKS_REGISTRY["experimental"]) == original_count - 1
    remaining_hooks = [h["id"] for h in HOOKS_REGISTRY["experimental"]]
    assert "test - removable" not in remaining_hooks
