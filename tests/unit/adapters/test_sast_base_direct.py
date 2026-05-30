from __future__ import annotations

import importlib.util
import sys
import typing
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parents[3] / "crackerjack" / "adapters" / "sast" / "_base.py"


def install_stub_package(monkeypatch, module_name: str) -> None:
    module = ModuleType(module_name)
    module.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)


def install_stub_module(monkeypatch, module_name: str, **attributes: object) -> None:
    module = ModuleType(module_name)
    for name, value in attributes.items():
        setattr(module, name, value)
    monkeypatch.setitem(sys.modules, module_name, module)


def load_module(module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_sast_base_import_exposes_protocol_alias_and_type_only_imports(monkeypatch) -> None:
    monkeypatch.setattr(typing, "TYPE_CHECKING", True)
    install_stub_package(monkeypatch, "crackerjack")
    install_stub_package(monkeypatch, "crackerjack.adapters")
    install_stub_package(monkeypatch, "crackerjack.models")
    install_stub_module(
        monkeypatch,
        "crackerjack.adapters._tool_adapter_base",
        ToolAdapterSettings=type("ToolAdapterSettings", (), {}),
        ToolExecutionResult=type("ToolExecutionResult", (), {}),
        ToolIssue=type("ToolIssue", (), {}),
    )
    install_stub_module(
        monkeypatch,
        "crackerjack.models.qa_config",
        QACheckConfig=type("QACheckConfig", (), {}),
    )
    install_stub_module(
        monkeypatch,
        "crackerjack.models.qa_results",
        QACheckType=type("QACheckType", (), {}),
    )

    module = load_module("tests.unit.adapters.sast_base_under_test")

    assert module.SASTAdapter is module.SASTAdapterProtocol
    assert module.SASTAdapterProtocol.__name__ == "SASTAdapterProtocol"
    assert module.ToolIssue is not None
    assert module.ToolExecutionResult is not None
    assert module.ToolAdapterSettings is not None
    assert module.QACheckConfig is not None
    assert module.QACheckType is not None


def test_sast_base_import_skips_type_only_imports_when_type_checking_false() -> None:
    module = load_module("tests.unit.adapters.sast_base_runtime_only")

    assert module.SASTAdapter is module.SASTAdapterProtocol
    assert module.SASTAdapterProtocol.__name__ == "SASTAdapterProtocol"
    assert not hasattr(module, "ToolIssue")
    assert not hasattr(module, "ToolExecutionResult")
    assert not hasattr(module, "ToolAdapterSettings")
