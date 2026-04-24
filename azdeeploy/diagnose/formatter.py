"""Output formatting helpers for diagnostics."""

from azdeeploy.llm.schemas import DiagnosisResult


def format_diagnosis(result: DiagnosisResult) -> str:
    """Format a diagnosis result for terminal output."""
    steps = "\n".join(f"- {step}" for step in result.next_steps) or "- No next steps provided."
    return f"Summary: {result.summary}\nRoot cause: {result.root_cause}\nNext steps:\n{steps}"
