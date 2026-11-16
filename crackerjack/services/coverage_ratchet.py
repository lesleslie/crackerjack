from __future__ import annotations

import json
import math
import re
import typing as t
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from crackerjack.models.protocols import CoverageRatchetProtocol
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.regex_patterns import update_coverage_requirement


def _update_fail_under_mirror(content: str, coverage: float) -> str:
    """Update the ``[tool.coverage.report].fail_under`` mirror site.

    pytest-cov enforces the floor through ``--cov-fail-under`` in
    ``addopts``; coverage.py enforces it through ``fail_under`` in the
    ``[tool.coverage.report]`` block. Both are present in most repos,
    so both have to carry the same number — otherwise the two
    entry-points enforce different floors and the repo's real
    requirement is whichever one nobody looked at.
    """
    coverage_pattern = r"(fail_under\s*=\s*)\d+(?:\.\d+)?"
    if not re.search(coverage_pattern, content):
        return content
    return re.sub(coverage_pattern, rf"\g<1>{coverage}", content, count=1)


def _achieved_milestone_values(raw: t.Any) -> set[float]:
    """The milestone values recorded in ``milestones_achieved``.

    Two shapes are in the wild, and both name the same thing:

    - a list of milestone numbers — what ``update_coverage`` writes;
    - a list of dicts carrying a ``milestone`` key — what a
      hand-written ratchet holds.

    Reading only the first shape made the refresh path raise
    ``TypeError: cannot use 'dict' as a set element`` on a
    hand-written ratchet, which turned a coverage IMPROVEMENT into a
    crash — the one case where the ratchet was supposed to rewrite
    itself. Both shapes are read here, and an entry that names no
    milestone contributes nothing rather than raising.
    """
    if not isinstance(raw, list):
        return set()
    values: set[float] = set()
    for entry in raw:
        candidate = entry.get("milestone") if isinstance(entry, dict) else entry
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, (int, float)):
            values.add(float(candidate))
    return values


def _normalize_milestones_achieved(raw: t.Any) -> list[float]:
    """``milestones_achieved`` in the canonical shape: a list of numbers.

    Written back on every ratchet write so a hand-written ratchet
    converges to the shape the rest of the service reads, and so the
    "already achieved" check cannot append a duplicate milestone on
    every refresh.
    """
    return sorted(_achieved_milestone_values(raw))


def enforced_floor(measured_coverage: float) -> float:
    """The coverage floor a measurement justifies.

    The floor is the whole percentage point BELOW the measurement, not
    the measurement itself. Pinning the floor to the raw measured float
    makes it a tripwire: the number is re-measured on every run, and
    any change to the code at all — a new uncovered line, a branch
    that stops being taken — moves the measurement below the floor and
    fails the suite over a fraction of a percent that no reader can
    act on. A floor a whole point below the measurement still refuses
    a real regression (the coverage cannot drop a full point without
    the gate noticing) while leaving room for ordinary churn.

    The CLAUDE.md claim is the other side of the same coin: it rounds
    UP to the whole percentage above the measurement, because the
    release audit compares the claim against the floor and the
    measured value.

    Never returns a floor above the measurement: a floor the current
    code cannot meet fails the suite on the run that set it.
    """
    return float(math.floor(measured_coverage))


