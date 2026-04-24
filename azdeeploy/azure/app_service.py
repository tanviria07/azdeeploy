"""Azure App Service helpers."""

from __future__ import annotations

from pathlib import Path


def app_service_plan_name(app_name: str) -> str:
    """Generate a predictable plan name."""
    return f"{app_name}-plan"


def _sanitize_name(value: str, max_length: int = 60) -> str:
    """Sanitize a value for Azure resource naming."""
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return (collapsed or "azdeeploy-app")[:max_length].strip("-") or "azdeeploy-app"


def _runtime_stack(project_type: str) -> str:
    """Map detected project types to App Service runtimes."""
    if project_type == "fastapi":
        return "PYTHON|3.11"
    if project_type == "express":
        return "NODE|20-lts"
    raise ValueError(f"Unsupported project type for App Service deployment: {project_type}")


def _read_env_azure(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a .env.azure file."""
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_vars[key.strip()] = value.strip()
    return env_vars


def deployment_target_names(root: Path | None = None) -> dict[str, str]:
    """Derive default Azure resource names from the current directory."""
    root = root or Path.cwd()
    base = _sanitize_name(root.name)
    app_name = base
    return {
        "resource_group": f"{base}-rg",
        "app_name": app_name,
        "plan_name": app_service_plan_name(app_name),
        "location": "eastus",
    }


def generate_deployment_plan(project_info: dict) -> list[dict[str, str]]:
    """Generate a concrete App Service deployment plan from scan output."""
    names = deployment_target_names()
    runtime = _runtime_stack(str(project_info["project_type"]))
    env_path = Path.cwd() / ".env.azure"
    env_vars = _read_env_azure(env_path)

    steps: list[dict[str, str]] = [
        {
            "description": "Ensure the resource group exists",
            "command": (
                f"az group create --name {names['resource_group']} "
                f"--location {names['location']}"
            ),
        },
        {
            "description": "Create the App Service plan",
            "command": (
                f"az appservice plan create --name {names['plan_name']} "
                f"--resource-group {names['resource_group']} --sku B1 --is-linux"
            ),
        },
        {
            "description": "Create the Web App",
            "command": (
                f"az webapp create --name {names['app_name']} "
                f"--resource-group {names['resource_group']} "
                f"--plan {names['plan_name']} --runtime \"{runtime}\""
            ),
        },
    ]

    startup_command = project_info.get("recommended_startup")
    if startup_command:
        steps.append(
            {
                "description": "Set the startup command",
                "command": (
                    f"az webapp config set --resource-group {names['resource_group']} "
                    f"--name {names['app_name']} --startup-file \"{startup_command}\""
                ),
            }
        )

    if env_vars:
        settings = " ".join(f"{key}={value}" for key, value in env_vars.items())
        steps.append(
            {
                "description": "Set environment variables from .env.azure",
                "command": (
                    f"az webapp config appsettings set --resource-group {names['resource_group']} "
                    f"--name {names['app_name']} --settings {settings}"
                ),
            }
        )

    steps.extend(
        [
            {
                "description": "Deploy the current directory to App Service",
                "command": (
                    f"az webapp up --name {names['app_name']} "
                    f"--resource-group {names['resource_group']} --runtime \"{runtime}\""
                ),
            },
            {
                "description": "Enable application logging",
                "command": (
                    f"az webapp log config --resource-group {names['resource_group']} "
                    f"--name {names['app_name']} --application-logging filesystem "
                    f"--detailed-error-messages true"
                ),
            },
        ]
    )

    return steps
