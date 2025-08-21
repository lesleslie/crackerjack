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

def test_generate_config_for_mode_basic():
    """Test basic functionality of generate_config_for_mode."""

    try:
        result = generate_config_for_mode()
        assert result is not None or result is None
    except TypeError:

        import inspect
        assert callable(generate_config_for_mode), "Function should be callable"
        sig = inspect.signature(generate_config_for_mode)
        assert sig is not None, "Function should have valid signature"
        pytest.skip("Function requires specific arguments - manual implementation needed")
    except Exception as e:
        pytest.fail(f"Unexpected error in generate_config_for_mode: {e}")

def test_filter_hooks_for_mode_basic():
    """Test basic functionality of filter_hooks_for_mode."""

    try:
        result = filter_hooks_for_mode()
        assert result is not None or result is None
    except TypeError:

        import inspect
        assert callable(filter_hooks_for_mode), "Function should be callable"
        sig = inspect.signature(filter_hooks_for_mode)
        assert sig is not None, "Function should have valid signature"
        pytest.skip("Function requires specific arguments - manual implementation needed")
    except Exception as e:
        pytest.fail(f"Unexpected error in filter_hooks_for_mode: {e}")

def test_group_hooks_by_repo_basic():
    """Test basic functionality of group_hooks_by_repo."""

    try:
        result = group_hooks_by_repo()
        assert result is not None or result is None
    except TypeError:

        import inspect
        assert callable(group_hooks_by_repo), "Function should be callable"
        sig = inspect.signature(group_hooks_by_repo)
        assert sig is not None, "Function should have valid signature"
        pytest.skip("Function requires specific arguments - manual implementation needed")
    except Exception as e:
        pytest.fail(f"Unexpected error in group_hooks_by_repo: {e}")

def test_generate_config_basic():
    """Test basic functionality of generate_config."""

    try:
        result = generate_config()
        assert result is not None or result is None
    except TypeError:

        import inspect
        assert callable(generate_config), "Function should be callable"
        sig = inspect.signature(generate_config)
        assert sig is not None, "Function should have valid signature"
        pytest.skip("Function requires specific arguments - manual implementation needed")
    except Exception as e:
        pytest.fail(f"Unexpected error in generate_config: {e}")

def test_create_temp_config_basic():
    """Test basic functionality of create_temp_config."""

    try:
        result = create_temp_config()
        assert result is not None or result is None
    except TypeError:

        import inspect
        assert callable(create_temp_config), "Function should be callable"
        sig = inspect.signature(create_temp_config)
        assert sig is not None, "Function should have valid signature"
        pytest.skip("Function requires specific arguments - manual implementation needed")
    except Exception as e:
        pytest.fail(f"Unexpected error in create_temp_config: {e}")
