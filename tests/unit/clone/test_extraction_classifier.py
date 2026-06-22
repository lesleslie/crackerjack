from __future__ import annotations

import textwrap

import pytest

from crackerjack.clone.classifier import ExtractionProposal, ExtractionTargetClassifier


@pytest.mark.unit
class TestExtractionTargetClassifier:
    def test_classifier_routes_stdlib_only_to_oneiric(self) -> None:
        """Code with only stdlib imports → extraction target = oneiric."""
        code = textwrap.dedent("""\
            import os
            import sys
            from pathlib import Path

            def get_config_path() -> Path:
                return Path(os.environ.get("CONFIG_PATH", "."))
        """)
        classifier = ExtractionTargetClassifier()
        proposal = classifier.classify(code, pattern_description="config path helper")
        assert proposal.target_repo == "oneiric"

    def test_classifier_routes_domain_imports_to_new_package(self) -> None:
        """Code with domain (non-stdlib, non-oneiric) imports → new shared package."""
        code = textwrap.dedent("""\
            import httpx
            from pydantic import BaseModel

            def fetch_data(url: str) -> dict:
                return httpx.get(url).json()
        """)
        classifier = ExtractionTargetClassifier()
        proposal = classifier.classify(code, pattern_description="HTTP data fetcher")
        assert proposal.target_repo == "new_package"

    def test_classifier_oneiric_import_routes_to_oneiric(self) -> None:
        """Code using oneiric itself → still routes to oneiric (it's foundational)."""
        code = textwrap.dedent("""\
            from oneiric.core.logging import get_logger

            logger = get_logger(__name__)

            def log_event(event: str) -> None:
                logger.info("Event: %s", event)
        """)
        classifier = ExtractionTargetClassifier()
        proposal = classifier.classify(code, pattern_description="logging helper")
        assert proposal.target_repo == "oneiric"

    def test_classifier_returns_proposed_name_from_pattern(self) -> None:
        """classifier.classify returns a non-empty proposed_name based on pattern_description."""
        code = textwrap.dedent("""\
            import os

            def resolve_env_path(key: str) -> str:
                return os.environ.get(key, "")
        """)
        classifier = ExtractionTargetClassifier()
        proposal = classifier.classify(code, pattern_description="env path resolver")
        assert proposal.proposed_name, "proposed_name must be non-empty"
        assert isinstance(proposal.proposed_name, str)

    def test_classifier_returns_extraction_proposal_dataclass(self) -> None:
        code = "import os\ndef f(): pass"
        classifier = ExtractionTargetClassifier()
        proposal = classifier.classify(code, pattern_description="test")
        assert isinstance(proposal, ExtractionProposal)
        assert proposal.rationale

    def test_classifier_local_for_non_extractable_domain_code(self) -> None:
        """Code importing crackerjack itself → local (same-repo, can't extract)."""
        code = textwrap.dedent("""\
            from crackerjack.models.qa_results import QACheckType

            def check_type() -> QACheckType:
                return QACheckType.SAST
        """)
        classifier = ExtractionTargetClassifier()
        proposal = classifier.classify(code, pattern_description="qa check type helper")
        assert proposal.target_repo == "local"
