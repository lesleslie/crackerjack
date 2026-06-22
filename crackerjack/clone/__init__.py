from __future__ import annotations

from crackerjack.clone.classifier import ExtractionProposal, ExtractionTargetClassifier
from crackerjack.clone.grouper import CloneGroup, CloneGrouper, CloneLocation, CloneType
from crackerjack.clone.refactor_engine import CloneDecision, CloneRefactorEngine, RefactorProposal

__all__ = [
    "CloneDecision",
    "CloneGroup",
    "CloneGrouper",
    "CloneLocation",
    "CloneType",
    "ExtractionProposal",
    "ExtractionTargetClassifier",
    "RefactorProposal",
    "CloneRefactorEngine",
]
