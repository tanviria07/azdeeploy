"""DeepSeek-backed deployment diagnosis helpers."""

from __future__ import annotations

from openai import OpenAI

from azdeeploy.config import load_config
from azdeeploy.llm.prompts import build_diagnosis_messages, parse_diagnosis_response
from azdeeploy.llm.schemas import Diagnosis


def diagnose(context: dict) -> Diagnosis:
    """Run a structured deployment diagnosis against DeepSeek."""
    settings = load_config()
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=build_diagnosis_messages(context),
        stream=False,
    )
    text = response.choices[0].message.content or ""

    try:
        payload = parse_diagnosis_response(text)
        return Diagnosis.model_validate(payload)
    except Exception:
        return Diagnosis(
            root_cause="Model returned non-JSON diagnosis output.",
            confidence="low",
            evidence=[text.strip() or "No response body returned by the model."],
            recommended_fix="Review the raw diagnosis text and retry with more deployment context.",
            azure_commands=[],
            code_or_config_patch=None,
            risk_level="medium",
        )
