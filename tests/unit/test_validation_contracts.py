from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from crackerjack.models.validation_contracts import (
    GateSeverity,
    QualityGateCheck,
    QualityGateReport,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)


class TestValidationContracts:
    def test_validation_report_from_result(self) -> None:
        result = SimpleNamespace(
            success=False,
            validation_type='ruff',
            summary='Validation failed',
            issues=[
                SimpleNamespace(
                    severity='warning',
                    message='line too long',
                    file_path=Path('app.py'),
                    line_number=17,
                    code='E501',
                    category='style',
                ),
                'fallback issue',
            ],
            metadata={'tool': 'ruff'},
        )

        report = ValidationReport.from_result(result)

        assert report.valid is False
        assert report.validation_type == 'ruff'
        assert report.summary == 'Validation failed'
        assert report.warning_count == 1
        assert report.error_count == 1
        assert report.issues[0].severity == ValidationSeverity.WARNING
        assert report.issues[0].file_path == 'app.py'
        assert report.issues[1].message == 'fallback issue'
        assert report.metadata == {'tool': 'ruff'}

    def test_validation_issue_to_dict(self) -> None:
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message='bad value',
            file_path='settings.yaml',
            line_number=3,
            code='CFG001',
        )

        data = issue.to_dict()

        assert data['severity'] == 'error'
        assert data['message'] == 'bad value'
        assert data['file_path'] == 'settings.yaml'
        assert data['line_number'] == 3
        assert data['code'] == 'CFG001'

    def test_quality_gate_report_from_result(self) -> None:
        result = SimpleNamespace(
            fast_hooks=True,
            tests=False,
            comprehensive=False,
            coverage=72.5,
            errors=['tests failed'],
            repository='crackerjack',
            profile='standard',
        )

        report = QualityGateReport.from_result(result)

        assert report.fast_hooks is True
        assert report.tests is False
        assert report.comprehensive is False
        assert report.passed is False
        assert report.blocking_failure is True
        assert report.coverage == 72.5
        assert report.errors == ['tests failed']
        assert report.repository == 'crackerjack'
        assert report.profile == 'standard'
        assert len(report.checks) == 3
        assert report.checks[0].severity == GateSeverity.REQUIRED

    def test_quality_gate_report_to_dict(self) -> None:
        report = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=False,
            coverage=95.0,
            errors=[],
            checks=[
                QualityGateCheck(
                    name='lint',
                    passed=True,
                    severity=GateSeverity.REQUIRED,
                    score=100.0,
                )
            ],
            repository='crackerjack',
            profile='quick',
        )

        data = report.to_dict()

        assert data['fast_hooks'] is True
        assert data['tests'] is True
        assert data['comprehensive'] is False
        assert data['coverage'] == 95.0
        assert data['passed'] is False
        assert data['blocking_failure'] is False
        assert data['checks'][0]['name'] == 'lint'
        assert data['repository'] == 'crackerjack'
        assert data['profile'] == 'quick'
