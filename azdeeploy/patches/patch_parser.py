"""Patch parsing helpers."""

from __future__ import annotations

from pathlib import Path

from azdeeploy.azure.app_service import deployment_target_names
from azdeeploy.llm.schemas import Diagnosis
from azdeeploy.scanner.detect_project import DetectionError, scan_project


def looks_like_unified_diff(text: str) -> bool:
    """Return whether the text resembles a unified diff."""
    return "--- " in text and "+++ " in text


def _is_python_project(project_dir: Path) -> bool:
    """Return whether the project directory looks like a Python project."""
    return any(
        (project_dir / marker).exists()
        for marker in ("pyproject.toml", "requirements.txt", "setup.py")
    )


def _read_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE pairs from a local env file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _extract_path(line: str) -> str:
    """Normalize a unified diff path line."""
    value = line[4:].strip()
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    return value


def _apply_unified_diff(diff_text: str, project_dir: Path) -> dict[str, str]:
    """Apply a unified diff to the local project files and return resulting writes."""
    lines = diff_text.splitlines()
    file_writes: dict[str, str] = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.startswith("--- "):
            index += 1
            continue

        old_path = _extract_path(line)
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            break

        new_path = _extract_path(lines[index])
        target_path = new_path if new_path != "/dev/null" else old_path
        index += 1

        if target_path == "/dev/null":
            continue

        source_path = project_dir / target_path
        original_lines = []
        if old_path != "/dev/null" and source_path.exists():
            original_lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()

        updated_lines: list[str] = []
        source_index = 0

        while index < len(lines):
            current = lines[index]
            if current.startswith("--- "):
                break
            if not current.startswith("@@"):
                index += 1
                continue

            header = current
            parts = header.split()
            old_start = int(parts[1].split(",")[0][1:]) if len(parts) > 1 else 1
            start_index = max(old_start - 1, 0)

            while source_index < start_index and source_index < len(original_lines):
                updated_lines.append(original_lines[source_index])
                source_index += 1

            index += 1
            while index < len(lines):
                hunk_line = lines[index]
                if hunk_line.startswith(("--- ", "@@")):
                    break
                if not hunk_line:
                    prefix = " "
                    content = ""
                else:
                    prefix = hunk_line[0]
                    content = hunk_line[1:]

                if prefix == " ":
                    if source_index < len(original_lines):
                        updated_lines.append(original_lines[source_index])
                    else:
                        updated_lines.append(content)
                    source_index += 1
                elif prefix == "-":
                    source_index += 1
                elif prefix == "+":
                    updated_lines.append(content)
                elif prefix == "\\":
                    pass
                index += 1

        while source_index < len(original_lines):
            updated_lines.append(original_lines[source_index])
            source_index += 1

        file_writes[str(source_path)] = "\n".join(updated_lines).rstrip("\n") + "\n"

    return file_writes


def _collect_text_parts(diagnosis: Diagnosis) -> list[str]:
    """Flatten diagnosis text into searchable fragments."""
    return [
        diagnosis.root_cause,
        diagnosis.recommended_fix,
        *diagnosis.evidence,
        *diagnosis.azure_commands,
        diagnosis.code_or_config_patch or "",
    ]


def generate_fixes(diagnosis: Diagnosis, project_dir: Path) -> list[dict]:
    """Generate fix objects from a structured diagnosis."""
    fixes: list[dict] = []
    text_parts = _collect_text_parts(diagnosis)
    normalized_text = "\n".join(text_parts).lower()
    names = deployment_target_names(project_dir)

    project_info: dict[str, object] = {}
    try:
        project_info = scan_project(project_dir)
    except DetectionError:
        project_info = {}

    if "missing requirements.txt" in normalized_text and _is_python_project(project_dir):
        fixes.append(
            {
                "description": "Create requirements.txt with FastAPI defaults",
                "type": "file_write",
                "commands_to_run": [],
                "file_writes": {
                    str(project_dir / "requirements.txt"): "fastapi\nuvicorn\n",
                },
                "is_safe": True,
            }
        )

    startup_commands = [
        cmd
        for cmd in diagnosis.azure_commands
        if cmd.strip().lower().startswith("az webapp config set")
        and "--startup-file" in cmd
    ]
    if not startup_commands and "startup command" in normalized_text and project_info.get("recommended_startup"):
        startup_commands = [
            (
                f"az webapp config set --resource-group {names['resource_group']} "
                f"--name {names['app_name']} --startup-file "
                f"\"{project_info['recommended_startup']}\""
            )
        ]
    if startup_commands:
        commands = startup_commands
        fixes.append(
            {
                "description": "Set the Azure Web App startup command",
                "type": "azure_command",
                "commands_to_run": commands,
                "file_writes": {},
                "is_safe": True,
            }
        )

    env_commands = [
        cmd
        for cmd in diagnosis.azure_commands
        if cmd.strip().lower().startswith("az webapp config appsettings set")
    ]
    if not env_commands and (
        "missing env variable" in normalized_text or "missing environment variable" in normalized_text
    ):
        env_vars = _read_env_file(project_dir / ".env.azure")
        if env_vars:
            settings = " ".join(f"{key}={value}" for key, value in env_vars.items())
            env_commands = [
                (
                    f"az webapp config appsettings set --resource-group {names['resource_group']} "
                    f"--name {names['app_name']} --settings {settings}"
                )
            ]
    if env_commands:
        commands = env_commands
        fixes.append(
            {
                "description": "Set missing Azure Web App environment variables",
                "type": "azure_command",
                "commands_to_run": commands,
                "file_writes": {},
                "is_safe": True,
            }
        )

    if diagnosis.code_or_config_patch and looks_like_unified_diff(diagnosis.code_or_config_patch):
        file_writes = _apply_unified_diff(diagnosis.code_or_config_patch, project_dir)
        if file_writes:
            fixes.append(
                {
                    "description": "Apply the suggested code/config patch",
                    "type": "code_patch",
                    "commands_to_run": [],
                    "file_writes": file_writes,
                    "is_safe": False,
                }
            )

    deduped: list[dict] = []
    seen: set[tuple] = set()
    for fix in fixes:
        key = (
            fix["description"],
            tuple(fix["commands_to_run"]),
            tuple(sorted(fix["file_writes"].items())),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fix)
    return deduped
