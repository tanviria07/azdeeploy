"""Patch parsing helpers."""


def looks_like_unified_diff(text: str) -> bool:
    """Return whether the text resembles a unified diff."""
    return "--- " in text and "+++ " in text
