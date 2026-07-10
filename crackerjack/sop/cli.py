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
    app_obj.add_typer(app, name="sop")