class CoverageRatchetService(CoverageRatchetProtocol):
    MILESTONES = [15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 95, 100]

    TOLERANCE_MARGIN = 2.0

    def __init__(
        self,
        pkg_path: Path,
        console: Console | None = None,
    ) -> None:
        try:
            self.pkg_path = Path(pkg_path)
        except Exception:
            self.pkg_path = Path(pkg_path)
        self.console = console or Console()
        self.ratchet_file = self.pkg_path / ".coverage-ratchet.json"
        self.pyproject_file = self.pkg_path / "pyproject.toml"

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def initialize_baseline(self, initial_coverage: float, force: bool = False) -> None:
        """Write a fresh ratchet at ``initial_coverage``.

        ``force`` overwrites an existing ratchet. Without it this is a
        no-op when the file is already there — which is what made
        ``crackerjack coverage-ratchet init --reinit`` print "Ratchet
        initialized" while leaving the file byte-identical: the
        command's own "already exists" guard was the only thing
        ``--reinit`` bypassed, and the write underneath it
        early-returned. It then mirrored the coverage number into
        pyproject.toml, so the enforced floor and the ratchet
        disagreed.
        """
        if self.ratchet_file.exists() and not force:
            return

        floor = enforced_floor(initial_coverage)
        ratchet_data: dict[str, t.Any] = {
            "baseline": floor,
            "current_minimum": floor,
            "target": 100.0,
            "last_updated": datetime.now(UTC).isoformat(),
            "history": [
                {
                    "date": datetime.now(UTC).isoformat(),
                    "coverage": floor,
                    "commit": "baseline",
                    "milestone": False,
                },
            ],
            "milestones_achieved": [],
            "next_milestone": self._get_next_milestone(floor),
        } | self._ratchet_metadata()

        self.ratchet_file.write_text(json.dumps(ratchet_data, indent=2))
        self.console.print(
            f"[cyan]📊[/cyan] Coverage ratchet initialized at {floor:.0f}% baseline",
        )

    def normalize_floor(self) -> float | None:
        """Round a legacy raw-float floor down to the policy floor.

        Ratchets written before the rounding policy pinned the floor to
        the raw measured float (``90.9895227008149``), which is a
        tripwire: the measurement moves on any code change, and the
        suite fails over a fraction of a percent. This rounds such a
        floor down to the whole point below it and mirrors the change
        into pyproject.

        Returns the new floor, or ``None`` when there was nothing to
        normalize (no ratchet, an already-integral floor, or a floor
        that is already the policy floor).

        Deliberately NOT part of ``update_coverage``: that path may
        only ever RAISE the floor, so a coverage regression can never
        quietly lower it. The round-down is a one-time migration an
        operator asks for explicitly.
        """
        data = self.get_ratchet_data()
        if not data:
            return None

        stored = data.get("current_minimum")
        if not isinstance(stored, (int, float)) or isinstance(stored, bool):
            return None
        stored = float(stored)
        if stored.is_integer():
            return None

        floor = enforced_floor(stored)
        data["baseline"] = floor
        data["current_minimum"] = floor
        data["next_milestone"] = self._get_next_milestone(floor)
        data["last_updated"] = datetime.now(UTC).isoformat()
        data.update(self._ratchet_metadata())
        self.ratchet_file.write_text(json.dumps(data, indent=2))
        self._update_pyproject_requirement(floor)
        return floor

    def _ratchet_metadata(self) -> dict[str, t.Any]:
        """Build the staleness metadata block for a ratchet write.

        Every ratchet write gets a ``generated_at`` ISO-8601 timestamp and,
        when a ``coverage.json`` exists at the project root, the absolute
        path and mtime of the file the ratchet was derived from. Readers
        use these to detect two distinct failure modes:

        - **time-stale**: ``generated_at`` is older than
          ``DEFAULT_RATCHET_MAX_AGE_DAYS`` days. The ratchet is from a
          long-ago run; the code may have shifted.
        - **data-stale**: ``coverage_data_mtime`` does not equal the
          current ``coverage.json`` mtime. The ratchet was rewritten
          without a corresponding test run, or the test run was deleted.

        Both conditions must hold for a ratchet to be trustworthy. The
        ratchet itself does not enforce this — readers do. See
        ``.claude/decisions/2026-10-13-ratchet-staleness.md``.

        ``generated_at`` is written as a timezone-aware UTC timestamp.
        The reader parses it with ``datetime.fromisoformat`` and
        normalizes a naive value to UTC, but a naive *local* timestamp
        is not UTC: on a machine west of Greenwich it reads as hours
        in the past, which shortens the staleness window by exactly
        that offset. Aware UTC is unambiguous wherever the file is
        written or read.
        """
        metadata: dict[str, t.Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
        }
        coverage_file = self.pkg_path / "coverage.json"
        if coverage_file.exists():
            with suppress(OSError):
                # coverage.json may disappear between exists() and stat()
                # — treat as no-data and let the ratchet carry only
                # the timestamp.
                metadata["coverage_data_path"] = str(coverage_file.resolve())
                metadata["coverage_data_mtime"] = coverage_file.stat().st_mtime
        return metadata

    def _refresh_freshness(self) -> bool:
        """Refresh the staleness metadata after a fresh measurement.

        The floor did not move, but a measurement was taken, and the
        reader in ``crackerjack.checks.release_audit`` judges the
        ratchet on that measurement rather than on the floor:

        - ``generated_at`` older than the staleness window reads as
          time-stale;
        - a recorded ``coverage_data_mtime`` that no longer matches the
          on-disk ``coverage.json`` reads as data-stale.

        Every test run rewrites ``coverage.json``, so a ratchet that is
        only written when the baseline *improves* goes data-stale the
        next time the suite runs — and time-stale 30 days later — even
        when nothing about the code changed. Both failure modes surface
        as "ratchet file could not be read", which is misleading: the
        file is present and perfectly readable.

        The write is skipped when ``coverage.json`` has not been
        re-measured since the last write, so a run that does not touch
        the test suite leaves the file alone.

        Returns True when the file was rewritten.
        """
        data = self.get_ratchet_data()
        if not data:
            return False

        coverage_file = self.pkg_path / "coverage.json"
        if not coverage_file.exists():
            return False
        try:
            current_mtime = coverage_file.stat().st_mtime
        except OSError:
            return False

        recorded_mtime = data.get("coverage_data_mtime")
        if isinstance(recorded_mtime, (int, float)) and recorded_mtime == current_mtime:
            return False  # no new measurement since the last write

        data["last_updated"] = datetime.now(UTC).isoformat()
        data.update(self._ratchet_metadata())
        self.ratchet_file.write_text(json.dumps(data, indent=2))
        return True

    def get_ratchet_data(self) -> dict[str, t.Any]:
        if not self.ratchet_file.exists():
            return {}
        return t.cast("dict[str, t.Any]", json.loads(self.ratchet_file.read_text()))

    def get_status_report(self) -> dict[str, t.Any]:
        return self.get_ratchet_data()

    def get_baseline(self) -> float:
        data = self.get_ratchet_data()
        baseline = data.get("baseline")
        return float(baseline) if baseline is not None else 0.0

    def get_baseline_coverage(self) -> float:
        return self.get_baseline()

    def update_baseline_coverage(self, new_coverage: float) -> bool:
        result: bool = self.update_coverage(new_coverage).get("success", False)
        return result

    def is_coverage_regression(self, current_coverage: float) -> bool:
        baseline = self.get_baseline()
        return current_coverage < (baseline - self.TOLERANCE_MARGIN)

    def calculate_coverage_gap(self) -> float:
        data = self.get_ratchet_data()
        baseline = data.get("baseline")
        baseline = float(baseline) if baseline is not None else 0.0
        next_milestone = data.get("next_milestone")
        next_milestone = float(next_milestone) if next_milestone is not None else None
        if next_milestone:
            return next_milestone - baseline
        return 100.0 - baseline

    def update_coverage(self, new_coverage: float) -> dict[str, t.Any]:
        if not self.ratchet_file.exists():
            self.initialize_baseline(new_coverage)
            return {
                "status": "initialized",
                "message": f"Coverage ratchet initialized at {new_coverage:.0f}%",
                "milestones": [],
                "progress_to_100": f"{new_coverage:.0f}% of the way to 100 % coverage",
                "allowed": True,
                "baseline_updated": True,
            }

        data = self.get_ratchet_data()
        current_baseline = float(data["baseline"])
        new_floor = enforced_floor(new_coverage)

        tolerance_threshold = current_baseline - self.TOLERANCE_MARGIN
        if new_coverage < tolerance_threshold:
            self._refresh_freshness()
            return {
                "status": "regression",
                "message": f"Coverage decreased from {current_baseline:.0f}% to {new_coverage:.0f}% (below {self.TOLERANCE_MARGIN}% tolerance margin)",
                "regression_amount": current_baseline - new_coverage,
                "tolerance_threshold": tolerance_threshold,
                "allowed": False,
                "baseline_updated": False,
            }
        # The floor is compared as a FLOOR, not as the raw measurement.
        # Comparing the measurement against a floor that was itself
        # derived from a measurement made every refresh look like an
        # improvement, and the ratchet rewrote itself on every run.
        if new_floor > current_baseline + 0.01:
            milestones_hit = self._check_milestones(
                current_baseline,
                new_coverage,
                data,
            )
            self._update_baseline(new_floor, data, milestones_hit)
            self._update_pyproject_requirement(new_floor)

            return {
                "status": "improved",
                "message": f"Coverage improved from {current_baseline:.0f}% to {new_floor:.0f}% !",
                "improvement": new_floor - current_baseline,
                "milestones": milestones_hit,
                "progress_to_100": f"{new_coverage:.0f}% of the way to 100 % coverage",
                "next_milestone": self._get_next_milestone(new_coverage),
                "points_to_next": (next_milestone - new_coverage)
                if (next_milestone := self._get_next_milestone(new_coverage))
                is not None
                else 0,
                "allowed": True,
                "baseline_updated": True,
            }

        self._refresh_freshness()
        return {
            "status": "maintained",
            "message": f"Coverage maintained at {new_coverage:.0f}% (within {self.TOLERANCE_MARGIN}% tolerance margin)",
            "allowed": True,
            "baseline_updated": False,
        }

    def _check_milestones(
        self,
        old_coverage: float,
        new_coverage: float,
        data: dict[str, t.Any],
    ) -> list[float]:
        achieved_milestones = _achieved_milestone_values(
            data.get("milestones_achieved", [])
        )
        return [
            milestone
            for milestone in self.MILESTONES
            if (
                old_coverage < milestone <= new_coverage
                and milestone not in achieved_milestones
            )
        ]

    def _get_next_milestone(self, coverage: float) -> float | None:
        for milestone in self.MILESTONES:
            if milestone > coverage:
                return milestone
        return None

    def _update_baseline(
        self,
        new_floor: float,
        data: dict[str, t.Any],
        milestones_hit: list[float],
    ) -> None:
        """Write the new floor to both floor fields and record it.

        ``new_floor`` is the ENFORCED floor (see ``enforced_floor``),
        not the raw measurement — the two floor fields are written
        together so the release audit and the update gate never
        disagree about what the floor is.
        """
        data["baseline"] = new_floor
        data["current_minimum"] = new_floor
        data["last_updated"] = datetime.now(UTC).isoformat()

        data["history"].append(
            {
                "date": datetime.now(UTC).isoformat(),
                "coverage": new_floor,
                "commit": "current",
                "milestone": milestones_hit,
                "milestones_hit": milestones_hit,
            },
        )

        achieved = data.setdefault("milestones_achieved", [])
        for milestone in milestones_hit:
            if milestone not in achieved:
                achieved.append(milestone)
        # Normalize the shape on every write: a hand-written ratchet may
        # hold dicts, and leaving them in place means the next refresh
        # compares a number against dicts and appends a duplicate.
        data["milestones_achieved"] = _normalize_milestones_achieved(
            data["milestones_achieved"]
        )

        data["next_milestone"] = self._get_next_milestone(new_floor)

        if len(data["history"]) > 50:
            data["history"] = data["history"][-50:]

        data.update(self._ratchet_metadata())

        self.ratchet_file.write_text(json.dumps(data, indent=2))

    def raise_floor(self, new_coverage: float) -> float:
        """Raise the enforced floor and rewrite the ratchet.

        The counterpart to :meth:`lower_baseline` for the case where
        coverage improved. Both floor fields are written together and
        the staleness metadata is refreshed, so a ratchet written here
        is as trustworthy as one written by :meth:`update_coverage`.

        The value is floored to a whole point on the way in, like every
        other write path, so the ratchet and the pyproject mirror can
        never disagree about the floor.

        Returns the floor written.

        Callers must not write ``.coverage-ratchet.json`` directly:
        a hand-written ratchet carries neither the fresh metadata nor
        both floor fields, which is what makes the release audit and
        the ratchet gate disagree.
        """
        floor = enforced_floor(new_coverage)
        data = self.get_ratchet_data()
        if not data:
            return floor
        data["baseline"] = floor
        data["current_minimum"] = floor
        data["last_updated"] = datetime.now(UTC).isoformat()
        data.update(self._ratchet_metadata())
        self.ratchet_file.write_text(json.dumps(data, indent=2))
        return floor

    def _update_pyproject_requirement(self, new_coverage: float) -> None:
        try:
            content = self.pyproject_file.read_text()

            updated_content = update_coverage_requirement(content, new_coverage)
            updated_content = _update_fail_under_mirror(updated_content, new_coverage)

            if updated_content != content:
                updated_content = (
                    FileSystemService.clean_trailing_whitespace_and_newlines(
                        updated_content,
                    )
                )

                self.pyproject_file.write_text(updated_content)
                self.console.print(
                    f"[cyan]📝[/cyan] Updated pyproject.toml coverage requirement to {new_coverage:.0f}%",
                )

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to update pyproject.toml: {e}",
            )

    def get_progress_visualization(self) -> str:
        data = self.get_ratchet_data()
        if not data:
            return "Coverage ratchet not initialized"

        current = data["baseline"]
        target = 100.0
        next_milestone = data.get("next_milestone")

        progress_chars = int(current / target * 20)
        bar = "█" * progress_chars + "░" * (20 - progress_chars)

        result = f"Coverage Progress: {current:.0f}% [{bar}] → 100%\n"
        result += f" Current ─┘{'':18} └─ Goal\n"

        if next_milestone:
            points_needed = next_milestone - current
            result += f"Next milestone: {next_milestone:.0f}% (+{points_needed:.0f}% needed)\n"

        return result

    def get_coverage_improvement_needed(self) -> float:
        current = self.get_baseline_coverage()
        for milestone in self.MILESTONES:
            if current < milestone:
                needed = milestone - current
                return max(0.0, needed)
        return 0.0

    def _calculate_trend(self, data: dict[str, t.Any]) -> str:
        history = data.get("history", [])
        if len(history) < 2:
            return "insufficient_data"

        recent_entries = history[-5:]
        if len(recent_entries) < 2:
            return "insufficient_data"

        start_coverage = recent_entries[0]["coverage"]
        end_coverage = recent_entries[-1]["coverage"]

        if end_coverage > start_coverage + 0.5:
            return "improving"
        if end_coverage < start_coverage - 0.5:
            return "declining"
        return "stable"

    def display_milestone_celebration(self, milestones: list[float]) -> None:
        for milestone in milestones:
            if milestone == 100.0:
                self.console.print(
                    "[gold]🎉🏆 PERFECT ! 100 % COVERAGE ACHIEVED ! 🏆🎉[/gold]",
                )
            elif milestone >= 90:
                self.console.print(
                    f"[gold]🏆 Milestone achieved: {milestone:.0f}% coverage ! Approaching perfection ![/gold]",
                )
            elif milestone >= 50:
                self.console.print(
                    f"[green]🎯 Milestone achieved: {milestone:.0f}% coverage ! Great progress ![/green]",
                )
            else:
                self.console.print(
                    f"[cyan]📈 Milestone achieved: {milestone:.0f}% coverage ! Keep it up ![/cyan]",
                )

    def show_progress_with_spinner(self) -> None:
        data = self.get_ratchet_data()
        if not data:
            return

        current = data["baseline"]
        target = 100.0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage: > 3.0f}%"),
        ) as progress:
            task = progress.add_task(
                "Coverage Progress",
                total=target,
                completed=current,
            )
            progress.update(task, description=f"Coverage: {current:.0f}% / 100 %")

    def get_coverage_report(self) -> str | None:
        data = self.get_ratchet_data()
        if not data:
            return None

        current_coverage = data.get("baseline", 0.0)
        next_milestone = data.get("next_milestone")

        report = f"Coverage: {current_coverage:.0f}%"
        if next_milestone:
            progress = (current_coverage / next_milestone) * 100
            report += f" (next milestone: {next_milestone:.0f}%, {progress:.0f}% there)"

        return report

    def check_and_update_coverage(self) -> dict[str, t.Any]:
        try:
            coverage_file = self.pkg_path / "coverage.json"
            if not coverage_file.exists():
                return {
                    "success": True,
                    "status": "no_coverage_data",
                    "message": "No coverage data found-tests passed without coverage",
                    "allowed": True,
                    "baseline_updated": False,
                }

            coverage_data = json.loads(coverage_file.read_text())
            current_coverage = coverage_data.get("totals", {}).get(
                "percent_covered",
                0.0,
            )

            result = self.update_coverage(current_coverage)
            result["success"] = result.get("allowed", True)
            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to read coverage data",
            }

    def lower_baseline(self, new_coverage: float, reason: str) -> None:
        """Lower the enforced coverage floor, with a recorded reason.

        ``baseline`` and ``current_minimum`` are two names for the same
        enforced floor, but they are read by different gates: the
        release audit reads ``current_minimum`` while
        ``update_coverage()`` reads ``baseline``. Writing only one of
        them leaves the two gates disagreeing about what the floor is —
        the audit would accept a coverage the gate still calls a
        regression, which is how a lowered ratchet could end up
        blocking the very publish it was lowered to unblock.

        Both fields are therefore written together here.

        The value is floored to a whole point on the way in, like every
        other write path, so the ratchet and the pyproject mirror stay
        in agreement and the floor stays a value the suite can meet.
        """
        if not reason or not reason.strip():
            msg = "lower_baseline requires a non-empty reason"
            raise ValueError(msg)
        data = self.get_ratchet_data()
        if not data:
            msg = "Coverage ratchet not initialized"
            raise ValueError(msg)
        floor = enforced_floor(new_coverage)
        data["baseline"] = floor
        data["current_minimum"] = floor
        data["last_updated"] = datetime.now(UTC).isoformat()
        data["history"].append(
            {
                "date": datetime.now(UTC).isoformat(),
                "coverage": floor,
                "commit": "lower",
                "milestone": False,
                "reason": reason,
            }
        )
        data.update(self._ratchet_metadata())
        self.ratchet_file.write_text(json.dumps(data, indent=2))

    def mirror_to_pyproject(self, coverage: float) -> None:
        """Write --cov-fail-under=<floor> to pyproject.toml.

        Updates BOTH `[tool.pytest.ini_options].addopts` (pytest-cov CLI flag)
        and `[tool.coverage.report].fail_under` (coverage.py 7.x config block)
        when present. The ratchet is the source of truth — both mirror sites
        must agree, since either entry-point (pytest or `coverage report`) can
        enforce the floor.

        The value is floored to a whole point on the way in, so a caller
        that measured the coverage and a caller that chose the floor
        explicitly cannot leave the two mirror sites disagreeing.
        """
        coverage = enforced_floor(coverage)
        content = self.pyproject_file.read_text()
        pattern = r"--cov-fail-under=\d+(?:\.\d+)?"
        replacement = f"--cov-fail-under={coverage}"
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
        elif re.search(r"addopts\s*=\s*\[", content):
            # Array-form addopts: insert as a new list element before the closing ]
            array_match = re.compile(r"(addopts\s*=\s*\[\s*)([^\]]*?)(\s*\])").search(
                content
            )
            if array_match is None:
                msg = "addopts array detected but regex did not match"
                raise RuntimeError(msg)
            existing = array_match.group(2).rstrip().rstrip(",").rstrip()
            prefix = "    "  # match pytest convention of indented list items
            if existing:
                new_option = f'{existing},\n{prefix}"{replacement}",'
            else:
                new_option = f'{prefix}"{replacement}",'
            content = (
                content[: array_match.start(2)]
                + new_option
                + content[array_match.end(2) :]
            )
        elif "addopts" in content:
            content = re.sub(
                r'(addopts\s*=\s*"[^"]*)"',
                rf'\1 {replacement}"',
                content,
                count=1,
            )
        else:
            content = (
                f'{content}\n[tool.pytest.ini_options]\naddopts = "{replacement}"\n'
            )
        # Mirror #2: [tool.coverage.report].fail_under (coverage.py 7.x canonical)
        content = _update_fail_under_mirror(content, coverage)
        self.pyproject_file.write_text(content)

    def report_status(self) -> str:
        data = self.get_ratchet_data()
        if not data:
            return "Coverage ratchet not initialized"
        baseline = data.get("baseline", 0.0)
        current = data.get("current_minimum", 0.0)
        next_milestone = data.get("next_milestone")
        history = data.get("history", [])
        lines = [
            f"Baseline: {baseline:.1f}%",
            f"Current minimum: {current:.1f}%",
            f"Next milestone: {next_milestone}",
            f"History entries: {len(history)}",
        ]
        return "\n".join(lines)
