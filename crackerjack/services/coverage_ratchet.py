import json
import typing as t
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn


class CoverageRatchetService:
    MILESTONES = [15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 95, 100]

    TOLERANCE_MARGIN = 2.0

    def __init__(self, pkg_path: Path, console: Console) -> None:
        self.pkg_path = pkg_path
        self.console = console
        self.ratchet_file = pkg_path / ".coverage-ratchet.json"
        self.pyproject_file = pkg_path / "pyproject.toml"

    def initialize_baseline(self, initial_coverage: float) -> None:
        if self.ratchet_file.exists():
            return

        ratchet_data: dict[str, t.Any] = {
            "baseline": initial_coverage,
            "current_minimum": initial_coverage,
            "target": 100.0,
            "last_updated": datetime.now().isoformat(),
            "history": [
                {
                    "date": datetime.now().isoformat(),
                    "coverage": initial_coverage,
                    "commit": "baseline",
                    "milestone": False,
                }
            ],
            "milestones_achieved": [],
            "next_milestone": self._get_next_milestone(initial_coverage),
        }

        self.ratchet_file.write_text(json.dumps(ratchet_data, indent=2))
        self.console.print(
            f"[cyan]📊[/ cyan] Coverage ratchet initialized at {initial_coverage: .2f}% baseline"
        )

    def get_ratchet_data(self) -> dict[str, t.Any]:
        if not self.ratchet_file.exists():
            return {}
        return t.cast(dict[str, t.Any], json.loads(self.ratchet_file.read_text()))

    def get_status_report(self) -> dict[str, t.Any]:
        """Get status report for coverage ratchet service."""
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
                "message": f"Coverage ratchet initialized at {new_coverage: .2f}%",
                "milestones": [],
                "progress_to_100": f"{new_coverage: .1f}% of the way to 100 % coverage",
                "allowed": True,
                "baseline_updated": True,
            }

        data = self.get_ratchet_data()
        current_baseline = data["baseline"]

        tolerance_threshold = current_baseline - self.TOLERANCE_MARGIN
        if new_coverage < tolerance_threshold:
            return {
                "status": "regression",
                "message": f"Coverage decreased from {current_baseline: .2f}% to {new_coverage: .2f}% (below {self.TOLERANCE_MARGIN}% tolerance margin)",
                "regression_amount": current_baseline - new_coverage,
                "tolerance_threshold": tolerance_threshold,
                "allowed": False,
                "baseline_updated": False,
            }
        elif new_coverage > current_baseline + 0.01:
            milestones_hit = self._check_milestones(
                current_baseline, new_coverage, data
            )
            self._update_baseline(new_coverage, data, milestones_hit)
            self._update_pyproject_requirement(new_coverage)

            return {
                "status": "improved",
                "message": f"Coverage improved from {current_baseline: .2f}% to {new_coverage: .2f}% !",
                "improvement": new_coverage - current_baseline,
                "milestones": milestones_hit,
                "progress_to_100": f"{new_coverage: .1f}% of the way to 100 % coverage",
                "next_milestone": self._get_next_milestone(new_coverage),
                "points_to_next": (next_milestone - new_coverage)
                if (next_milestone := self._get_next_milestone(new_coverage))
                is not None
                else 0,
                "allowed": True,
                "baseline_updated": True,
            }

        return {
            "status": "maintained",
            "message": f"Coverage maintained at {new_coverage: .2f}% (within {self.TOLERANCE_MARGIN}% tolerance margin)",
            "allowed": True,
            "baseline_updated": False,
        }

    def _check_milestones(
        self, old_coverage: float, new_coverage: float, data: dict[str, t.Any]
    ) -> list[float]:
        achieved_milestones = set[t.Any](data.get("milestones_achieved", []))
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
        self, new_coverage: float, data: dict[str, t.Any], milestones_hit: list[float]
    ) -> None:
        data["baseline"] = new_coverage
        data["current_minimum"] = new_coverage
        data["last_updated"] = datetime.now().isoformat()

        data["history"].append(
            {
                "date": datetime.now().isoformat(),
                "coverage": new_coverage,
                "commit": "current",
                "milestone": len(milestones_hit) > 0,
                "milestones_hit": milestones_hit,
            }
        )

        for milestone in milestones_hit:
            if milestone not in data["milestones_achieved"]:
                data["milestones_achieved"].append(milestone)

        data["next_milestone"] = self._get_next_milestone(new_coverage)

        if len(data["history"]) > 50:
            data["history"] = data["history"][-50:]

        self.ratchet_file.write_text(json.dumps(data, indent=2))

    def _update_pyproject_requirement(self, new_coverage: float) -> None:
        try:
            content = self.pyproject_file.read_text()

            from crackerjack.services.regex_patterns import update_coverage_requirement

            updated_content = update_coverage_requirement(content, new_coverage)

            if updated_content != content:
                from crackerjack.services.filesystem import FileSystemService

                updated_content = (
                    FileSystemService.clean_trailing_whitespace_and_newlines(
                        updated_content
                    )
                )

                self.pyproject_file.write_text(updated_content)
                self.console.print(
                    f"[cyan]📝[/ cyan] Updated pyproject.toml coverage requirement to {new_coverage: .0f}%"
                )

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Failed to update pyproject.toml: {e}"
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

        result = f"Coverage Progress: {current: .2f}% [{bar}] → 100 %\n"
        result += f" Current ─┘{'': > 18} └─ Goal\n"

        if next_milestone:
            points_needed = next_milestone - current
            result += f"Next milestone: {next_milestone: .0f}% (+{points_needed: .2f}% needed)\n"

        return result

    def get_coverage_improvement_needed(self) -> float:
        """Get percentage improvement needed to reach next milestone."""
        current = self.get_baseline_coverage()
        for milestone in self.MILESTONES:
            if current < milestone:
                needed = milestone - current
                return max(0.0, needed)
        return 0.0
        data = self.get_ratchet_data()
        if not data:
            return {"status": "not_initialized"}

        return {
            "status": "active",
            "current_coverage": data["baseline"],
            "target_coverage": data["target"],
            "next_milestone": data.get("next_milestone"),
            "milestones_achieved": data.get("milestones_achieved", []),
            "total_milestones": len(self.MILESTONES),
            "progress_percent": (data["baseline"] / data["target"]) * 100,
            "last_updated": data["last_updated"],
            "history_count": len(data.get("history", [])),
            "improvement_trend": self._calculate_trend(data),
        }

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
        elif end_coverage < start_coverage - 0.5:
            return "declining"
        return "stable"

    def display_milestone_celebration(self, milestones: list[float]) -> None:
        for milestone in milestones:
            if milestone == 100.0:
                self.console.print(
                    "[gold]🎉🏆 PERFECT ! 100 % COVERAGE ACHIEVED ! 🏆🎉[/ gold]"
                )
            elif milestone >= 90:
                self.console.print(
                    f"[gold]🏆 Milestone achieved: {milestone: .0f}% coverage ! Approaching perfection ![/ gold]"
                )
            elif milestone >= 50:
                self.console.print(
                    f"[green]🎯 Milestone achieved: {milestone: .0f}% coverage ! Great progress ![/ green]"
                )
            else:
                self.console.print(
                    f"[cyan]📈 Milestone achieved: {milestone: .0f}% coverage ! Keep it up ![/ cyan]"
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
                "Coverage Progress", total=target, completed=current
            )
            progress.update(task, description=f"Coverage: {current: .1f}% / 100 %")

    def get_coverage_report(self) -> str | None:
        data = self.get_ratchet_data()
        if not data:
            return None

        current_coverage = data.get("baseline", 0.0)
        next_milestone = data.get("next_milestone")

        report = f"Coverage: {current_coverage: .2f}%"
        if next_milestone:
            progress = (current_coverage / next_milestone) * 100
            report += (
                f" (next milestone: {next_milestone: .0f}%, {progress: .1f}% there)"
            )

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
                "percent_covered", 0.0
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
