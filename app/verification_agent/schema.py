from pydantic import BaseModel, Field
from typing import List, Literal


class VerificationResult(BaseModel):
    """Structured result of verifying a failure analysis against evidence."""
    verdict: Literal["confirmed", "unconfirmed", "inconclusive"] = Field(
        ..., description="Whether the failure analysis is confirmed by the evidence"
    )
    reasoning: str = Field(
        ..., description="Explanation of how the verdict was reached"
    )
    evidence_gaps: List[str] = Field(
        default_factory=list, description="Missing evidence that would strengthen the analysis"
    )
    recommended_action: str = Field(
        ..., description="Suggested next step (e.g., 'fix redirect', 'add more tests', 'needs manual review')"
    )
