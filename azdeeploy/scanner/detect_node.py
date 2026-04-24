"""Node.js project detection helpers."""

from __future__ import annotations

import json
from pathlib import Path


def is_node_project(root: Path) -> bool:
    """Detect whether a directory looks like a Node.js project."""
    return any((root / marker).exists() for marker in ("package.json", "pnpm-lock.yaml", "yarn.lock"))


def scan_node(root: Path | None = None) -> dict[str, object]:
    """Scan the current directory for an Express-style Node project."""
    root = root or Path.cwd()
    package_json_path = root / "package.json"
    if not package_json_path.exists():
        raise ValueError("Could not find package.json in the current directory.")

    try:
        package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse package.json: {exc.msg}.") from exc

    issues: list[str] = []
    dependencies = package_data.get("dependencies", {})
    if "express" not in dependencies:
        issues.append("express dependency not found")

    entry_file = package_data.get("main")
    if not entry_file:
        for candidate in ("server.js", "app.js"):
            if (root / candidate).exists():
                entry_file = candidate
                break

    if not entry_file:
        raise ValueError(
            "Could not determine a Node entry file. Set package.json main or add server.js/app.js."
        )

    if not (root / entry_file).exists():
        issues.append(f"Entry file {entry_file} does not exist")

    return {
        "project_type": "express",
        "entry_file": entry_file,
        "main_file": entry_file,
        "recommended_startup": f"node {entry_file}",
        "potential_issues": issues,
    }
