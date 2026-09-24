"""Deterministic LLM client for the login SUT.

When no OpenAI API key is available, this client provides pre-built responses
for the login demo SUT so the full LangGraph workflow can execute end-to-end
without an external LLM.

It implements the same LLMClient interface used by all agents.
"""
import json
import os
from typing import Type, TypeVar

from pydantic import BaseModel

from app.llm.client import LLMClient

T = TypeVar("T", bound=BaseModel)

# SUT configuration (read from env or use defaults matching demo_app)
SUT_BASE_URL = os.getenv("TEST_APP_URL", "http://127.0.0.1:8001")
SUT_USERNAME = os.getenv("DEMO_APP_USERNAME", "testuser")
SUT_PASSWORD = os.getenv("DEMO_APP_PASSWORD", "securepass")


class SUTAwareLLMClient(LLMClient):
    """Deterministic LLM client that returns SUT-aware responses.

    Maps known prompt patterns to correct structured outputs so the
    RequirementToTestCaseGenerator and TestAutomationAgent produce
    working Selenium code against the login SUT.
    """

    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """Return a deterministic response based on the prompt and schema."""
        schema_name = schema.__name__

        # --- RequirementToTestCaseGenerator asks for a TestCase ---
        if schema_name == "TestCase":
            return schema.model_validate(self._login_test_case())

        # --- TestAutomationAgent asks for a CodeLine (step → selenium) ---
        if schema_name == "CodeLine":
            code = self._step_to_code(prompt)
            return schema.model_validate({"code": code})

        # --- TestAutomationAgent asks for an AssertionLine ---
        if schema_name == "AssertionLine":
            assertion = self._expected_to_assertion(prompt)
            return schema.model_validate({"assertion": assertion})

        # --- FailureInvestigationAgent asks for a FailureAnalysis ---
        if schema_name == "FailureAnalysis":
            return schema.model_validate(self._failure_analysis(prompt))

        # --- VerificationAgent asks for a VerificationResult ---
        if schema_name == "VerificationResult":
            return schema.model_validate(self._verification_result(prompt))

        # --- Fallback: return a minimal valid instance ---
        # Build with defaults where possible
        raise ValueError(
            f"SUTAwareLLMClient: unhandled schema '{schema_name}'. "
            "Set OPENAI_API_KEY for full LLM support."
        )

    # ------------------------------------------------------------------
    # Pre-built responses
    # ------------------------------------------------------------------

    def _login_test_case(self) -> dict:
        """Return a TestCase dict for the login requirement."""
        return {
            "test_id": "login_valid_credentials",
            "title": "Login with valid credentials",
            "description": "Verify that a user can log in with valid credentials and is redirected to the dashboard.",
            "preconditions": [
                "The SUT is running at " + SUT_BASE_URL,
                "Valid credentials exist: username='" + SUT_USERNAME + "', password='" + SUT_PASSWORD + "'",
            ],
            "steps": [
                f"Navigate to {SUT_BASE_URL}/login",
                f"Enter '{SUT_USERNAME}' into the username field (id='username')",
                f"Enter '{SUT_PASSWORD}' into the password field (id='password')",
                "Click the login button (id='login_button')",
                "Wait for the page to redirect to the dashboard",
            ],
            "expected_result": "The user is redirected to the dashboard page with title 'Dashboard'",
            "test_type": "functional",
            "priority": "critical",
        }

    def _step_to_code(self, prompt: str) -> str:
        """Map a step description to a Selenium code line."""
        prompt_lower = prompt.lower()

        if "navigate" in prompt_lower and "login" in prompt_lower:
            return f'driver.get("{SUT_BASE_URL}/login")'

        if "username" in prompt_lower and "enter" in prompt_lower:
            return (
                f'driver.find_element(By.ID, "username").clear(); '
                f'driver.find_element(By.ID, "username").send_keys("{SUT_USERNAME}")'
            )

        if "password" in prompt_lower and "enter" in prompt_lower:
            return (
                f'driver.find_element(By.ID, "password").clear(); '
                f'driver.find_element(By.ID, "password").send_keys("{SUT_PASSWORD}")'
            )

        if "click" in prompt_lower and ("login" in prompt_lower or "button" in prompt_lower):
            return 'driver.find_element(By.ID, "login_button").click()'

        if "wait" in prompt_lower and ("redirect" in prompt_lower or "dashboard" in prompt_lower):
            # After click(), Selenium follows the 302 redirect synchronously.
            # Just add a brief implicit wait as a safety margin.
            return 'driver.implicitly_wait(5)'

        # Fallback
        return "pass  # step not mapped"

    def _expected_to_assertion(self, prompt: str) -> str:
        """Map an expected result to an assertion line."""
        prompt_lower = prompt.lower()

        if "dashboard" in prompt_lower:
            return 'assert "Dashboard" in driver.title, "Expected dashboard page after login"'

        # Fallback
        return 'assert True, "Expected result not mapped"'

    def _failure_analysis(self, prompt: str) -> dict:
        """Build a deterministic FailureAnalysis from the investigation prompt."""
        print("SUTAwareLLMClient._failure_analysis called")
        prompt_lower = prompt.lower()

        # Extract clues from the prompt
        evidence = []
        if "assertionerror" in prompt_lower or "assertionerror" in prompt_lower:
            evidence.append("AssertionError raised during test execution")
        if "dashboard" in prompt_lower:
            evidence.append("Expected page title 'Dashboard' was not found")
        if "screenshot" in prompt_lower:
            evidence.append("Screenshot captured at point of failure")
        if "login" in prompt_lower:
            evidence.append("Browser was on the login page after submitting valid credentials")
        if not evidence:
            evidence.append("Test execution failed with an exception")

        return {
            "failure_summary": "Login with valid credentials failed: expected dashboard page not found",
            "probable_root_cause": (
                "The login attempt failed because the provided credentials were incorrect, "
                "causing the user to stay on the login page. The assertion expected the dashboard title "
                "but found the login page title."
            ),
            "evidence": evidence,
            "severity": "high",
            "suggested_owner": "backend-api",
            "confidence": 0.9,
        }

    def _verification_result(self, prompt: str) -> dict:
        """Build a deterministic VerificationResult from the verification prompt."""
        prompt_lower = prompt.lower()

        # Check if the analysis and evidence are consistent
        evidence_gaps = []
        if "screenshot" not in prompt_lower:
            evidence_gaps.append("No screenshot evidence referenced")
        if "traceback" not in prompt_lower:
            evidence_gaps.append("No traceback details available")

        # Determine verdict based on prompt content
        has_analysis = "failure_summary" in prompt_lower or "root_cause" in prompt_lower or "probable_root_cause" in prompt_lower
        has_exception = "assertionerror" in prompt_lower or "exception" in prompt_lower
        has_evidence = "dashboard" in prompt_lower and "login" in prompt_lower

        if has_analysis and has_exception and has_evidence:
            verdict = "confirmed"
            reasoning = (
                "The failure analysis correctly identifies a redirect defect. "
                "The exception (AssertionError on missing 'Dashboard' title) matches "
                "the screenshot showing the login page after valid credential submission. "
                "Evidence and analysis are consistent."
            )
            action = "Fix the POST /login redirect URL from /login back to /dashboard"
        elif has_analysis and has_exception:
            verdict = "inconclusive"
            reasoning = "Analysis is plausible but evidence is insufficient for full confirmation."
            action = "Gather additional evidence (e.g., server logs, network trace)"
        else:
            verdict = "unconfirmed"
            reasoning = "Unable to correlate the failure analysis with available evidence."
            action = "Manual review required"

        return {
            "verdict": verdict,
            "reasoning": reasoning,
            "evidence_gaps": evidence_gaps,
            "recommended_action": action,
        }
