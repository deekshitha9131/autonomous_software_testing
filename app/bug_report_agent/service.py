"""Bug Report Agent for generating bug reports from workflow state."""

from typing import Dict, Any, Optional
from app.llm.client import LLMClient


class BugReportAgent:
    """Agent that generates a bug report from workflow state."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def generate(
        self,
        requirement: str,
        test_case: Optional[Dict[str, Any]],
        execution_result: Optional[Dict[str, Any]],
        failure_analysis: Optional[Dict[str, Any]],
        verification_result: Optional[Dict[str, Any]],
        retrieved_knowledge: Optional[list],
    ) -> Dict[str, Any]:
        """Generate a bug report from the provided state.

        Returns a dictionary representing the bug report.
        """
        # For now, we'll create a simple bug report by combining the inputs.
        # In a real implementation, we might use the LLM to generate a formatted report.
        bug_report = {
            "requirement": requirement,
            "test_case": test_case,
            "execution_result": execution_result,
            "failure_analysis": failure_analysis,
            "verification_result": verification_result,
            "retrieved_knowledge": retrieved_knowledge or [],
            "summary": "Bug report generated from test failure.",
        }
        return bug_report