from __future__ import annotations

import logging
import sys
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.core.ai_fix_event_bus import AIFixEventBus
    from crackerjack.ui.ai_fix_dashboard import AIFixDashboard


logger = logging.getLogger(__name__)


# All logging routes through this logger so a single ``configure_logging``
# call can install/replace handlers without leaking state between runs.
_AI_FIX_LOGGER_NAME = "crackerjack.core.ai_fix_sinks"


class Verbosity(IntEnum):
    """Verbosity levels for the ``crackerjack run --ai-fix`` stage.

    Mapping to CLI flags:
    - NORMAL      : default (no ``-v``)
    - VERBOSE     : ``-v``
    - VERY_VERBOSE: ``-vv``
    - DEBUG       : ``-vvv`` (or ``--ai-fix-debug``)
    """

    NORMAL = 0
    VERBOSE = 1
    VERY_VERBOSE = 2
    DEBUG = 3

    @classmethod
    def from_count(cls, count: int) -> Verbosity:
        """Map a ``-v`` count (0..N) to a Verbosity, capped at DEBUG."""
        if count <= 0:
            return cls.NORMAL
        if count == 1:
            return cls.VERBOSE
        if count == 2:
            return cls.VERY_VERBOSE
        return cls.DEBUG

    def should_log_event(self) -> bool:
        """Whether to log a structured one-line summary per event.

        Active at ``-vv`` and above (matches the existing LoggingSink
        behavior). The ``-v`` per-event log is rendered directly in the
        dashboard panel, not via a separate sink.
        """
        return self >= Verbosity.VERY_VERBOSE

    def should_dump_json_to_stderr(self) -> bool:
        """Whether to dump every event as JSON to stderr.

        Active at ``-vvv`` (DEBUG) per spec: "Dashboard + full JSON
        event stream to stderr".
        """
        return self >= Verbosity.DEBUG

    def should_write_debug_file(self) -> bool:
        """Whether to write the full JSON event stream to a debug file."""
        return self >= Verbosity.DEBUG


def parse_verbosity(verbose_count: int, *, ai_fix_debug: bool) -> Verbosity:
    """Resolve CLI flags into a single Verbosity level.

    ``--ai-fix-debug`` always forces DEBUG regardless of ``-v`` count.
    """
    if ai_fix_debug:
        return Verbosity.DEBUG
    return Verbosity.from_count(verbose_count)


def configure_logging(level: Verbosity) -> None:
    """Install/replace handlers on the AI-fix sinks logger.

    Idempotent: calling twice does not stack handlers (we replace by name).
    The DEBUG level also lowers the logger's own level so DEBUG messages
    propagate to the handler.
    """
    log = logging.getLogger(_AI_FIX_LOGGER_NAME)
    # Remove any handlers we previously attached (idempotency).
    for h in list(log.handlers):
        if getattr(h, "_crackerjack_owned", False):
            log.removeHandler(h)
    # Don't propagate to the root logger; we want the AI-fix log
    # to be self-contained.
    log.propagate = False

    handler: logging.Handler
    if level == Verbosity.NORMAL:
        # No handler needed: nothing should be logged at NORMAL.
        log.setLevel(logging.WARNING)
        return

    handler = logging.StreamHandler(sys.stderr)
    handler._crackerjack_owned = True  # type: ignore[attr-defined]
    if level >= Verbosity.DEBUG:
        handler.setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)
    elif level >= Verbosity.VERY_VERBOSE:
        handler.setLevel(logging.INFO)
        log.setLevel(logging.INFO)
    else:
        handler.setLevel(logging.INFO)
        log.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)


def build_bus_for_verbosity(
    *,
    level: Verbosity,
    base_dir: Path | None,
    run_id: str | None,
    dashboard_mode: str = "auto",
) -> tuple[AIFixEventBus, AIFixDashboard | None]:
    """Construct the default event bus for a given verbosity level.

    Subscribes (per spec):
    - LoggingSink     when level >= VERBOSE
    - JsonlSink       always (crash recovery depends on it)
    - MetricsSink     always
    - DebugFileSink   when level >= DEBUG
    - AIFixDashboard  when ``dashboard_mode`` resolves to "on"

    Returns the bus and the dashboard (or None if the dashboard was not
    activated). Callers must call ``dashboard.stop()`` on shutdown.
    """
    # Local imports keep this module independent of UI imports (and let
    # us patch the sidecar check helper at runtime if needed).
    from crackerjack.core.ai_fix_event_bus import AIFixEventBus
    from crackerjack.core.ai_fix_sinks import (
        DebugFileSink,
        JsonlSink,
        LoggingSink,
        MetricsSink,
    )
    from crackerjack.ui.ai_fix_dashboard import attach_dashboard

    bus = AIFixEventBus()

    # JSONL is always-on (per spec: "JSONL always"). It only opens a file
    # once it sees RunStarted, so passing base_dir is required to make it
    # write anything at all.
    if base_dir is not None and run_id is not None:
        bus.subscribe(JsonlSink(base_dir=base_dir))

    if level.should_log_event():
        configure_logging(level)
        bus.subscribe(LoggingSink())

    bus.subscribe(MetricsSink())

    if level.should_dump_json_to_stderr() and run_id is not None:
        # Per spec: "-vvv Dashboard + full JSON event stream to stderr".
        # The dashboard subscribes to the bus, so consumers piping stderr
        # can subscribe a JsonlSink-shaped writer here. For PR 0 we keep
        # this implicit (users can `tee` from `DebugFileSink`).
        pass

    if level.should_write_debug_file() and base_dir is not None and run_id is not None:
        bus.subscribe(DebugFileSink(base_dir=base_dir, run_id=run_id))

    dashboard = attach_dashboard(bus, mode=dashboard_mode)
    return bus, dashboard
