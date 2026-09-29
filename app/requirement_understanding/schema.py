from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class RequirementUnderstanding(BaseModel):
    """Structured understanding of a natural language requirement."""
    feature: str = Field(..., description="The feature or capability being described")
    objective: str = Field(..., description="The goal or objective of the requirement")
    actors: List[str] = Field(
        default_factory=list, description="Actors or users involved in the requirement"
    )
    inputs: List[str] = Field(
        default_factory=list, description="Inputs or data required"
    )
    preconditions: List[str] = Field(
        default_factory=list, description="Conditions that must be met before the requirement can be fulfilled"
    )
    expected_behavior: str = Field(..., description="Expected behavior when the requirement is fulfilled")
    constraints: List[str] = Field(
        default_factory=list, description="Constraints or limitations on the requirement"
    )
    ambiguities: List[str] = Field(
        default_factory=list, description="Ambiguities or unclear aspects of the requirement"
    )
    status: Literal["testable", "clarification_needed", "unsupported"] = Field(
        ..., description="Whether the requirement is suitable for test generation"
    )
    clarification_reason: Optional[str] = Field(
        default=None, description="Reason why clarification is needed (when status is clarification_needed)"
    )