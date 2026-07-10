from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from harness_foundry import __version__
from harness_foundry.cli.app_types import OutputFormat
from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.output import emit
from harness_foundry.cli.result import CommandResult
from harness_foundry.domain.builds import BuildMode
from harness_foundry.domain.events import EventScope
from harness_foundry.repositories.events import EventStore
from harness_foundry.services.build import Builder
from harness_foundry.services.changes import record_change as record_source_change
from harness_foundry.services.doctor import inspect_workspace
from harness_foundry.services.stage_transitions import advance_stage as apply_stage_advance
from harness_foundry.services.validation import validate_root
from harness_foundry.services.workspaces import (
    create_workspace,
    initialize,
    list_workspaces,
    require_workspace,
    status,
)

FormatOption = Annotated[OutputFormat, typer.Option("--format")]
RootOption = Annotated[Path, typer.Option("--root")]
DryRunOption = Annotated[bool, typer.Option("--dry-run")]
WorkspaceOption = Annotated[str, typer.Option("--workspace", "-w")]

app = typer.Typer(no_args_is_help=True, add_completion=False)
workspace_app = typer.Typer(no_args_is_help=True)
capture_app = typer.Typer(no_args_is_help=True)
unknown_app = typer.Typer(no_args_is_help=True)
stage_app = typer.Typer(no_args_is_help=True)
readiness_app = typer.Typer(no_args_is_help=True)
events_app = typer.Typer(no_args_is_help=True)

app.add_typer(workspace_app, name="workspace")
app.add_typer(capture_app, name="capture")
app.add_typer(unknown_app, name="unknown")
app.add_typer(stage_app, name="stage")
app.add_typer(readiness_app, name="readiness")
app.add_typer(events_app, name="events")


def _run(command: str, output_format: OutputFormat, operation: Callable[[], CommandResult]) -> None:
    try:
        result = operation()
    except FoundryError as error:
        result = CommandResult(
            command=command,
            status="error",
            exit_code=error.exit_code,
            diagnostics=[
                {"category": error.category, "code": error.code, "message": error.message}
            ],
        )
    emit(result, output_format)


def _pending(command: str, root: Path, workspace: str, dry_run: bool = False) -> CommandResult:
    require_workspace(root, workspace)
    return CommandResult(
        command=command,
        status="dry-run" if dry_run else "ok",
        next_actions=["Provide or update the evidence-backed normative asset files."],
    )


@app.command()
def version(output_format: FormatOption = OutputFormat.text) -> None:
    """Show the Harness Foundry version."""
    result = CommandResult(command="version")
    if output_format is OutputFormat.text:
        typer.echo(f"Harness Foundry {__version__}")
        return
    emit(result, output_format)


@app.command("init")
def init_command(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    dry_run: DryRunOption = False,
) -> None:
    """Initialize the mother workspace."""
    _run("init", output_format, lambda: initialize(root.resolve(), dry_run=dry_run))


@workspace_app.command("new")
def workspace_new(
    slug: Annotated[str, typer.Argument()] = "workspace",
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    owner: Annotated[str, typer.Option("--owner")] = "maintainer",
    dry_run: DryRunOption = False,
) -> None:
    """Create a canonical child workspace."""
    _run(
        "workspace new",
        output_format,
        lambda: create_workspace(root.resolve(), slug, owner=owner, dry_run=dry_run),
    )


@workspace_app.command("list")
def workspace_list(
    output_format: FormatOption = OutputFormat.text, root: RootOption = Path(".")
) -> None:
    """List child workspaces."""
    _run("workspace list", output_format, lambda: list_workspaces(root.resolve()))


@workspace_app.command("status")
def workspace_status(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
) -> None:
    """Show the stage and autonomy status."""
    _run("workspace status", output_format, lambda: status(root.resolve(), workspace))


