"""Workflow state definition for the LangGraph testing pipeline.

This module defines the shared state that flows through the workflow nodes.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowState(BaseModel):
    """State shared across all nodes in the LangGraph workflow.

    Each node reads from and writes to this state as the workflow progresses
    through: requirement -> test_case -> generated_test -> execution_result.
    """
    # Input
    requirement: str = Field(..., description="Natural language requirement to test")
    test_scenarios: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of test scenarios generated from the requirement"
    )
    test_cases: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of test cases generated from the test scenarios"
    )

    # After RequirementToTestCase node
    test_case: Optional[Dict[str, Any]] = Field(
        default=None, description="Generated test case (TestCase as dict)"
    )

    # After TestAutomationAgent node
    generated_test_path: Optional[str] = Field(
        default=None, description="File path of the generated Selenium test"
    )
    generated_test_code: Optional[str] = Field(
        default=None, description="Source code of the generated test"
    )

    # After ExecutionService node
    execution_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Execution result dict (status, duration, exception, ...)",
    )

    # After FailureInvestigationAgent node (only populated on test failure)
    failure_analysis: Optional[Dict[str, Any]] = Field(
        default=None, description="Failure analysis from FailureInvestigationAgent (FailureAnalysis as dict)",
    )

    # After VerificationAgent node (only populated on test failure)
    verification_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Verification result from VerificationAgent (VerificationResult as dict)",
    )

    # After BugReportAgent node (only populated on test failure)
    bug_report: Optional[Dict[str, Any]] = Field(
        default=None, description="Generated bug report from BugReportAgent"
    )

    # After RegressionTestAgent node (only populated on test failure)
    regression_test: Optional[Dict[str, Any]] = Field(
        default=None, description="Generated regression test from RegressionTestAgent (RegressionTestCase as dict)",
    )

    # Human-in-the-Loop approval fields (only populated on test failure)
    human_approval_required: bool = Field(
        default=False, description="Whether human approval is required for bug report and regression test"
    )
    bug_report_approved: Optional[bool] = Field(
        default=None, description="Whether the bug report has been approved by a human"
    )
    regression_test_approved: Optional[bool] = Field(
        default=None, description="Whether the regression test has been approved by a human"
    )

    # Retrieved knowledge from KnowledgeRetriever (only populated on test failure)
    retrieved_knowledge: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Retrieved knowledge chunks from KnowledgeRetriever"
    )

    # Errors captured at any stage
    errors: List[str] = Field(default_factory=list, description="Errors encountered during workflow")