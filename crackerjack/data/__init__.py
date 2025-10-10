"""Data access layer utilities backed by ACB infrastructure."""

from __future__ import annotations

from crackerjack.data.models import QualityBaselineRecord
from crackerjack.data.repository import QualityBaselineRepository

__all__ = ["QualityBaselineRecord", "QualityBaselineRepository"]
