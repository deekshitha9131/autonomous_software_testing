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
        # New parameters for Phase 8
        test_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        base_url: Optional[str] = None,
        sut_id: Optional[str] = None,
        sut_context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify whether a failure analysis is consistent with the evidence.

        Args:
            requirement: The original natural language requirement.
            test_case: The test case that was executed.
            generated_test_code: The Selenium test code that failed.
            execution_result: Raw execution result (status, exception, screenshot, duration).
            failure_analysis: The FailureAnalysis dict from the investigation agent.
            test_id: Identifier of the test case.
            scenario_id: Identifier of the scenario.
            base_url: Base URL of the System Under Test.
            sut_id: Identifier for the System Under Test.
            sut_context: Additional context about the System Under Test.

        Returns:
            A VerificationResult with the verdict.
        """
        test_case_str = json.dumps(test_case, indent=2)
        execution_str = json.dumps(execution_result, indent=2)
        analysis_str = json.dumps(failure_analysis, indent=2)

        # Build the prompt with clear separation of observed evidence and supporting context
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

## Observed Evidence (Execution Result):
{execution_str}

Interpret browser_evidence as observations from the live browser. Selenium .text is visible text and may contain decoded characters even when innerHTML is safely escaped. An assertion mismatch alone does not prove an application defect. For script-injection checks, use visible_text, innerHTML, and script_alerts together; absence of a recorded alert does not by itself prove safe rendering.

## Failure Analysis (to verify):
{analysis_str}

## Supporting Context:
"""
        if test_id:
            prompt += f"### Test ID: {test_id}\n"
        if scenario_id:
            prompt += f"### Scenario ID: {scenario_id}\n"
        if base_url:
            prompt += f"### Base URL: {base_url}\n"
        if sut_id:
            prompt += f"### SUT ID: {sut_id}\n"
        if sut_context:
            prompt += f"### SUT Context: {json.dumps(sut_context, indent=2)}\n"

        prompt += """
Based on the above, determine:
1. Does the failure analysis correctly identify the root cause based on the evidence?
2. Are there any gaps in the evidence?
3. What is the recommended next action?
Do not confirm a root cause that is not directly supported by execution evidence. If the failure may be caused by an incorrect expected result or generated test, identify that possibility and return "unconfirmed" or "inconclusive".

Return your verdict as one of: "confirmed" (analysis matches evidence), "unconfirmed" (analysis contradicts evidence), or "inconclusive" (insufficient evidence to decide).
"""

        return self.llm_client.generate_structured(prompt, VerificationResult)