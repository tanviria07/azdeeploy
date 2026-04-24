"""Node.js project detection helpers."""

from pathlib import Path


def is_node_project(root: Path) -> bool:
    """Detect whether a directory looks like a Node.js project."""
    return any((root / marker).exists() for marker in ("package.json", "pnpm-lock.yaml", "yarn.lock"))
