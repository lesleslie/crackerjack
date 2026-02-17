import pytest

from crackerjack.tools import validate_input_validator_patterns as validator


def test_main_reports_success(capsys: pytest.CaptureFixture[str]) -> None:
    code = validator.main()
    out = capsys.readouterr().out

    assert code == 0
    assert "ALL SECURITY VALIDATION TESTS PASSED" in out
