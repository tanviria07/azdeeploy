"""CLI entrypoint for azdeeploy."""

from pathlib import Path

import typer
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich.table import Table

from azdeeploy import __version__
from azdeeploy.azure.app_service import deployment_target_names, generate_deployment_plan
from azdeeploy.azure.commands import check_azure_login, get_last_azure_error, run_az
from azdeeploy.azure.deepseek_client import diagnose as run_diagnosis
from azdeeploy.azure.logs import get_recent_logs, tail_logs
from azdeeploy.config import load_config
from azdeeploy.llm.schemas import Diagnosis
from azdeeploy.patches.patch_parser import generate_fixes
from azdeeploy.scanner.detect_project import DetectionError, scan_project

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


def _read_key_files() -> dict[str, str]:
    """Read a few high-signal project files for diagnosis context."""
    key_files: dict[str, str] = {}
    for name in (
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "main.py",
        "app.py",
        "run.py",
        "api.py",
        "package.json",
        ".env.azure",
    ):
        path = Path.cwd() / name
        if path.exists():
            key_files[name] = path.read_text(encoding="utf-8", errors="ignore")
    return key_files


def _render_scan_result(result: dict[str, object]) -> None:
    """Render a scan result using a Rich panel."""
    body_lines = [
        f"Project type: {result['project_type']}",
    ]

    if result.get("main_file"):
        body_lines.append(f"Main file: {result['main_file']}")
    if result.get("entry_file") and result["entry_file"] != result.get("main_file"):
        body_lines.append(f"Entry file: {result['entry_file']}")
    if result.get("app_object"):
        body_lines.append(f"App object: {result['app_object']}")

    body_lines.append("")
    body_lines.append(f"Startup: [bold green]{result['recommended_startup']}[/bold green]")

    issues = result.get("potential_issues", [])
    if issues:
        body_lines.append("")
        body_lines.append("[yellow]Warnings:[/yellow]")
        body_lines.extend(f"[yellow]- {issue}[/yellow]" for issue in issues)

    console.print(Panel("\n".join(body_lines), title="Project Scan", border_style="cyan"))


def _collect_diagnosis(
    lines: int,
    resource_group: str | None,
    app_name: str | None,
) -> Diagnosis:
    """Collect Azure and local context, then run the diagnosis model."""
    names = deployment_target_names()
    resolved_resource_group = resource_group or names["resource_group"]
    resolved_app_name = app_name or names["app_name"]

    try:
        project_info = scan_project()
        plan_steps = generate_deployment_plan(project_info)
    except (DetectionError, ValueError) as exc:
        console.print(Panel(str(exc), title="Diagnose Failed", border_style="red"))
        raise typer.Exit(code=1) from exc

    log_excerpt = ""
    login_error = ""
    try:
        check_azure_login()
        log_excerpt = get_recent_logs(resolved_resource_group, resolved_app_name, lines=lines)
    except RuntimeError as exc:
        login_error = str(exc)

    context = {
        "project_scan": project_info,
        "deployment_plan_steps_attempted": [step["command"] for step in plan_steps],
        "error_output": "\n\n".join(
            part for part in (get_last_azure_error(), login_error) if part
        ),
        "log_excerpt": log_excerpt,
        "key_files": _read_key_files(),
    }

    try:
        with console.status("[bold blue]Analyzing deployment with DeepSeek...[/bold blue]", spinner="dots"):
            return run_diagnosis(context)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Diagnose Failed", border_style="red"))
        raise typer.Exit(code=1) from exc


def _render_diagnosis(result: Diagnosis) -> None:
    """Render a diagnosis result using Rich."""
    confidence_style = {
        "high": "black on green",
        "medium": "black on yellow",
        "low": "white on red",
    }.get(result.confidence.lower(), "white on blue")
    risk_icon = {
        "low": "[green]i LOW[/green]",
        "medium": "[yellow]! MEDIUM[/yellow]",
        "high": "[red]!! HIGH[/red]",
    }.get(result.risk_level.lower(), f"[blue]? {result.risk_level.upper()}[/blue]")

    console.print(Panel(f"[bold]{result.root_cause}[/bold]", title="Root Cause", border_style="red"))
    console.print(f"Confidence: [{confidence_style}] {result.confidence.upper()} [/]")
    console.print(f"Risk: {risk_icon}")

    if result.evidence:
        console.print("\nEvidence:")
        for item in result.evidence:
            console.print(f"- {item}")

    console.print(
        Panel(result.recommended_fix, title="Recommended Fix", border_style="green")
    )

    if result.azure_commands:
        console.print(
            Panel("\n".join(result.azure_commands), title="Azure Commands", border_style="cyan")
        )

    if result.code_or_config_patch:
        console.print(
            Panel(result.code_or_config_patch, title="Code Or Config Patch", border_style="magenta")
        )


