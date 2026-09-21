import json
from typing import Any, Dict, List, Optional

from app.llm.client import LLMClient
from .schema import FailureAnalysis


class FailureInvestigationAgent:
    def __init__(self, llm_client: LLMClient = None):
        """Initialize the failure investigation agent.

        Args:
            llm_client: An instance of LLMClient. If None, defaults to OpenAIClient.
        """
        if llm_client is None:
            from app.llm.client import OpenAIClient
            llm_client = OpenAIClient()
        self.llm_client = llm_client

    def investigate(
        self,
        requirement: str,
        test_case: dict,  # We'll accept a dict for simplicity, but could be TestCase instance
        generated_test_code: str,
        exception: Dict[str, Any],
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        execution_metadata: Optional[Dict[str, Any]] = None,
    ) -> FailureAnalysis:
        """Investigate a test failure and return a structured analysis.

        Args:
            requirement: The original natural language requirement.
            test_case: The test case object (as dict or TestCase instance).
            generated_test_code: The Selenium test code that was generated and failed.
            exception: Dictionary containing exception details (type, message, traceback).
            stdout: Standard output from the test execution (if any).
            stderr: Standard error from the test execution (if any).
            screenshot_path: Path to screenshot taken on failure (if any).
            execution_metadata: Additional metadata (e.g., execution duration).

        Returns:
            A FailureAnalysis instance with the investigation results.
        """
        # Convert test_case to string representation if it's a TestCase instance
        if hasattr(test_case, 'dict'):
            test_case_str = test_case.json(indent=2)
        else:
            test_case_str = json.dumps(test_case, indent=2)

        # Format exception for the prompt
        exception_str = json.dumps(exception, indent=2)

        # Build the prompt
        prompt = f"""
You are an expert software test engineer and failure analyst. Analyze the following test failure and provide a structured root cause analysis.

## Requirement:
{requirement}

## Test Case:
{test_case_str}

## Generated Test Code:
```python
{generated_test_code}
```

## Exception Details:
{exception_str}

## Standard Output:
{stdout if stdout else "(empty)"}

## Standard Error:
{stderr if stderr else "(empty)"}

## Screenshot Path:
{screenshot_path if screenshot_path else "(none)"}

## Execution Metadata:
{json.dumps(execution_metadata, indent=2) if execution_metadata else "(none)"}

Based on the above information, provide a failure analysis in the following JSON format:
{{
  "failure_summary": "Brief summary of what failed",
  "probable_root_cause": "Most likely root cause based on the evidence",
  "evidence": [
    "List of specific observed facts from the failure (e.g., 'Exception: TimeoutException', 'Screenshot shows blank page', 'Error message: Element not found')"
  ],
  "severity": "one of: low, medium, high, critical",
  "suggested_owner": "Suggested team or person to investigate (e.g., 'frontend-team', 'backend-api', 'qa-engineer')",
  "confidence": 0.0  // float between 0.0 and 1.0
}}

Important guidelines:
1. Clearly distinguish evidence (facts) from inference (root cause, etc.).
2. Never claim certainty when evidence is insufficient - reflect this in the confidence field.
3. The evidence array should contain only observable facts, not interpretations.
4. Be concise but thorough in your analysis.
5. Return ONLY the JSON object, no additional text.
"""

        # Use the LLM client to generate the structured analysis
        return self.llm_client.generate_structured(prompt, FailureAnalysis)
