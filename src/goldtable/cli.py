"""Command-line interface for goldtable."""

from __future__ import annotations

import typer
from rich.console import Console

from goldtable import __version__

app = typer.Typer(
    name="goldtable",
    help="Snapshot testing for data pipeline outputs.",
    no_args_is_help=True,
    add_completion=False,
)

_err = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"goldtable {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Snapshot testing for data pipeline outputs."""


@app.command()
def diff(
    a: str = typer.Argument(..., help="Baseline source spec (e.g. old.parquet)."),
    b: str = typer.Argument(..., help="Candidate source spec (e.g. new.csv)."),
) -> None:
    """Compare two tables. (Not implemented yet.)"""
    _err.print("[yellow]goldtable diff is not implemented yet.[/yellow]")
    raise typer.Exit(code=2)


def main() -> None:
    """Console-script entry point."""
    app()
