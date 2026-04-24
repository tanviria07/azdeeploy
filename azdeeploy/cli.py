"""CLI entrypoint for azdeeploy."""

from pathlib import Path

import typer
from openai import OpenAI
from rich.console import Console
from rich.prompt import Prompt

from azdeeploy import __version__
from azdeeploy.config import load_config

app = typer.Typer(help="Deployment diagnostics and Azure helper CLI.")
console = Console()


def azdeeploy() -> None:
    """Console script entrypoint."""
    app()


@app.command()
def version() -> None:
    """Show the package version."""
    console.print(f"azdeeploy {__version__}")


@app.command()
def init() -> None:
    """Prompt for DeepSeek credentials and write them to a .env file."""
    api_key = Prompt.ask("Enter your DeepSeek API key", password=True).strip()
    if not api_key:
        raise typer.BadParameter("API key cannot be empty.")

    env_path = Path.cwd() / ".env"
    env_path.write_text(
        "\n".join(
            [
                f"AZDEEPPLOY_DEEPSEEK_API_KEY={api_key}",
                "AZDEEPPLOY_DEEPSEEK_BASE_URL=https://api.deepseek.com",
                "",
            ]
        ),
        encoding="utf-8",
    )
    console.print(f"[green]Wrote configuration to {env_path}[/green]")


@app.command()
def ask(question: str = typer.Argument(..., help="Question to send to DeepSeek.")) -> None:
    """Ask DeepSeek a question and stream the response."""
    try:
        settings = load_config()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )

    stream = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": question}],
        stream=True,
    )

    console.print("[bold blue]Asking DeepSeek...[/bold blue]")
    console.print()

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            console.print(delta, end="")
    console.print()


def _not_implemented(command_name: str) -> None:
    console.print(f"{command_name}: Not implemented yet")


@app.command()
def scan() -> None:
    """Placeholder scan command."""
    _not_implemented("scan")


@app.command()
def plan() -> None:
    """Placeholder plan command."""
    _not_implemented("plan")


@app.command()
def deploy() -> None:
    """Placeholder deploy command."""
    _not_implemented("deploy")


@app.command()
def logs() -> None:
    """Placeholder logs command."""
    _not_implemented("logs")


@app.command()
def diagnose() -> None:
    """Placeholder diagnose command."""
    _not_implemented("diagnose")


@app.command()
def fix() -> None:
    """Placeholder fix command."""
    _not_implemented("fix")


if __name__ == "__main__":
    azdeeploy()
