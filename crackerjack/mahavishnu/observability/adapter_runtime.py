from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AdapterSettingsVersion:
    adapter_id: str
    version: int
    settings_hash: str
    activated_at: datetime
    activated_by: str
    notes: str = ""
    deactivated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.settings_hash:
            raise ValueError(
                "settings_hash is required (join key for forensic queries)"
            )
        if self.version < 1:
            raise ValueError(
                f"version must be a positive integer; got {self.version!r}"
            )

    @property
    def is_active(self) -> bool:
        return self.deactivated_at is None


@dataclass(frozen=True)
class SettingsActivationRecord:
    adapter_id: str
    version: int
    settings_hash: str
    activated_by: str
    notes: str = ""


@runtime_checkable
class SettingsPersister(Protocol):
    def append(self, record: SettingsActivationRecord) -> AdapterSettingsVersion: ...

    def get_active(self, adapter_id: str) -> AdapterSettingsVersion | None: ...

    def get_history(self, adapter_id: str) -> list[AdapterSettingsVersion]: ...


class InMemorySettingsPersister:
    def __init__(self) -> None:

        self._history: dict[str, list[AdapterSettingsVersion]] = {}

    def append(self, record: SettingsActivationRecord) -> AdapterSettingsVersion:
        now = datetime.now(UTC)

        history = self._history.setdefault(record.adapter_id, [])
        for prev in reversed(history):
            if prev.is_active:
                object.__setattr__(prev, "deactivated_at", now)
                break

        new_row = AdapterSettingsVersion(
            adapter_id=record.adapter_id,
            version=record.version,
            settings_hash=record.settings_hash,
            activated_at=now,
            activated_by=record.activated_by,
            notes=record.notes,
            deactivated_at=None,
        )
        history.append(new_row)
        return new_row

    def get_active(self, adapter_id: str) -> AdapterSettingsVersion | None:
        history = self._history.get(adapter_id, [])
        for row in reversed(history):
            if row.is_active:
                return row
        return None

    def get_history(self, adapter_id: str) -> list[AdapterSettingsVersion]:
        return list(self._history.get(adapter_id, []))


class HttpSettingsPersister:
    # TODO(Workstream C): wire to the actual Dhara HTTP client once the

    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def append(self, record: SettingsActivationRecord) -> AdapterSettingsVersion:
        # TODO(Workstream C): POST {base_url}/adapters/{adapter_id}/settings-versions

        raise NotImplementedError(
            "HttpSettingsPersister is a stub — Workstream C is blocked on "
            "the Dhara HTTP surface. Use InMemorySettingsPersister in tests "
            "or wait for the endpoint to ship."
        )

    def get_active(self, adapter_id: str) -> AdapterSettingsVersion | None:
        # TODO(Workstream C): GET {base_url}/adapters/{adapter_id}/active-settings-version  # noqa: E501

        raise NotImplementedError("Workstream C: HTTP GET not yet wired.")

    def get_history(self, adapter_id: str) -> list[AdapterSettingsVersion]:
        # TODO(Workstream C): GET {base_url}/adapters/{adapter_id}/settings-versions
        raise NotImplementedError("Workstream C: HTTP GET history not yet wired.")


def activate(
    record: SettingsActivationRecord, persister: SettingsPersister
) -> AdapterSettingsVersion:
    return persister.append(record)


__all__ = [
    "AdapterSettingsVersion",
    "SettingsActivationRecord",
    "SettingsPersister",
    "InMemorySettingsPersister",
    "HttpSettingsPersister",
    "activate",
]
