"""Safety checks for Azure operations."""


def confirm_target(resource_group: str, app_name: str) -> str:
    """Return a human-readable deployment target summary."""
    return f"{resource_group}/{app_name}"
