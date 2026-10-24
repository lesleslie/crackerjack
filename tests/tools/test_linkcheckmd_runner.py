"""Tests for the linkcheckmd runner module."""

from __future__ import annotations

import aiohttp
import pytest

from crackerjack.tools._linkcheckmd_runner import (
    MAX_FIELD_SIZE,
    _header_limit,
)


class TestHeaderLimit:
    """Tests for the _header_limit context manager."""

    async def test_raises_default_max_field_size(self) -> None:
        """Verify the default header ceiling is raised while active."""
        original_init = aiohttp.ClientSession.__init__

        with _header_limit():
            async with aiohttp.ClientSession() as session:
                assert session._max_field_size == MAX_FIELD_SIZE

        assert aiohttp.ClientSession.__init__ is original_init

    async def test_explicit_max_field_size_wins(self) -> None:
        """Verify an explicit caller-supplied ceiling is not overridden."""
        with _header_limit():
            async with aiohttp.ClientSession(max_field_size=1234) as session:
                assert session._max_field_size == 1234

    async def test_custom_limit_is_applied(self) -> None:
        """Verify a custom limit is honoured."""
        with _header_limit(limit=4096):
            async with aiohttp.ClientSession() as session:
                assert session._max_field_size == 4096

    async def test_restores_original_on_exit(self) -> None:
        """Verify the ceiling reverts to aiohttp's default after the block."""
        original_init = aiohttp.ClientSession.__init__

        with _header_limit():
            pass

        assert aiohttp.ClientSession.__init__ is original_init
        async with aiohttp.ClientSession() as session:
            assert session._max_field_size == 8190

    async def test_restores_original_on_exception(self) -> None:
        """Verify the ceiling is restored even when the block raises."""
        original_init = aiohttp.ClientSession.__init__

        with pytest.raises(RuntimeError, match="boom"), _header_limit():
            raise RuntimeError("boom")

        assert aiohttp.ClientSession.__init__ is original_init
