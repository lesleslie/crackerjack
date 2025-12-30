from __future__ import annotations

from datetime import datetime

import pytest

from crackerjack.documentation.dual_output_generator import (
    DocumentationResult,
    DualOutputGenerator,
)
from rich.console import Console


def test_to_dict_basic():
    result = DocumentationResult(
        ai_reference="ai",
        agent_capabilities={"agents": {"demo": {}}},
        error_patterns={"type_errors": {"E001": {}}},
        readme_enhancements="readme",
        generation_timestamp=datetime(2024, 1, 1),
    )

    payload = result.to_dict()
    assert payload["success"] is True
    assert payload["outputs"]["ai_reference_length"] == 2
    assert payload["outputs"]["agent_count"] == 1
    assert payload["outputs"]["error_pattern_count"] == 1
    assert payload["outputs"]["readme_length"] == 6


@pytest.mark.asyncio
async def test_generate_documentation_short_circuit(tmp_path):
    generator = DualOutputGenerator(project_path=tmp_path, console=Console())
    cached_result = DocumentationResult(
        ai_reference="cached",
        agent_capabilities={},
        error_patterns={},
        readme_enhancements="",
    )
    generator.last_generation = cached_result
    generator._needs_regeneration = lambda: False

    result = await generator.generate_documentation(update_existing=False)
    assert result is cached_result
