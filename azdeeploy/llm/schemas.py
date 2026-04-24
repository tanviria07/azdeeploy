"""Pydantic schemas for LLM interactions."""

from typing import Optional

from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    """Structured deployment diagnosis."""

    root_cause: str
    confidence: str
    evidence: list[str] = Field(default_factory=list)
    recommended_fix: str
    azure_commands: list[str] = Field(default_factory=list)
    code_or_config_patch: Optional[str] = None
    risk_level: str
