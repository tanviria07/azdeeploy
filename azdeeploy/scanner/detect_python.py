"""Python project detection helpers."""

from pathlib import Path


def is_python_project(root: Path) -> bool:
    """Detect whether a directory looks like a Python project."""
    return any((root / marker).exists() for marker in ("pyproject.toml", "requirements.txt", "setup.py"))
