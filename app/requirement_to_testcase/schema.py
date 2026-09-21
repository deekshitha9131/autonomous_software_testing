from pydantic import BaseModel, Field
from typing import List, Literal


class TestCase(BaseModel):
    """Schema for a generated test case from a natural language requirement."""
    test_id: str = Field(..., description="Unique identifier for the test case")
    title: str = Field(..., description="Short title summarizing the test case")
    description: str = Field(..., description="Detailed description of what the test covers")
    preconditions: List[str] = Field(
        default_factory=list, description="Conditions that must be met before executing the test"
    )
    steps: List[str] = Field(..., description="Ordered steps to execute the test")
    expected_result: str = Field(..., description="Expected outcome after executing the steps")
    test_type: Literal["functional", "non-functional", "unit", "integration", "ui", "api"] = Field(
        ..., description="Type of test"
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Priority of the test case"
    )
