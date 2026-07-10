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


_AI_FIX_LOGGER_NAME = "crackerjack.core.ai_fix_sinks"


class Verbosity(IntEnum):
    NORMAL = 0
    VERBOSE = 1
    VERY_VERBOSE = 2
    DEBUG = 3

    @classmethod
    def from_count(cls, count: int) -> Verbosity:
        if count <= 0:
            return cls.NORMAL
        if count == 1:
            return cls.VERBOSE
        if count == 2:
            return cls.VERY_VERBOSE
        return cls.DEBUG

    def should_log_event(self) -> bool:
        return self >= Verbosity.VERY_VERBOSE

    def should_dump_json_to_stderr(self) -> bool:
        return self >= Verbosity.DEBUG

    def should_write_debug_file(self) -> bool:
        return self >= Verbosity.DEBUG


def parse_verbosity(verbose_count: int, *, ai_fix_debug: bool) -> Verbosity:
    if ai_fix_debug:
        return Verbosity.DEBUG
    return Verbosity.from_count(verbose_count)


def configure_logging(level: Verbosity) -> None:
    log = logging.getLogger(_AI_FIX_LOGGER_NAME)

    for h in list(log.handlers):
        if getattr(h, "_crackerjack_owned", False):
            log.removeHandler(h)

    log.propagate = False

    handler: logging.Handler
    if level == Verbosity.NORMAL:
        log.setLevel(logging.WARNING)
        return

    handler = logging.StreamHandler(sys.stderr)
    handler._crackerjack_owned = True # type: ignore[attr-defined]
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

    from crackerjack.core.ai_fix_event_bus import AIFixEventBus
    from crackerjack.core.ai_fix_sinks import (
        DebugFileSink,
        JsonlSink,
        LoggingSink,
        MetricsSink,
    )
    from crackerjack.ui.ai_fix_dashboard import attach_dashboard

    bus = AIFixEventBus()

    if base_dir is not None and run_id is not None:
        bus.subscribe(JsonlSink(base_dir=base_dir))

    if level.should_log_event():
        configure_logging(level)
        bus.subscribe(LoggingSink())

    bus.subscribe(MetricsSink())

    if level.should_dump_json_to_stderr() and run_id is not None:
        pass

    if level.should_write_debug_file() and base_dir is not None and run_id is not None:
        bus.subscribe(DebugFileSink(base_dir=base_dir, run_id=run_id))

    dashboard = attach_dashboard(bus, mode=dashboard_mode)
    return bus, dashboard
