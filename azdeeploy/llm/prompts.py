"""Prompt helpers for diagnosis and remediation."""

from __future__ import annotations

import json
import re


SYSTEM_PROMPT = (
    "You are an Azure App Service deployment expert. Analyze the following "
    "deployment information, error logs, and project details. Respond in valid "
    "JSON only, matching the field structure specified. Do not include any text "
    "outside the JSON."
)


def _trim_text(value: str, max_chars: int) -> str:
    """Trim long text sections to stay within budget."""
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}\n...[truncated]..."


def build_diagnosis_messages(context: dict) -> list[dict[str, str]]:
    """Build a compact message list for structured deployment diagnosis."""
    payload = {
        "project_scan": context.get("project_scan", {}),
        "deployment_plan_steps_attempted": context.get("deployment_plan_steps_attempted", []),
        "error_output": _trim_text(context.get("error_output", "") or "", 4000),
        "log_excerpt": _trim_text(context.get("log_excerpt", "") or "", 5000),
        "key_files": {
            path: _trim_text(text, 3000)
            for path, text in (context.get("key_files", {}) or {}).items()
        },
    }

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, indent=2),
        },
    ]


def parse_diagnosis_response(text: str) -> dict:
    """Extract the first JSON object from a model response."""
    match = re.search(r"\{.*", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")

    candidate = match.group(0)
    decoder = json.JSONDecoder()
    parsed, _ = decoder.raw_decode(candidate)
    return parsed
