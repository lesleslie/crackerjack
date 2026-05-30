from __future__ import annotations

import importlib.util
import sys
import typing
from pathlib import Path
from uuid import uuid4


def _load_module(module_name: str, relative_path: str):
    path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_execution_result_defaults_and_metadata() -> None:
    results = _load_module("tests.unit.model_results", "crackerjack/models/results.py")

    execution = results.ExecutionResult(
        operation_id="op-1",
        success=True,
        duration_seconds=1.25,
    )

    assert execution.output == ""
    assert execution.error == ""
    assert execution.exit_code == 0
    assert execution.metadata == {}


def test_parallel_execution_result_properties() -> None:
    results = _load_module("tests.unit.model_results", "crackerjack/models/results.py")

    execution = results.ExecutionResult(
        operation_id="op-1",
        success=True,
        duration_seconds=1.25,
    )
    parallel = results.ParallelExecutionResult(
        group_name="group",
        total_operations=4,
        successful_operations=3,
        failed_operations=1,
        total_duration_seconds=5.0,
        results=[execution],
    )

    assert parallel.success_rate == 0.75
    assert parallel.overall_success is False

    empty = results.ParallelExecutionResult(
        group_name="empty",
        total_operations=0,
        successful_operations=0,
        failed_operations=0,
        total_duration_seconds=0.0,
        results=[],
    )
    assert empty.success_rate == 0.0
    assert empty.overall_success is True


def test_adapter_metadata_dict_and_string() -> None:
    metadata = _load_module(
        "tests.unit.adapter_metadata",
        "crackerjack/models/adapter_metadata.py",
    )

    adapter = metadata.AdapterMetadata(
        module_id=uuid4(),
        name="ruff",
        category="lint",
        version="1.2.3",
        status=metadata.AdapterStatus.STABLE,
        description="Static analysis",
    )

    adapter_dict = adapter.dict()
    assert adapter_dict == adapter.to_dict()
    assert adapter_dict["name"] == "ruff"
    assert adapter_dict["category"] == "lint"
    assert adapter_dict["version"] == "1.2.3"
    assert adapter_dict["status"] == "stable"
    assert adapter_dict["description"] == "Static analysis"
    assert str(adapter) == "ruff v1.2.3 (stable)"


def test_adapter_metadata_type_checking_import_branch(monkeypatch) -> None:
    monkeypatch.setattr(typing, "TYPE_CHECKING", True)

    metadata = _load_module(
        "tests.unit.adapter_metadata_type_checking",
        "crackerjack/models/adapter_metadata.py",
    )

    assert metadata.AdapterStatus.BETA.value == "beta"
