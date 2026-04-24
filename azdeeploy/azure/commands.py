"""Common Azure CLI command builders."""


def webapp_show(resource_group: str, app_name: str) -> list[str]:
    """Build a command for inspecting an Azure Web App."""
    return ["az", "webapp", "show", "--resource-group", resource_group, "--name", app_name]
