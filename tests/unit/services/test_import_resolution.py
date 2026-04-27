from crackerjack.services.import_resolution import get_safe_import_spec


def test_get_safe_import_spec_known_values() -> None:
    assert get_safe_import_spec("suppress") == (
        "contextlib",
        "suppress",
        "from contextlib import suppress",
    )
    assert get_safe_import_spec("operator") == (
        "operator",
        None,
        "import operator",
    )


def test_get_safe_import_spec_unknown_value() -> None:
    assert get_safe_import_spec("missing_name") is None
