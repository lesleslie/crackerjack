from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = (
    Path(__file__).resolve().parents[4]
    / "crackerjack"
    / "services"
    / "quality"
    / "quality_baseline_enhanced.py"
)


def load_module(module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_quality_baseline_enhanced_exports_and_stub_behavior() -> None:
    module = load_module("tests.unit.services.quality.quality_baseline_enhanced_under_test")

    assert module.TrendDirection.IMPROVING == "improving"
    assert module.TrendDirection.STABLE == "stable"
    assert module.TrendDirection.DEGRADING == "degrading"

    assert module.AlertSeverity.INFO == "info"
    assert module.AlertSeverity.WARNING == "warning"
    assert module.AlertSeverity.CRITICAL == "critical"

    service = module.EnhancedQualityBaselineService()
    assert service.get_recent_baselines() == []
    assert service.get_recent_baselines(limit=3) == []
