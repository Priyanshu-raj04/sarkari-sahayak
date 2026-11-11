"""`sahayak` command-line entry point."""

import typer

from sahayak import __version__

app = typer.Typer(no_args_is_help=True, help="Sarkari Sahayak CLI")


@app.callback()
def main() -> None:
    """Sarkari Sahayak: ingest, index, benchmark and serve."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)