def _render_proposed_fixes(fixes: list[dict]) -> None:
    """Render proposed fixes in a numbered table."""
    table = Table(title="Proposed Fixes")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Type", style="magenta")
    table.add_column("Description")
    table.add_column("Safe", justify="center")

    for index, fix in enumerate(fixes, start=1):
        table.add_row(
            str(index),
            str(fix["type"]),
            str(fix["description"]),
            "yes" if fix["is_safe"] else "no",
        )

    console.print(table)


def _parse_fix_selection(selection: str, total: int) -> list[int]:
    """Parse a user's fix selection input into zero-based indices."""
    raw = selection.strip().lower()
    if raw in {"all", "*"}:
        return list(range(total))

    selected: list[int] = []
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            index = int(value)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid fix selection: {value}") from exc
        if index < 1 or index > total:
            raise typer.BadParameter(f"Fix selection out of range: {value}")
        zero_based = index - 1
        if zero_based not in selected:
            selected.append(zero_based)
    return selected


def _confirm_action(prompt_text: str, *, default: str = "n") -> bool:
    """Prompt the user for a yes/no confirmation."""
    response = Prompt.ask(prompt_text, default=default).strip().lower()
    return response in {"y", "yes"}


def _show_fix_preview(fix: dict) -> None:
    """Show the concrete changes a fix would make."""
    body_lines = [fix["description"], f"Safe: {'yes' if fix['is_safe'] else 'no'}"]

    if fix["commands_to_run"]:
        body_lines.append("")
        body_lines.append("Commands:")
        body_lines.extend(f"  - {command}" for command in fix["commands_to_run"])

    if fix["file_writes"]:
        body_lines.append("")
        body_lines.append("Files:")
        body_lines.extend(f"  - {path}" for path in fix["file_writes"])

    console.print(Panel("\n".join(body_lines), title=f"Fix: {fix['type']}", border_style="cyan"))


