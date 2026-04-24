"""Azure App Service helpers."""


def app_service_plan_name(app_name: str) -> str:
    """Generate a predictable placeholder plan name."""
    return f"{app_name}-plan"
