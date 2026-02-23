from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TransformResult:
    success: bool
    transformed_code: str | None = None
    error_message: str | None = None
    pattern_name: str | None = None


class BaseSurgeon(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def apply(
        self,
        code: str,
        match_info: dict,
        file_path: Path | None = None,
    ) -> TransformResult: ...

    def can_handle(self, match_info: dict) -> bool:
        return True
