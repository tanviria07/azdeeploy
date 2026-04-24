"""Project type detection helpers."""

from __future__ import annotations

from pathlib import Path

from azdeeploy.scanner.detect_node import is_node_project, scan_node
from azdeeploy.scanner.detect_python import is_python_project, scan_python


class DetectionError(RuntimeError):
    """Raised when project detection fails."""


def detect_project_type(root: Path) -> str:
    """Return a coarse project type based on common marker files."""
    if is_python_project(root):
        return "python"
    if is_node_project(root):
        return "node"
    return "unknown"


def scan_project(root: Path | None = None) -> dict[str, object]:
    """Scan the current directory and return unified project metadata."""
    root = root or Path.cwd()
    project_type = detect_project_type(root)

    try:
        if project_type == "python":
            return scan_python(root)
        if project_type == "node":
            return scan_node(root)
    except ValueError as exc:
        raise DetectionError(str(exc)) from exc

    raise DetectionError(
        "Could not detect a supported project in the current directory. "
        "Expected Python markers like pyproject.toml/requirements.txt/setup.py "
        "or Node markers like package.json."
    )
