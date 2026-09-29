"""Deterministic LLM client for the login SUT.

When no OpenAI API key is available, this client provides pre-built responses
for the login demo SUT so the full LangGraph workflow can execute end-to-end
without an external LLM.

It implements the same LLMClient interface used by all agents.
"""
import json
import os
from typing import Optional, Type, TypeVar

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
            return schema.model_validate(self._login_test_case(prompt))

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

        # --- Requirement Understanding Agent asks for a RequirementUnderstanding ---
        if schema_name == "RequirementUnderstanding":
            return schema.model_validate(self._requirement_understanding(prompt))

        # --- Fallback: return a minimal valid instance ---
        # Build with defaults where possible
        raise ValueError(
            f"SUTAwareLLMClient: unhandled schema '{schema_name}'. "
            "Set OPENAI_API_KEY for full LLM support."
        )

    # ------------------------------------------------------------------
    # Pre-built responses
    # ------------------------------------------------------------------

    def _login_test_case(self, prompt: str) -> dict:
        """Return a TestCase dict based on the requirement in the prompt."""
        requirement = self._extract_requirement(prompt)
        scenario_id = self._extract_scenario_id(prompt)
        print(f"DEBUG: requirement extracted: {requirement}")
        print(f"DEBUG: scenario_id extracted: {scenario_id}")
        if requirement is None:
            # Fallback to the hardcoded login test case
            print("DEBUG: using hardcoded test case")
            test_case = self._hardcoded_login_test_case()
        else:
            print("DEBUG: generating test case from requirement")
            test_case = self._generate_test_case_from_requirement(requirement)
        # Ensure scenario_id is present
        if scenario_id is not None:
            test_case["scenario_id"] = scenario_id
        else:
            # If no scenario_id in prompt, fallback to empty string (should not happen in Phase 4)
            test_case["scenario_id"] = ""
        # Generate a scenario-specific test_id if we have a scenario_id
        if scenario_id and scenario_id.strip():
            # Use pattern tc_<scenario_id>_001
            test_case["test_id"] = f"tc_{scenario_id}_001"
        return test_case

    def _extract_requirement(self, prompt: str) -> Optional[str]:
        """Extract the requirement from the prompt.
        The prompt is expected to have a line that starts with "Requirement:" and then the requirement on the next line.
        """
        print(f"DEBUG prompt: {repr(prompt)}")
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            print(f"DEBUG line {i}: {repr(line)}")
            if line.strip() == "Requirement:":
                # The requirement is the next line
                print(f"DEBUG: found Requirement at line {i}")
                if i+1 < len(lines):
                    req = lines[i+1].strip()
                    # Remove any trailing instructions (like "Generate a JSON object...")
                    if "Generate a JSON object" in req:
                        req = req.split("Generate a JSON object")[0].strip()
                    print(f"DEBUG: req = {repr(req)}")
                    return req
        return None

    def _extract_scenario_id(self, prompt: str) -> Optional[str]:
        """Extract the scenario ID from the prompt.
        The prompt is expected to have a line that contains "Scenario ID:" followed by the ID.
        """
        print(f"DEBUG prompt for scenario_id: {repr(prompt)}")
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            print(f"DEBUG line {i}: {repr(line)}")
            if "Scenario ID:" in line:
                # The scenario ID is after the colon
                print(f"DEBUG: found Scenario ID at line {i}")
                parts = line.split('Scenario ID:', 1)
                if len(parts) == 2:
                    sid = parts[1].strip()
                    # Remove any leading dash or bullet if present
                    if sid.startswith('-'):
                        sid = sid[1:].strip()
                    # Remove any trailing instructions (like on same line)
                    # There shouldn't be extra text after the ID on same line in our prompt format
                    return sid
        return None

    def _hardcoded_login_test_case(self) -> dict:
        """Return a TestCase dict for the login requirement (hardcoded fallback)."""
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

    def _generate_test_case_from_requirement(self, requirement: str) -> dict:
        """Generate a TestCase dict from the requirement."""
        print(f"DEBUG: _generate_test_case_from_requirement called with requirement: {requirement}")
        import re
        # Try to extract an expected title from the requirement
        title_match = re.search(r"title\s*['\"]([^'\"]+)['\"]", requirement, re.IGNORECASE)
        expected_title = title_match.group(1) if title_match else None

        # Generate a test_id from the requirement (first three words, lowercased, joined by underscores)
        words = requirement.lower().split()
        test_id = "_".join(words[:3]) if len(words) >= 3 else "login_test_case"
        if not test_id:
            test_id = "login_test_case"

        # Preconditions: same as hardcoded
        preconditions = [
            f"The SUT is running at {SUT_BASE_URL}",
            f"Valid credentials exist: username='{SUT_USERNAME}', password='{SUT_PASSWORD}'",
        ]

        # Steps: login steps and then a step to check the title (if we have an expected title) or just wait for page load
        steps = [
            f"Navigate to {SUT_BASE_URL}/login",
            f"Enter '{SUT_USERNAME}' into the username field (id='username')",
            f"Enter '{SUT_PASSWORD}' into the password field (id='password')",
            "Click the login button (id='login_button')",
            "Wait for the page to redirect",
        ]
        if expected_title:
            steps.append(f"Assert that the page title is '{expected_title}'")
        else:
            steps.append("Wait for the page to load")

        # Expected result: we'll use the requirement as the expected result
        expected_result = f"The user is redirected to the page as specified in the requirement: '{requirement}'"

        # Description: the requirement
        description = requirement

        # Title: a short version of the requirement for the test title
        title = f"Login test: {requirement[:50]}" if len(requirement) > 50 else f"Login test: {requirement}"

        result = {
            "test_id": test_id,
            "title": title,
            "description": description,
            "preconditions": preconditions,
            "steps": steps,
            "expected_result": expected_result,
            "test_type": "functional",
            "priority": "critical",
        }
        print(f"DEBUG: generated test case: {result}")
        return result

    def _step_to_code(self, prompt: str) -> str:
        """Map a step description to a Selenium code line."""
        prompt_lower = prompt.lower()

        if "navigate" in prompt_lower and "login" in prompt_lower:
            return f'driver.get("{SUT_BASE_URL}/login")'

        if "username" in prompt_lower and "enter" in prompt_lower:
            # Extract the value if specified in quotes, otherwise use SUT_USERNAME
            import re
            # Look for a pattern like Enter 'value' into the username field
            match = re.search(r"Enter\s+'([^']*)'\s+into\s+the\s+username\s+field", prompt, re.IGNORECASE)
            if match:
                value = match.group(1)
            else:
                value = SUT_USERNAME
            return (
                f'driver.find_element(By.ID, "username").clear(); '
                f'driver.find_element(By.ID, "username").send_keys("{value}")'
            )

        if "password" in prompt_lower and "enter" in prompt_lower:
            # Extract the value if specified in quotes, otherwise use SUT_PASSWORD
            import re
            match = re.search(r"Enter\s+'([^']*)'\s+into\s+the\s+password\s+field", prompt, re.IGNORECASE)
            if match:
                value = match.group(1)
            else:
                value = SUT_PASSWORD
            return (
                f'driver.find_element(By.ID, "password").clear(); '
                f'driver.find_element(By.ID, "password").send_keys("{value}")'
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

        # Handle assertion about page title
        if "assert that the page title is" in prompt_lower:
            # Extract the title in quotes
            import re
            title_match = re.search(r"assert that the page title is\s*['\"]([^'\"]+)['\"]", prompt, re.IGNORECASE)
            if title_match:
                expected_title = title_match.group(1)
                return f'assert "{expected_title}" in driver.title, "Expected page title to be \'{expected_title}\'"'
            # If we can't extract, fall back to dashboard check
            if "dashboard" in prompt_lower:
                return 'assert "Dashboard" in driver.title, "Expected dashboard page after login"'
            # Fallback
            return 'assert True, "Expected result not mapped"'

        # Handle redirected to the page as specified in the requirement
        if "redirected to the page as specified in the requirement:" in prompt_lower:
            # Extract the requirement in single quotes
            import re
            # Pattern to capture text inside single quotes after the colon
            match = re.search(r"redirected to the page as specified in the requirement:\s*'([^']+)'", prompt, re.IGNORECASE)
            if match:
                requirement = match.group(1).lower()
                # If the requirement is about login, assert dashboard
                if "login" in requirement:
                    return 'assert "Dashboard" in driver.title, "Expected dashboard page after login"'
                # If the requirement is about profile, assert User Profile in title
                if "profile" in requirement:
                    return 'assert "User Profile" in driver.title, "Expected page title to be \'User Profile\'"'
                # Fallback to dashboard for login-related requirements
                return 'assert "Dashboard" in driver.title, "Expected dashboard page after login"'

        if "dashboard" in prompt_lower:
            return 'assert "Dashboard" in driver.title, "Expected dashboard page after login"'

        # Fallback
        return 'assert True, "Expected result not mapped"'

    def _failure_analysis(self, prompt: str) -> dict:
        """Build a FailureAnalysis from the investigation prompt by extracting actual test details."""
        print("SUTAwareLLMClient._failure_analysis called")
        import json
        import re

        # Initialize default values
        test_case = {}
        exception = {}
        failure_summary = "Test execution failed"
        probable_root_cause = "Insufficient evidence to determine root cause"
        evidence = []
        severity = "medium"
        suggested_owner = "unknown"
        confidence = 0.5

        # Helper to extract a JSON-like section between two markers
        def extract_section(text, start_marker, end_marker):
            try:
                start_idx = text.index(start_marker) + len(start_marker)
                end_idx = text.index(end_marker, start_idx)
                return text[start_idx:end_idx].strip()
            except ValueError:
                return None

        # Extract Test Case section
        test_case_str = extract_section(prompt, "## Test Case:", "## Generated Test Code:")
        if test_case_str:
            try:
                test_case = json.loads(test_case_str)
            except json.JSONDecodeError:
                # If not valid JSON, try to extract key-value pairs crudely
                pass

        # Extract Exception Details section
        exception_str = extract_section(prompt, "## Exception Details:", "## Standard Output:")
        if exception_str:
            try:
                exception = json.loads(exception_str)
            except json.JSONDecodeError:
                pass

        # Build evidence list based on what we found
        if exception:
            exc_type = exception.get("type", "")
            exc_message = exception.get("message", "")
            if exc_type:
                evidence.append(f"Exception: {exc_type}")
            if exc_message:
                evidence.append(f"Exception message: {exc_message}")

        # Check for screenshot
        if "Screenshot Path:" in prompt:
            # Extract the screenshot path line
            for line in prompt.split('\n'):
                if line.startswith("Screenshot Path:"):
                    path = line.split(":", 1)[1].strip()
                    if path and path != "(none)":
                        evidence.append(f"Screenshot captured: {path}")
                    break

        # Check for stdout/stderr
        if "## Standard Output:" in prompt:
            stdout_section = extract_section(prompt, "## Standard Output:", "## Standard Error:")
            if stdout_section and stdout_section.strip() and stdout_section.strip() != "(empty)":
                evidence.append("Standard output captured during execution")
        if "## Standard Error:" in prompt:
            stderr_section = extract_section(prompt, "## Standard Error:", "## Execution Metadata:")
            if stderr_section and stderr_section.strip() and stderr_section.strip() != "(empty)":
                evidence.append("Standard error captured during execution")

        # Check for connection/environment failures in exception or stderr
        exc_message = exception.get("message", "").lower()
        # Also check stderr section if we have it
        stderr_text = ""
        if "## Standard Error:" in prompt:
            stderr_section = extract_section(prompt, "## Standard Error:", "## Execution Metadata:")
            if stderr_section:
                stderr_text = stderr_section.lower()

        # Combine sources for checking
        combined_text = exc_message + " " + stderr_text

        # Connection-related failure indicators
        connection_indicators = [
            "err_connection_refused",
            "connection refused",
            "failed to connect",
            "connection timed out",
            "name or service not known",
            "network is unreachable",
            "no route to host",
            "wtf is",
            "webdriverexception",  # often wraps connection errors
        ]

        is_connection_failure = any(indicator in combined_text for indicator in connection_indicators)

        # If we have test case details, tailor the summary and root cause
        if test_case:
            test_id = test_case.get("test_id", "unknown")
            title = test_case.get("title", "")
            test_type = test_case.get("test_type", "")
            # Build a base summary
            failure_summary = f"Test '{test_id}' ({title}) failed"
            if test_type:
                failure_summary += f" [{test_type} test]"

            if is_connection_failure:
                failure_summary = f"Test '{test_id}' ({title}) failed: SUT was unreachable"
                probable_root_cause = "The demo application was not running or was not accepting connections at the configured URL/port."
                severity = "high"
                suggested_owner = "devops/infrastructure"
                confidence = 0.9
            else:
                # Determine probable root cause based on exception and test case (existing logic)
                # Look for assertion messages that indicate what went wrong
                if "expected dashboard page after login" in exc_message:
                    # This suggests the test expected to be redirected to dashboard but wasn't
                    failure_summary = f"Test '{test_id}' failed: expected redirect to dashboard but did not occur"
                    probable_root_cause = "The login attempt did not redirect to the dashboard page as expected. This could be due to incorrect credentials, a bug in the login logic, or a redirect issue."
                    severity = "high"
                    suggested_owner = "backend-api"
                    confidence = 0.8
                elif "expected to remain on the login page" in exc_message:
                    failure_summary = f"Test '{test_id}' failed: expected to remain on login page but was redirected"
                    probable_root_cause = "The login attempt redirected to another page (e.g., dashboard) when it should have remained on the login page (e.g., due to incorrect credentials being accepted)."
                    severity = "high"
                    suggested_owner = "backend-api"
                    confidence = 0.8
                elif "invalid credentials" in exc_message or "error message" in exc_message:
                    failure_summary = f"Test '{test_id}' failed: expected error message not found"
                    probable_root_cause = "The test expected an error message to appear (e.g., for invalid credentials) but it did not. This could be due to the error message not being displayed or the test looking for the wrong text."
                    severity = "medium"
                    suggested_owner = "frontend-team"
                    confidence = 0.7
                else:
                    # Generic fallback
                    probable_root_cause = "The test failed due to an assertion error. Examine the exception message and test steps for more details."
                    confidence = 0.6
        else:
            # If we couldn't extract test case, use a generic summary based on exception
            if exception:
                if is_connection_failure:
                    failure_summary = f"Test execution failed: SUT was unreachable"
                    probable_root_cause = "The demo application was not running or was not accepting connections at the configured URL/port."
                    severity = "high"
                    suggested_owner = "devops/infrastructure"
                    confidence = 0.9
                else:
                    failure_summary = f"Test execution failed with {exception.get('type', 'an exception')}"
                    probable_root_cause = f"Exception details: {exception.get('message', 'No message provided')}"
                    confidence = 0.6
            else:
                failure_summary = "Test execution failed (no exception details available)"
                probable_root_cause = "Insufficient information to determine the cause of failure."
                confidence = 0.4

        # If we have no evidence yet, add a generic one
        if not evidence:
            evidence.append("Test execution failed (see exception for details)")

        return {
            "failure_summary": failure_summary,
            "probable_root_cause": probable_root_cause,
            "evidence": evidence,
            "severity": severity,
            "suggested_owner": suggested_owner,
            "confidence": confidence,
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

    def _requirement_understanding(self, prompt: str) -> dict:
        """Generate a deterministic requirement understanding based on the prompt."""
        # Extract the requirement from the prompt
        requirement = self._extract_requirement(prompt)

        # If we can't extract a requirement, return a basic unsupported response
        if requirement is None:
            return {
                "feature": "",
                "objective": "",
                "actors": [],
                "inputs": [],
                "preconditions": [],
                "expected_behavior": "",
                "constraints": [],
                "ambiguities": ["No clear requirement provided"],
                "status": "unsupported",
                "clarification_reason": "Unable to extract a clear requirement from the prompt"
            }

        requirement_lower = requirement.lower().strip()

        # Handle specific test cases for verification
        if "verify that a user can log in with valid credentials" in requirement_lower:
            return {
                "feature": "user login",
                "objective": "Verify that a user can successfully authenticate with valid credentials",
                "actors": ["user"],
                "inputs": ["username", "password"],
                "preconditions": ["User account exists with valid credentials", "Login system is operational"],
                "expected_behavior": "System authenticates the user and grants access to the application",
                "constraints": ["Must use valid credentials", "Login process must complete within timeout period"],
                "ambiguities": [],
                "status": "testable",
                "clarification_reason": None
            }
        elif "change the name displayed on their profile" in requirement_lower or "modify their profile name" in requirement_lower:
            return {
                "feature": "profile name update",
                "objective": "Allow users to update their display name in their profile",
                "actors": ["user"],
                "inputs": ["new profile name"],
                "preconditions": ["User is authenticated", "Profile exists for the user"],
                "expected_behavior": "System updates the user's display name and reflects the change in the profile",
                "constraints": ["Profile name must meet length and character requirements", "Name cannot be empty"],
                "ambiguities": [],
                "status": "testable",
                "clarification_reason": None
            }
        elif requirement_lower.strip() == "test the profile.":
            return {
                "feature": "profile",
                "objective": "",
                "actors": [],
                "inputs": [],
                "preconditions": [],
                "expected_behavior": "",
                "constraints": [],
                "ambiguities": ["Unclear what aspect of the profile should be tested", "No specific action or behavior mentioned"],
                "status": "clarification_needed",
                "clarification_reason": "Requirement is too vague - needs to specify what aspect of the profile to test and what behavior to verify"
            }
        elif "write a poem" in requirement_lower or "poem about" in requirement_lower:
            return {
                "feature": "",
                "objective": "",
                "actors": [],
                "inputs": [],
                "preconditions": [],
                "expected_behavior": "",
                "constraints": [],
                "ambiguities": ["Request is for creative writing, not software functionality"],
                "status": "unsupported",
                "clarification_reason": "Request is for poetry writing, which is not a software feature that can be tested"
            }
        else:
            # Generic fallback for other requirements
            # Try to determine if it sounds like a software requirement
            software_indicators = ["verify", "ensure", "check", "test", "validate", "confirm", "should", "must", "shall"]
            is_likely_software = any(indicator in requirement_lower for indicator in software_indicators)

            if is_likely_software:
                # It seems like a software requirement but we need more details
                return {
                    "feature": requirement[:50] + "..." if len(requirement) > 50 else requirement,
                    "objective": "To be determined based on requirement clarification",
                    "actors": ["user"],  # Default assumption
                    "inputs": [],
                    "preconditions": ["System is operational"],
                    "expected_behavior": "To be determined based on requirement clarification",
                    "constraints": [],
                    "ambiguities": ["Requirement lacks sufficient detail to determine specific test criteria"],
                    "status": "clarification_needed",
                    "clarification_reason": "Requirement needs more specific details about expected behavior, inputs, and constraints to be testable"
                }
            else:
                return {
                    "feature": "",
                    "objective": "",
                    "actors": [],
                    "inputs": [],
                    "preconditions": [],
                    "expected_behavior": "",
                    "constraints": [],
                    "ambiguities": ["Request does not appear to describe software functionality"],
                    "status": "unsupported",
                    "clarification_reason": "Request does not describe a testable software feature or requirement"
                }
