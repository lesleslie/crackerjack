from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_import_resolution_module() -> types.ModuleType:
    module_path = (
        Path(__file__).resolve().parents[3]
        / "crackerjack"
        / "services"
        / "import_resolution.py"
    )
    spec = importlib.util.spec_from_file_location(
        "tests.unit.services.import_resolution_direct",
        module_path,
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tests.unit.services.import_resolution_direct"] = module
    spec.loader.exec_module(module)
    return module


def test_get_safe_import_spec_returns_known_spec() -> None:
    module = _load_import_resolution_module()

    spec = module.get_safe_import_spec("Path")

    assert spec is not None
    assert spec.module_name == "pathlib"
    assert spec.symbol_name == "Path"
    assert spec.import_line == "from pathlib import Path"


def test_get_safe_import_spec_returns_none_for_unknown_name() -> None:
    module = _load_import_resolution_module()

    assert module.get_safe_import_spec("missing_name") is None
