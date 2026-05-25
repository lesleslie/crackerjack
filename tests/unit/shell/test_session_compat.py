"""Tests for session_compat module - SessionEventEmitter fallback implementation."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


class TestFallbackSessionEventEmitter:
    """Test suite for _FallbackSessionEventEmitter class."""

    def test_init_basic(self):
        """Test initialization of fallback emitter."""
        from crackerjack.shell.session_compat import _FallbackSessionEventEmitter

        emitter = _FallbackSessionEventEmitter(component_name="test_component")

        assert emitter.component_name == "test_component"
        assert emitter.available is False

    @pytest.mark.asyncio
    async def test_emit_session_start_returns_none(self):
        """Test emit_session_start returns None in fallback mode."""
        from crackerjack.shell.session_compat import _FallbackSessionEventEmitter

        emitter = _FallbackSessionEventEmitter(component_name="test")

        result = await emitter.emit_session_start(
            shell_type="TestShell", metadata={"key": "value"}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_emit_session_end_does_not_raise(self):
        """Test emit_session_end does not raise in fallback mode."""
        from crackerjack.shell.session_compat import _FallbackSessionEventEmitter

        emitter = _FallbackSessionEventEmitter(component_name="test")

        # Should not raise
        await emitter.emit_session_end(session_id="test_session", metadata={})

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self):
        """Test close does not raise in fallback mode."""
        from crackerjack.shell.session_compat import _FallbackSessionEventEmitter

        emitter = _FallbackSessionEventEmitter(component_name="test")

        # Should not raise
        await emitter.close()

    def test_available_property(self):
        """Test available property returns False."""
        from crackerjack.shell.session_compat import _FallbackSessionEventEmitter

        emitter = _FallbackSessionEventEmitter(component_name="test")

        assert emitter.available is False

    def test_component_name_assignment(self):
        """Test component_name is assigned correctly."""
        from crackerjack.shell.session_compat import _FallbackSessionEventEmitter

        names = ["crackerjack", "test-component", "a", "long_component_name_here"]
        for name in names:
            emitter = _FallbackSessionEventEmitter(component_name=name)
            assert emitter.component_name == name


class TestSessionEventEmitterImport:
    """Test suite for SessionEventEmitter import behavior."""

    def test_session_event_emitter_import(self):
        """Test SessionEventEmitter can be imported."""
        # Just verify we can import it without error
        from crackerjack.shell.session_compat import SessionEventEmitter

        assert SessionEventEmitter is not None

    def test_session_event_emitter_available_is_bool(self):
        """Test SessionEventEmitter has an available property."""
        from crackerjack.shell.session_compat import SessionEventEmitter

        emitter = SessionEventEmitter(component_name="test")
        assert isinstance(emitter.available, bool)