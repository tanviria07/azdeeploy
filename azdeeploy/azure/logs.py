"""Azure log helper functions."""


def tail_logs_command(resource_group: str, app_name: str) -> list[str]:
    """Build a command for log streaming."""
    return ["az", "webapp", "log", "tail", "--resource-group", resource_group, "--name", app_name]
