"""Python project detection helpers."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path


def is_python_project(root: Path) -> bool:
    """Detect whether a directory looks like a Python project."""
    return any((root / marker).exists() for marker in ("pyproject.toml", "requirements.txt", "setup.py"))


def _read_dependency_text(root: Path) -> tuple[str, list[str]]:
    """Collect dependency declarations from common Python packaging files."""
    issues: list[str] = []
    chunks: list[str] = []

    requirements_path = root / "requirements.txt"
    pyproject_path = root / "pyproject.toml"
    setup_path = root / "setup.py"

    if requirements_path.exists():
        chunks.append(requirements_path.read_text(encoding="utf-8", errors="ignore"))
    else:
        issues.append("Missing requirements.txt")

    if pyproject_path.exists():
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            project_deps = data.get("project", {}).get("dependencies", [])
            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            chunks.extend(project_deps)
            chunks.extend(str(name) for name in poetry_deps.keys())
        except tomllib.TOMLDecodeError:
            issues.append("Unable to parse pyproject.toml")
    else:
        issues.append("Missing pyproject.toml")

    if setup_path.exists():
        chunks.append(setup_path.read_text(encoding="utf-8", errors="ignore"))
    else:
        issues.append("Missing setup.py")

    return "\n".join(chunks).lower(), issues


def _find_main_file(root: Path) -> Path | None:
    """Find a likely FastAPI entry file."""
    for name in ("main.py", "app.py", "run.py", "api.py"):
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _find_fastapi_app_object(main_file: Path) -> str | None:
    """Parse a module to find a common FastAPI application variable."""
    source = main_file.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=str(main_file))
    candidates = ("app", "api", "application")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue

        func = node.value.func
        is_fastapi_ctor = False
        if isinstance(func, ast.Name) and func.id == "FastAPI":
            is_fastapi_ctor = True
        if isinstance(func, ast.Attribute) and func.attr == "FastAPI":
            is_fastapi_ctor = True
        if not is_fastapi_ctor:
            continue

        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in candidates:
                return target.id

    return None


def scan_python(root: Path | None = None) -> dict[str, object]:
    """Scan the current directory for a FastAPI-style Python project."""
    root = root or Path.cwd()
    dependency_text, issues = _read_dependency_text(root)

    if "fastapi" not in dependency_text:
        issues.append("fastapi dependency not found")
    if "uvicorn" not in dependency_text:
        issues.append("uvicorn dependency not found")

    main_file = _find_main_file(root)
    if main_file is None:
        raise ValueError(
            "Could not find a Python entry file. Expected one of: main.py, app.py, run.py, api.py."
        )

    try:
        app_object = _find_fastapi_app_object(main_file)
    except SyntaxError as exc:
        raise ValueError(f"Could not parse {main_file.name}: {exc.msg}.") from exc

    if app_object is None:
        raise ValueError(
            f"Could not find a FastAPI app object in {main_file.name}. "
            "Looked for app, api, or application = FastAPI(...)."
        )

    filename_no_ext = main_file.stem
    startup = f"uvicorn {filename_no_ext}:{app_object} --host 0.0.0.0 --port 8000"

    return {
        "project_type": "fastapi",
        "main_file": main_file.name,
        "app_object": app_object,
        "recommended_startup": startup,
        "potential_issues": issues,
    }
