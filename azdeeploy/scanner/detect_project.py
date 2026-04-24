"""Project type detection helpers."""

from pathlib import Path


def detect_project_type(root: Path) -> str:
    """Return a coarse project type based on common marker files."""
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return "python"
    if (root / "package.json").exists():
        return "node"
    return "unknown"
