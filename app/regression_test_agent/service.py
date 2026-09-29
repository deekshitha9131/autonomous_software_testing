from typing import Any, Dict, Optional

from app.llm.client import LLMClient
from .schema import RegressionTestCase


class RegressionTestAgent:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize the regression test agent.

        Args:
            llm_client: An instance of LLMClient. If None, defaults to OpenAIClient.
        """
        if llm_client is None:
            from app.llm.client import OpenAIClient
            llm_client = OpenAIClient()
        self.llm_client = llm_client

    def generate(
        self,
        requirement: str,
        test_case: Dict[str, Any],
        failure_analysis: Optional[Dict[str, Any]] = None,
        verification_result: Optional[Dict[str, Any]] = None,
    ) -> RegressionTestCase:
        """Generate a regression test case based on the failed test case and failure analysis.

        The regression test is a variant of the original test case that helps prevent
        regression of the specific defect that was found.

        Args:
            requirement: The original natural language requirement.
            test_case: The test case object (as dict) that failed.
            failure_analysis: The failure analysis from the FailureInvestigationAgent (if any).
            verification_result: The verification result from the VerificationAgent (if any).

        Returns:
            A RegressionTestCase instance.
        """
        # Use the failed test case as base
        base_test_id = test_case.get("test_id", "unknown")
        base_title = test_case.get("title", "")
        base_description = test_case.get("description", "")
        base_steps = test_case.get("steps", [])
        base_expected_result = test_case.get("expected_result", "")
        base_preconditions = test_case.get("preconditions", [])
        base_priority = test_case.get("priority", "medium")

        # Generate regression test identifiers
        regression_test_id = f"REG_{base_test_id}"
        regression_title = f"Regression test for: {base_title}"
        regression_description = (
            f"Regression test to ensure the fix for the defect remains effective. "
            f"Original test case: {base_title}. "
            f"Failure analysis: {failure_analysis.get('failure_summary', 'N/A') if failure_analysis else 'N/A'}"
        )
        # Steps: we can keep the original steps, but optionally add verification steps based on root cause.
        # For simplicity, we keep the original steps.
        regression_steps = base_steps.copy()
        regression_expected_result = base_expected_result
        regression_preconditions = base_preconditions.copy()
        regression_priority = "high"  # regression tests are often high priority

        return RegressionTestCase(
            test_id=regression_test_id,
            title=regression_title,
            description=regression_description,
            steps=regression_steps,
            expected_result=regression_expected_result,
            priority=regression_priority,
            preconditions=regression_preconditions,
            test_type="regression",
        )