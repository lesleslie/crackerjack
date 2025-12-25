from __future__ import annotations

from crackerjack.core.container import DependencyContainer, create_container
from crackerjack.models.protocols import FileSystemInterface


class DummyInterface:
    pass


class DummyService:
    pass


def test_create_container_basic():
    container = create_container()
    assert isinstance(container, DependencyContainer)


def test_register_singleton_basic():
    container = DependencyContainer()
    instance = DummyService()
    container.register_singleton(DummyInterface, instance)
    assert container.get(DummyInterface) is instance


def test_register_transient_basic():
    container = DependencyContainer()
    container.register_transient(DummyInterface, DummyService)
    first = container.get(DummyInterface)
    second = container.get(DummyInterface)
    assert isinstance(first, DummyService)
    assert isinstance(second, DummyService)
    assert first is not second


def test_get_raises_for_missing_service():
    container = DependencyContainer()
    try:
        container.get(DummyInterface)
    except ValueError as exc:
        assert "Service DummyInterface not registered" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing service")


def test_create_default_container_basic(tmp_path):
    container = DependencyContainer().create_default_container(pkg_path=tmp_path)
    filesystem = container.get(FileSystemInterface)
    assert filesystem is not None
