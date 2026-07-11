from __future__ import annotations

import json

import typer

from human_to_agent.cli.app_types import OutputFormat
from human_to_agent.cli.result import CommandResult


def emit(result: CommandResult, output_format: OutputFormat) -> None:
    if output_format is OutputFormat.json:
        typer.echo(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(f"{result.command}: {result.status}")
        for diagnostic in result.diagnostics:
            typer.echo(f"[{diagnostic['category']}] {diagnostic['message']}")
        for path in result.changed_files:
            typer.echo(path)
    if result.exit_code:
        raise typer.Exit(result.exit_code)
