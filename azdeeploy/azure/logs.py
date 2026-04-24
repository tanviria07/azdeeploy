"""Azure log helper functions."""

from __future__ import annotations

from azdeeploy.azure.commands import run_az


def tail_logs(resource_group: str, app_name: str) -> None:
    """Stream App Service logs directly to the terminal."""
    run_az(
        f"az webapp log tail --resource-group {resource_group} --name {app_name}",
        skip_confirmation=True,
        stream_output=True,
    )


def get_recent_logs(resource_group: str, app_name: str, lines: int = 100) -> str:
    """Fetch a recent slice of App Service logs."""
    result = run_az(
        f"az webapp log tail --resource-group {resource_group} --name {app_name} --lines {lines}",
        skip_confirmation=True,
    )
    return result.stdout
