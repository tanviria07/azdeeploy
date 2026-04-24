"""Pydantic schemas for LLM interactions."""

from pydantic import BaseModel, Field


class DiagnosisResult(BaseModel):
    """Structured diagnosis result."""

    summary: str = Field(description="Short problem summary.")
    root_cause: str = Field(description="Most likely root cause.")
    next_steps: list[str] = Field(default_factory=list, description="Recommended next actions.")
