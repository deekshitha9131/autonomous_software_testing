from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class FailureAnalysis(BaseModel):
    """Structured analysis of a test failure."""
    failure_summary: str = Field(..., description="Brief summary of the failure")
    probable_root_cause: str = Field(..., description="Most likely root cause based on evidence")
    evidence: List[str] = Field(
        default_factory=list, description="Observed facts from the failure (logs, screenshots, etc.)"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Severity of the failure"
    )
    suggested_owner: str = Field(
        ..., description="Suggested team or person to investigate (e.g., 'frontend-team', 'backend-dev')"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the analysis (0.0 to 1.0)"
    )
