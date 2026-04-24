"""CLI entrypoint for azdeeploy."""

import typer
from rich.console import Console

app = typer.Typer(help="Deployment diagnostics and Azure helper CLI.")
console = Console()


@app.command()
def version() -> None:
    """Show the package version."""
    from azdeeploy import __version__

    console.print(f"azdeeploy {__version__}")


@app.command()
def health() -> None:
    """Basic health check command."""
    console.print("[green]azdeeploy is ready[/green]")


if __name__ == "__main__":
    app()
