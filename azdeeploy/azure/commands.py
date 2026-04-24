"""Safe Azure CLI command helpers."""

from __future__ import annotations

import json
import shlex
import subprocess

from rich.console import Console

console = Console()

ALLOWED_READONLY = {
    "az account show",
    "az group show",
    "az webapp show",
    "az webapp config appsettings list",
    "az webapp log tail",
    "az webapp deployment list-publishing-profiles",
}

REQUIRES_CONFIRMATION = {
    "az group create",
    "az appservice plan create",
    "az webapp create",
    "az webapp up",
    "az webapp deploy",
    "az webapp config set",
    "az webapp config appsettings set",
    "az webapp log config",
}

BLOCKED = {
    "az group delete",
    "az webapp delete",
    "az resource delete",
    "az appservice plan delete",
}


def _normalize_command(cmd: str) -> str:
    """Collapse command whitespace for stable prefix matching."""
    return " ".join(cmd.strip().lower().split())


def _matches_prefix(cmd: str, prefixes: set[str]) -> bool:
    """Return whether the command begins with any known prefix."""
    normalized = _normalize_command(cmd)
    return any(normalized.startswith(prefix) for prefix in prefixes)


def run_az(
    cmd: str,
    skip_confirmation: bool = False,
    stream_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a guarded Azure CLI command."""
    if _matches_prefix(cmd, BLOCKED):
        raise RuntimeError(f"Blocked Azure command: {cmd}")

    if _matches_prefix(cmd, REQUIRES_CONFIRMATION) and not skip_confirmation:
        response = console.input("This may incur Azure costs. Continue? [y/N] ").strip().lower()
        if response != "y":
            raise RuntimeError("Azure command cancelled by user.")

    result = subprocess.run(
        shlex.split(cmd),
        capture_output=not stream_output,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        error = stderr or stdout or "Unknown Azure CLI error."
        raise RuntimeError(f"Azure command failed: {cmd}\n{error}")
    return result


def check_azure_login() -> subprocess.CompletedProcess[str]:
    """Verify Azure CLI login and print the active subscription."""
    result = run_az("az account show", skip_confirmation=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Could not parse Azure account information.") from exc

    subscription_name = payload.get("name", "Unknown subscription")
    console.print(f"[green]Azure subscription:[/green] {subscription_name}")
    return result


def webapp_show(resource_group: str, app_name: str) -> list[str]:
    """Build a command for inspecting an Azure Web App."""
    return ["az", "webapp", "show", "--resource-group", resource_group, "--name", app_name]
