"""Verification Agent: cross-checks failure analysis against execution evidence.

Takes the FailureAnalysis produced by the FailureInvestigationAgent and
validates it against the raw execution evidence (exception, screenshot,
test code, etc.) to produce a confirmed/unconfirmed/inconclusive verdict.
"""
import json
from typing import Any, Dict, List, Optional

from app.llm.client import LLMClient
from .schema import VerificationResult


class VerificationAgent:
    def __init__(self, llm_client: LLMClient = None):
        """Initialize the verification agent.

        Args:
            llm_client: An instance of LLMClient. If None, defaults to OpenAIClient.
        """
        if llm_client is None:
            from app.llm.client import OpenAIClient
            llm_client = OpenAIClient()
        self.llm_client = llm_client

    def verify(
        self,
        requirement: str,
        test_case: dict,
        generated_test_code: str,
        execution_result: Dict[str, Any],
        failure_analysis: Dict[str, Any],
    ) -> VerificationResult:
        """Verify whether a failure analysis is consistent with the evidence.

        Args:
            requirement: The original natural language requirement.
            test_case: The test case that was executed.
            generated_test_code: The Selenium test code that failed.
            execution_result: Raw execution result (status, exception, screenshot, duration).
            failure_analysis: The FailureAnalysis dict from the investigation agent.

        Returns:
            A VerificationResult with the verdict.
        """
        test_case_str = json.dumps(test_case, indent=2)
        execution_str = json.dumps(execution_result, indent=2)
        analysis_str = json.dumps(failure_analysis, indent=2)

        prompt = f"""
You are a senior QA verification engineer. Your job is to independently verify whether a failure analysis is correct and consistent with the raw evidence.

## Requirement:
{requirement}

## Test Case:
{test_case_str}

## Generated Test Code:
```python
{generated_test_code}
```

## Raw Execution Result:
{execution_str}

## Failure Analysis (to verify):
{analysis_str}

Based on the above, determine:
1. Does the failure analysis correctly identify the root cause based on the evidence?
2. Are there any gaps in the evidence?
3. What is the recommended next action?

Return your verdict as one of: "confirmed" (analysis matches evidence), "unconfirmed" (analysis contradicts evidence), or "inconclusive" (insufficient evidence to decide).
"""
        return self.llm_client.generate_structured(prompt, VerificationResult)
