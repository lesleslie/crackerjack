import pytest


@pytest.mark.unit
class TestModelsConfigAdapter:
    def test_config_adapter_import(self) -> None:
        import crackerjack.models.config_adapter

        assert crackerjack.models.config_adapter is not None


@pytest.mark.unit
class TestPy313:
    def test_py313_import(self) -> None:
        import crackerjack.py313

        assert crackerjack.py313 is not None
