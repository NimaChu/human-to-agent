from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated

import typer

from harness_foundry import __version__
from harness_foundry.cli.result import CommandResult


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def root() -> None:
    """Harness Foundry command line."""


@app.command()
def version(
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.text,
) -> None:
    """Show the Harness Foundry version."""
    result = CommandResult(command="version")
    if output_format is OutputFormat.json:
        typer.echo(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(f"Harness Foundry {__version__}")


def main() -> None:
    app()