@capture_app.command("record")
def capture_record(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Record a work-reproduction capture."""
    _run(
        "capture record",
        output_format,
        lambda: _pending("capture record", root.resolve(), workspace, dry_run),
    )


def _unknown_command(
    name: str, output_format: OutputFormat, root: Path, workspace: str, dry_run: bool
) -> None:
    _run(
        f"unknown {name}",
        output_format,
        lambda: _pending(f"unknown {name}", root.resolve(), workspace, dry_run),
    )


@unknown_app.command("add")
def unknown_add(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Add an Unknown without inventing missing facts."""
    _unknown_command("add", output_format, root, workspace, dry_run)


@unknown_app.command("update")
def unknown_update(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Update an Unknown."""
    _unknown_command("update", output_format, root, workspace, dry_run)


@unknown_app.command("close")
def unknown_close(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Close an Unknown with evidence."""
    _unknown_command("close", output_format, root, workspace, dry_run)


@unknown_app.command("reopen")
def unknown_reopen(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Reopen an Unknown while preserving its history."""
    _unknown_command("reopen", output_format, root, workspace, dry_run)


@app.command("validate")
def validate_command(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: Annotated[str | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Validate Schemas, references, evidence, and recorded content."""
    emit(validate_root(root.resolve(), workspace), output_format)


def _stage_command(
    name: str, output_format: OutputFormat, root: Path, workspace: str, dry_run: bool = False
) -> None:
    _run(
        f"stage {name}",
        output_format,
        lambda: _pending(f"stage {name}", root.resolve(), workspace, dry_run),
    )


@stage_app.command("assess")
def stage_assess(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
) -> None:
    """Assess the current stage gate."""
    _stage_command("assess", output_format, root, workspace)


@stage_app.command("advance")
def stage_advance(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Advance only after the prospective gate passes."""
    _run(
        "stage advance",
        output_format,
        lambda: apply_stage_advance(root.resolve(), workspace, actor="maintainer", dry_run=dry_run),
    )


@stage_app.command("reopen")
def stage_reopen(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Reopen a prior stage after material change."""
    _stage_command("reopen", output_format, root, workspace, dry_run)


@readiness_app.command("assess")
def readiness_assess(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
) -> None:
    """Assess 10 readiness and 6 autonomy dimensions."""
    _run(
        "readiness assess",
        output_format,
        lambda: _pending("readiness assess", root.resolve(), workspace),
    )


@app.command("diff")
def diff_command(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
) -> None:
    """Compare source files with their recorded artifact index."""
    _run("diff", output_format, lambda: _pending("diff", root.resolve(), workspace))


@app.command("record-change")
def record_change(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Validate and record normative source changes atomically."""
    _run(
        "record-change",
        output_format,
        lambda: record_source_change(root.resolve(), workspace, dry_run=dry_run),
    )


@app.command("migrate")
def migrate_command(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    dry_run: DryRunOption = False,
) -> None:
    """Run sequential, recoverable Schema migrations."""
    _run("migrate", output_format, lambda: _pending("migrate", root.resolve(), workspace, dry_run))


@app.command("build")
def build_command(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
    draft: Annotated[bool, typer.Option("--draft")] = False,
    release: Annotated[bool, typer.Option("--release")] = False,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    dry_run: DryRunOption = False,
) -> None:
    """Build a deterministic draft or gate-checked release distribution."""

    def operation() -> CommandResult:
        if draft == release:
            raise FoundryError("usage", "build.mode", "Choose exactly one of --draft or --release.")
        mode = BuildMode.draft if draft else BuildMode.release
        try:
            builder = Builder(root.resolve())
            result = builder.build(builder.plan(workspace, mode, output, dry_run=dry_run))
        except ValueError as error:
            raise FoundryError("gate", "build.release_gate", str(error)) from error
        return CommandResult(
            command="build",
            status="dry-run" if dry_run else "ok",
            changed_files=[]
            if dry_run
            else [str(result.path / item) for item in result.changed_files],
            next_actions=[f"mode={mode.value}", f"source_digest={result.source_digest}"],
        )

    _run("build", output_format, operation)


def _event_scope(root: Path, workspace: str) -> EventScope:
    path = require_workspace(root, workspace)
    return EventScope(scope_id=workspace, log_path=path / ".foundry" / "events.jsonl")


@events_app.command("verify")
def events_verify(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
) -> None:
    """Verify the append-only event hash chain."""

    def operation() -> CommandResult:
        verification = EventStore().verify(_event_scope(root.resolve(), workspace))
        diagnostics: list[dict[str, object]] = (
            []
            if verification.valid
            else [
                {"category": "event", "code": "event.invalid", "message": item}
                for item in verification.errors
            ]
        )
        return CommandResult(
            command="events verify",
            status="ok" if verification.valid else "error",
            exit_code=0 if verification.valid else 9,
            diagnostics=diagnostics,
            next_actions=[f"events={verification.event_count}"],
        )

    _run("events verify", output_format, operation)


@events_app.command("replay")
def events_replay(
    output_format: FormatOption = OutputFormat.text,
    root: RootOption = Path("."),
    workspace: WorkspaceOption = "workspace",
) -> None:
    """Replay stored events in sequence."""

    def operation() -> CommandResult:
        replay = EventStore().replay(_event_scope(root.resolve(), workspace))
        return CommandResult(
            command="events replay", next_actions=[item.event_id for item in replay.events]
        )

    _run("events replay", output_format, operation)


@app.command("doctor")
def doctor(output_format: FormatOption = OutputFormat.text, root: RootOption = Path(".")) -> None:
    """Check configuration, recovery state, and normative-source hygiene."""
    resolved = root.resolve()
    if not (resolved / "foundry.yaml").is_file():
        emit(
            CommandResult(
                command="doctor",
                status="error",
                exit_code=2,
                diagnostics=[
                    {
                        "category": "config",
                        "code": "config.missing",
                        "message": "foundry.yaml is missing",
                    }
                ],
            ),
            output_format,
        )
        return
    emit(inspect_workspace(resolved), output_format)


def main() -> None:
    app()