def _apply_fix(fix: dict, *, dry_run: bool) -> None:
    """Apply a single fix object."""
    if fix["file_writes"]:
        for path_str, content in fix["file_writes"].items():
            path = Path(path_str)
            if dry_run:
                console.print(f"[cyan]Would write[/cyan] {path}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            console.print(f"[green]Wrote[/green] {path}")

    if fix["commands_to_run"]:
        for command in fix["commands_to_run"]:
            if dry_run:
                console.print(f"[cyan]Would run[/cyan] {command}")
                continue
            run_az(command, skip_confirmation=True)
            console.print(f"[green]Ran[/green] {command}")


@app.command()
def scan() -> None:
    """Scan the current directory for a supported app entrypoint."""
    try:
        result = scan_project()
    except DetectionError as exc:
        console.print(Panel(str(exc), title="Scan Failed", border_style="red"))
        raise typer.Exit(code=1) from exc

    _render_scan_result(result)


@app.command()
def plan() -> None:
    """Generate an Azure App Service deployment plan."""
    try:
        project_info = scan_project()
        steps = generate_deployment_plan(project_info)
    except DetectionError as exc:
        console.print(Panel(str(exc), title="Plan Failed", border_style="red"))
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(Panel(str(exc), title="Plan Failed", border_style="red"))
        raise typer.Exit(code=1) from exc

    console.print(Panel(f"Project type: {project_info['project_type']}", title="Deployment Plan"))
    for index, step in enumerate(steps, start=1):
        console.print(f"{index}. {step['description']}")
        console.print(f"   [bold green]{step['command']}[/bold green]")


@app.command()
def deploy() -> None:
    """Deploy the current project to Azure App Service."""
    try:
        project_info = scan_project()
        steps = generate_deployment_plan(project_info)
        names = deployment_target_names()
        check_azure_login()
    except DetectionError as exc:
        console.print(Panel(str(exc), title="Deploy Failed", border_style="red"))
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(Panel(str(exc), title="Deploy Failed", border_style="red"))
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Azure Login Failed", border_style="red"))
        raise typer.Exit(code=1) from exc

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Running deployment steps", total=len(steps))
            for step in steps:
                progress.update(task_id, description=step["description"])
                run_az(step["command"])
                progress.advance(task_id)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Deployment Failed", border_style="red"))
        raise typer.Exit(code=1) from exc

    try:
        result = run_az(
            (
                f"az webapp show --resource-group {names['resource_group']} "
                f"--name {names['app_name']} --query defaultHostName -o tsv"
            ),
            skip_confirmation=True,
        )
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Deployment Succeeded, URL Lookup Failed", border_style="yellow"))
        raise typer.Exit(code=1) from exc

    host_name = result.stdout.strip()
    console.print(f"[green]Deployment complete:[/green] https://{host_name}")


@app.command()
def logs(
    tail: bool = typer.Option(True, "--tail/--no-tail", help="Stream logs live or fetch a recent slice."),
    lines: int = typer.Option(100, min=1, help="Number of recent lines to fetch when not tailing."),
    resource_group: str | None = typer.Option(None, help="Azure resource group name."),
    app_name: str | None = typer.Option(None, help="Azure Web App name."),
) -> None:
    """View Azure App Service logs."""
    names = deployment_target_names()
    resolved_resource_group = resource_group or names["resource_group"]
    resolved_app_name = app_name or names["app_name"]

    try:
        check_azure_login()
        if tail:
            console.print(
                f"[cyan]Tailing logs for {resolved_resource_group}/{resolved_app_name}...[/cyan]"
            )
            tail_logs(resolved_resource_group, resolved_app_name)
            return

        log_text = get_recent_logs(resolved_resource_group, resolved_app_name, lines=lines)
        console.print(
            Panel(
                log_text.rstrip() or "No log output returned.",
                title=f"Recent Logs ({lines} lines)",
                border_style="cyan",
            )
        )
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Logs Failed", border_style="red"))
        raise typer.Exit(code=1) from exc


@app.command()
def diagnose(
    lines: int = typer.Option(100, min=1, help="Number of recent Azure log lines to include."),
    resource_group: str | None = typer.Option(None, help="Azure resource group name."),
    app_name: str | None = typer.Option(None, help="Azure Web App name."),
) -> None:
    """Diagnose a deployment issue using recent Azure context and DeepSeek."""
    result = _collect_diagnosis(lines=lines, resource_group=resource_group, app_name=app_name)
    _render_diagnosis(result)


@app.command()
def fix(
    lines: int = typer.Option(100, min=1, help="Number of recent Azure log lines to include."),
    resource_group: str | None = typer.Option(None, help="Azure resource group name."),
    app_name: str | None = typer.Option(None, help="Azure Web App name."),
    yes: bool = typer.Option(False, "--yes", help="Apply selected fixes without per-fix confirmation."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display fixes without applying them."),
) -> None:
    """Diagnose the app, propose fixes, and optionally apply them."""
    diagnosis = _collect_diagnosis(lines=lines, resource_group=resource_group, app_name=app_name)
    _render_diagnosis(diagnosis)

    fixes = generate_fixes(diagnosis, Path.cwd())
    if not fixes:
        console.print(Panel("No actionable fixes were generated.", title="Fix", border_style="yellow"))
        raise typer.Exit(code=0)

    _render_proposed_fixes(fixes)

    if yes:
        selected_indices = list(range(len(fixes)))
    else:
        selection = Prompt.ask("Select fixes to apply", default="all")
        try:
            selected_indices = _parse_fix_selection(selection, len(fixes))
        except typer.BadParameter as exc:
            console.print(Panel(str(exc), title="Invalid Selection", border_style="red"))
            raise typer.Exit(code=1) from exc

    selected_fixes = [fixes[index] for index in selected_indices]
    if not selected_fixes:
        console.print(Panel("No fixes selected.", title="Fix", border_style="yellow"))
        raise typer.Exit(code=0)

    applied_any = False
    for fix_item in selected_fixes:
        _show_fix_preview(fix_item)
        if not dry_run and not yes and not _confirm_action("Apply this fix? [y/N]", default="n"):
            console.print("[yellow]Skipped.[/yellow]")
            continue
        try:
            _apply_fix(fix_item, dry_run=dry_run)
            applied_any = True
        except RuntimeError as exc:
            console.print(Panel(str(exc), title="Fix Failed", border_style="red"))
            raise typer.Exit(code=1) from exc

    if dry_run:
        console.print("[cyan]Dry run complete. No changes were applied.[/cyan]")
        raise typer.Exit(code=0)

    if applied_any and _confirm_action("Redeploy now? [y/N]", default="n"):
        deploy()


if __name__ == "__main__":
    azdeeploy()
