from pydantic import BaseModel, Field
from typing import List, Literal


class RegressionTestCase(BaseModel):
    """Schema for a regression test case generated from a requirement and existing test artifacts."""
    test_id: str = Field(..., description="Unique identifier for the test case")
    title: str = Field(..., description="Short title summarizing the test case")
    description: str = Field(..., description="Detailed description of what the test covers")
    steps: List[str] = Field(..., description="Ordered steps to execute the test")
    expected_result: str = Field(..., description="Expected outcome after executing the steps")
    priority: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Priority of the test case"
    )
    # Optional fields from the original TestCase schema, not required in output but kept for compatibility
    preconditions: List[str] = Field(default_factory=list, description="Conditions that must be met before executing the test")
    test_type: Literal["functional", "non-functional", "unit", "integration", "ui", "api", "regression"] = Field(
        default="regression", description="Type of test"
    )