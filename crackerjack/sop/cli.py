"""CLI commands for project-scoped SOPs (Spec #7).

Subcommands:

- ``sop list``   -- list SOPs for a project (in-memory store; stub output)
- ``sop show``   -- show a single SOP body
- ``sop propose``-- record a failure observation and surface a proposal when
  the threshold is crossed (stub -- surfaces the proposal but does not
  apply it)

The CLI is intentionally a thin shell over the SOP domain. The persister is
in-memory for v0; the Dhara-backed persister lands as a follow-up.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import typer

from crackerjack.sop.evolution import EvolutionEngine, EvolutionTrigger
from crackerjack.sop.models import FailureModeCatalog
from crackerjack.sop.persisters import InMemorySOPPersister

app = typer.Typer(
    name="sop",
    help="Project-scoped SOP evolution (Spec #7).",
    add_completion=False,
)


def _build_engine(project_id: str) -> tuple[EvolutionEngine, InMemorySOPPersister]:
    """Construct an EvolutionEngine + InMemorySOPPersister pair for one CLI
    invocation. Each invocation gets a fresh in-memory store -- persistence
    is the job of the (future) Dhara-backed persister.
    """
    persister = InMemorySOPPersister()
    catalog = FailureModeCatalog(project_id=project_id)
    trigger = EvolutionTrigger()
    return EvolutionEngine(
        persister=persister, trigger=trigger, catalog=catalog
    ), persister


@app.command("list")
def sop_list(
    project_id: str = typer.Option(..., "--project", "-p", help="Project id"),
) -> None:
    """List SOPs for a project (stub)."""
    _, persister = _build_engine(project_id)
    sops = persister.list(project_id)
    if not sops:
        typer.echo(f"No SOPs recorded for project '{project_id}'.")
        raise typer.Exit(code=0)
    for sop in sops:
        typer.echo(
            f"{sop.project_id}/{sop.name} v{sop.version} "
            f"(evolved_at={sop.last_evolved_at})"
        )


@app.command("show")
def sop_show(
    project_id: str = typer.Option(..., "--project", "-p", help="Project id"),
    name: str = typer.Option(..., "--name", "-n", help="SOP name"),
) -> None:
    """Show one SOP's body (stub)."""
    _, persister = _build_engine(project_id)
    sop = persister.get(project_id, name)
    if sop is None:
        typer.echo(f"No SOP named '{name}' for project '{project_id}'.")
        raise typer.Exit(code=1)
    typer.echo(f"# {sop.project_id}/{sop.name} v{sop.version}")
    if sop.last_failure_id:
        typer.echo(f"# last_failure_id={sop.last_failure_id}")
    typer.echo(sop.body)


@app.command("propose")
def sop_propose(
    project_id: str = typer.Option(..., "--project", "-p", help="Project id"),
    sop_name: str = typer.Option(..., "--sop", "-s", help="SOP name to evolve"),
    fingerprint: str = typer.Option(
        ..., "--fingerprint", "-f", help="Failure-mode fingerprint"
    ),
    description: str = typer.Option(
        "", "--description", "-d", help="Failure description"
    ),
    body: str = typer.Option(
        "", "--body", "-b", help="Current SOP body (for the proposal context)"
    ),
) -> None:
    """Record a failure observation and surface a proposal when the trigger
    fires (stub -- never auto-applies)."""
    engine, _ = _build_engine(project_id)
    at = datetime.now(UTC)
    engine.observe_failure(
        fingerprint=fingerprint,
        description=description,
        at=at,
    )
    proposal = engine.propose(sop_name=sop_name, current_body=body, at=at)
    if proposal is None:
        typer.echo(
            f"Recorded observation of '{fingerprint}' for project "
            f"'{project_id}'; trigger not yet fired."
        )
        raise typer.Exit(code=0)
    payload: dict[str, Any] = {
        "sop_name": proposal.sop_name,
        "fingerprint": proposal.fingerprint,
        "observed_count": proposal.observed_count,
        "proposed_at": proposal.proposed_at.isoformat(),
        "current_body": proposal.current_body,
    }
    typer.echo("Proposal ready for review:")
    typer.echo(str(payload))


def add_sop_commands(app_obj: typer.Typer) -> None:
    """Register the ``sop`` subcommand group on a parent Typer app."""
    app_obj.add_typer(app, name="sop")
