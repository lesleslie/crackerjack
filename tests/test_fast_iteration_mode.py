"""Tests for Phase 10.2.4: Fast Iteration Mode CLI flags."""

import pytest
from crackerjack.cli.options import Options


class TestFastIterationFlag:
    """Test --fast-iteration flag functionality."""

    def test_fast_iteration_default_false(self):
        """Test that fast_iteration defaults to False."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
        )

        assert options.fast_iteration is False

    def test_fast_iteration_can_be_enabled(self):
        """Test that fast_iteration can be set to True."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            fast_iteration=True,
        )

        assert options.fast_iteration is True

    def test_fast_iteration_in_options_dataclass(self):
        """Test that fast_iteration field exists in Options dataclass."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            fast_iteration=True,
        )

        assert hasattr(options, "fast_iteration")
        assert options.fast_iteration is True


class TestToolFlag:
    """Test --tool flag functionality."""

    def test_tool_default_none(self):
        """Test that tool defaults to None."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
        )

        assert options.tool is None

    def test_tool_can_be_set(self):
        """Test that tool can be set to a specific value."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            tool="ruff-check",
        )

        assert options.tool == "ruff-check"

    def test_tool_in_options_dataclass(self):
        """Test that tool field exists in Options dataclass."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            tool="zuban",
        )

        assert hasattr(options, "tool")
        assert options.tool == "zuban"


class TestChangedOnlyFlag:
    """Test --changed-only flag functionality."""

    def test_changed_only_default_false(self):
        """Test that changed_only defaults to False."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
        )

        assert options.changed_only is False

    def test_changed_only_can_be_enabled(self):
        """Test that changed_only can be set to True."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            changed_only=True,
        )

        assert options.changed_only is True

    def test_changed_only_in_options_dataclass(self):
        """Test that changed_only field exists in Options dataclass."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            changed_only=True,
        )

        assert hasattr(options, "changed_only")
        assert options.changed_only is True


class TestFlagCombinations:
    """Test combinations of fast iteration flags."""

    def test_fast_iteration_with_tool(self):
        """Test fast_iteration combined with tool."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            fast_iteration=True,
            tool="zuban",
            changed_only=False,
        )

        assert options.fast_iteration is True
        assert options.tool == "zuban"

    def test_fast_iteration_with_changed_only(self):
        """Test fast_iteration combined with changed_only."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            fast_iteration=True,
            tool=None,
            changed_only=True,
        )

        assert options.fast_iteration is True
        assert options.changed_only is True

    def test_all_three_flags_together(self):
        """Test all three flags can be used together."""
        options = Options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            clean=False,
            test=False,
            benchmark=False,
            fast_iteration=True,
            tool="ruff-check",
            changed_only=True,
        )

        assert options.fast_iteration is True
        assert options.tool == "ruff-check"
        assert options.changed_only is True


class TestOptionsProtocolIntegration:
    """Test that new fields are in OptionsProtocol."""

    def test_options_protocol_has_fast_iteration(self):
        """Test OptionsProtocol includes fast_iteration."""
        from crackerjack.models.protocols import OptionsProtocol
        import typing as t

        # Check that the protocol has the attribute
        assert hasattr(OptionsProtocol, "__annotations__")
        assert "fast_iteration" in OptionsProtocol.__annotations__

    def test_options_protocol_has_tool(self):
        """Test OptionsProtocol includes tool."""
        from crackerjack.models.protocols import OptionsProtocol

        assert hasattr(OptionsProtocol, "__annotations__")
        assert "tool" in OptionsProtocol.__annotations__

    def test_options_protocol_has_changed_only(self):
        """Test OptionsProtocol includes changed_only."""
        from crackerjack.models.protocols import OptionsProtocol

        assert hasattr(OptionsProtocol, "__annotations__")
        assert "changed_only" in OptionsProtocol.__annotations__
