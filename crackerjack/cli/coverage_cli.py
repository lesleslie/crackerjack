from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import typer

from crackerjack.skills.coverage import (
    DEFAULT_THRESHOLD_DAYS,
    skill_coverage_report,
)
from crackerjack.skills.mcp_skills import MCP_SKILL_GROUPS
from crackerjack.skills.registration import register_mcp_skills

DEFAULT_SESSION_BUDDY_URL: str = "http://localhost: 8678/mcp"


app = typer.Typer(
    name="coverage",
    help="Coverage reports (Phase 1.5 wiring, Item 4 of bodai-adoption-phase-1.5).",
    add_completion=False,
)


def _get_crackerjack_skill_names() -> list[str]:
    registry = register_mcp_skills()
    return [s["name"] for s in registry.list_all_skills()]


async def _fetch_distilled_skill_health(
    *,
    session_buddy_url: str,
    threshold_days: int,
    crackerjack_skill_names: list[str],
) -> list[dict[str, Any]]:
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "distilled_skill_health",
            "arguments": {
                "threshold_days": threshold_days,
                "crackerjack_skill_names": crackerjack_skill_names,
            },
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(session_buddy_url, json=payload)
        resp.raise_for_status()
        body = resp.json()
    result = body.get("result", {})

    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return json.loads(first["text"])
    if isinstance(result, list):
        return result
    return []


def _format_table(report: Any) -> str:
    lines = [
        "Skill coverage report",
        "======================",
        "",
        f" Threshold (days): {report.threshold_days}",
        f" Distilled skills: {report.total_distilled}",
        f" Crackerjack skills: {len(report.crackerjack_only) + _matched_count(report)}",
        "",
        " Bucket counts",
        " -------------",
        f" fresh: {report.fresh}",
        f" cold: {report.cold}",
        f" stale: {report.stale}",
        f" under_utilized: {report.under_utilized}",
        "",
    ]
    if report.crackerjack_only:
        lines.append(" Crackerjack-only skills (cold-start):")
        for name in report.crackerjack_only:
            lines.append(f" - {name}")
        lines.append("")
    if report.distilled:
        lines.extend((" Distilled skill status", " ----------------------"))

        for row in report.distilled:
            lines.append(
                f" [{row.status:<14}] {row.id:<24} "
                f"importance={row.importance_score:.2f} "
                f"evidence={row.evidence_count} "
                f"last_reinforced={row.last_reinforced_at or '?'}"
            )
    return "\n".join(lines)


def _matched_count(report: Any) -> int:

    return 0


@app.command()
def skills(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of a table.",
    ),
    threshold_days: int = typer.Option(
        DEFAULT_THRESHOLD_DAYS,
        "--threshold-days",
        help="Days since last_reinforced_at before a skill is 'stale'.",
    ),
    session_buddy_url: str = typer.Option(
        os.environ.get("SESSION_BUDDY_MCP_URL", DEFAULT_SESSION_BUDDY_URL),
        "--session-buddy-url",
        help="Session-Buddy MCP endpoint.",
    ),
) -> None:
    crackerjack_skill_names = _get_crackerjack_skill_names()

    async def runner() -> Any:
        return await skill_coverage_report(
            session_buddy_client=_LocalClient(
                threshold_days=threshold_days,
                crackerjack_skill_names=crackerjack_skill_names,
                session_buddy_url=session_buddy_url,
            ),
            crackerjack_skill_names=crackerjack_skill_names,
            threshold_days=threshold_days,
        )

    report = asyncio.run(runner())

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "cold": report.cold,
                    "stale": report.stale,
                    "under_utilized": report.under_utilized,
                    "fresh": report.fresh,
                    "threshold_days": report.threshold_days,
                    "total_distilled": report.total_distilled,
                    "crackerjack_only": report.crackerjack_only.copy(),
                    "distilled": [
                        {
                            "id": row.id,
                            "problem_pattern": row.problem_pattern,
                            "importance_score": row.importance_score,
                            "evidence_count": row.evidence_count,
                            "last_reinforced_at": row.last_reinforced_at,
                            "status": row.status,
                        }
                        for row in report.distilled
                    ],
                },
                indent=2,
            )
        )
    else:
        typer.echo(_format_table(report))


class _LocalClient:
    def __init__(
        self,
        *,
        threshold_days: int,
        crackerjack_skill_names: list[str],
        session_buddy_url: str,
    ) -> None:
        self._threshold_days = threshold_days
        self._crackerjack_skill_names = crackerjack_skill_names
        self._url = session_buddy_url

    async def call_tool(
        self,
        tool_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if tool_name != "distilled_skill_health":
            raise ValueError(f"unsupported tool for coverage report: {tool_name!r}")
        return await _fetch_distilled_skill_health(
            session_buddy_url=self._url,
            threshold_days=self._threshold_days,
            crackerjack_skill_names=self._crackerjack_skill_names,
        )


__all__ = [
    "app",
    "DEFAULT_SESSION_BUDDY_URL",
    "MCP_SKILL_GROUPS",
]
