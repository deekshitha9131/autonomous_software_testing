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
    base_url: Optional[str] = Field(
        default=None, description="Base URL of the System Under Test"
    )
    sut_id: Optional[str] = Field(
        default=None, description="Identifier for the System Under Test"
    )
    sut_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context about the System Under Test"
    )
    test_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Test data to be used during test execution"
    )
    # Requirement Understanding
    requirement_understanding: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured understanding of the requirement"
    )
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
        default=None, description="Aggregate execution result for all generated tests",
    )
    primary_execution_result: Optional[Dict[str, Any]] = Field(
        default=None, description="First individual execution result for compatibility",
    )

    # Individual execution results for all generated Selenium tests
    execution_results: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of execution result dicts for each generated test"
    )

    # Aggregate execution summary
    execution_summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Aggregate summary of execution results (total, passed, failed)"
    )

    # Generated Selenium code for all test cases (only populated after generating Selenium for test cases)
    generated_test_codes: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of generated Selenium test code dicts (test_id and code)"
    )

    # After FailureInvestigationAgent node (only populated on test failure)
    failure_analysis: Optional[Dict[str, Any]] = Field(
        default=None, description="Failure analysis from FailureInvestigationAgent (FailureAnalysis as dict)"
    )
    # Per-test failure analyses
    failure_analyses: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of failure analyses for each failed/error test"
    )

    # After VerificationAgent node (only populated on test failure)
    verification_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Verification result from VerificationAgent (VerificationResult as dict)"
    )
    # Per-test verification results
    verification_results: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of verification results for each failure analysis"
    )

    # After BugReportAgent node (only populated on test failure)
    bug_report: Optional[Dict[str, Any]] = Field(
        default=None, description="Generated bug report from BugReportAgent"
    )

    # After RegressionTestAgent node (only populated on test failure)
    regression_test: Optional[Dict[str, Any]] = Field(
        default=None, description="Generated regression test from RegressionTestAgent (RegressionTestCase as dict)"
    )
    # After regression test execution (only populated after executing approved regression test)
    regression_execution_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Execution result of the approved regression test"
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

    # Missing context flag (for Phase 6)
    missing_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured missing context result when SUT context is insufficient"
    )

    # Per-failure bug reports (for Phase 9)
    bug_reports: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of generated bug reports"
    )
    # Per-failure regression tests (for Phase 9)
    regression_tests: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of generated regression test cases"
    )