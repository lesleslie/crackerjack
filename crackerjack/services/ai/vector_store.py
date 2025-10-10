"""AI domain re-export for the vector store service.

This module exposes the semantic vector store implementation through the
``crackerjack.services.ai`` namespace so CLI entrypoints and future AI agents
can depend on the domain package instead of legacy module paths.
"""

from __future__ import annotations

from ..vector_store import *  # noqa: F401,F403
