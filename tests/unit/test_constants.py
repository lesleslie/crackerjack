from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_constants_exports_expected_values() -> None:
    constants = _load_module(
        "tests.unit.cli_constants",
        "crackerjack/cli/constants.py",
    )

    assert constants.PROJECT_NAME == "crackerjack"
    assert constants.VARIABLE_PREFIX == "CRACKERJACK"
    assert constants.DEFAULT_TEST_TIMEOUT == 600
    assert constants.DEFAULT_LSP_PORT == 8685
    assert constants.DEFAULT_XCODE_SCHEME == "MdInjectApp"


def test_service_constants_exports_expected_values() -> None:
    constants = _load_module(
        "tests.unit.service_constants",
        "crackerjack/services/constants.py",
    )

    assert constants.DEFAULT_API_TIMEOUT == 10.0
    assert constants.MAX_RETRY_ATTEMPTS == 3
    assert constants.DEFAULT_DB_TIMEOUT == 30.0
    assert constants.LARGE_QUEUE_SIZE == 10_000
    assert constants.DEFAULT_BUFFER_SIZE == 8192
