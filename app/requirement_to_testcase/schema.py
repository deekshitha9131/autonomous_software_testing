from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Any, Optional


class TestDataItem(BaseModel):
    """A single key-value pair for test data."""
    key: str = Field(..., description="Data key identifier")
    value: Any = Field(..., description="Data value associated with the key")


class TestCase(BaseModel):
    """Schema for a generated test case from a natural language requirement."""
    test_id: str = Field(..., description="Unique identifier for the test case")
    scenario_id: str = Field(..., description="Identifier of the source test scenario")
    route: Optional[str] = Field(
        default=None, description="Implemented SUT route this test case exercises"
    )
    title: str = Field(..., description="Short title summarizing the test case")
    description: str = Field(..., description="Detailed description of what the test covers")
    preconditions: List[str] = Field(
        default_factory=list, description="Conditions that must be met before executing the test"
    )
    steps: List[str] = Field(..., description="Ordered steps to execute the test")
    test_data: List[TestDataItem] = Field(
        default_factory=list, description="Test data needed for executing the test as key-value pairs"
    )
    expected_result: str = Field(..., description="Expected outcome after executing the steps")
    test_type: Literal["functional", "non-functional", "unit", "integration", "ui", "api", "negative", "boundary"] = Field(
        ..., description="Type of test"
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Priority of the test case"
    )