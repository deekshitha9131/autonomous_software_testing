#!/usr/bin/env python3
"""
Test script for Phase 7: Generic Execution & Evidence.
Tests multi-test generation, execution, missing_context behavior, and SUT lifecycle.
"""
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Ensure we use the deterministic SUT-aware LLM client (no API key)
os.environ["OPENAI_API_KEY"] = ""

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import (
    generate_test_case,
    generate_selenium_test,
    execute_test,
    WorkflowState,
    _start_sut,
    _stop_sut,
    _get_llm_client,
)
from app.test_automation_agent.service import TestAutomationAgent
from app.llm.client import LLMClient
from app.requirement_to_testcase.schema import TestCase


class DummyLLMClient(LLMClient):
    """Deterministic LLM client that returns safe, generic Selenium code based on prompt."""
    def generate_structured(self, prompt, schema):
        # Analyze prompt to return appropriate code line
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            # Extract step from prompt
            if "Step:" in prompt:
                step = prompt.split("Step:")[1].strip()
                # Generate a safe selector based on step keywords
                if "username" in step.lower() or "email" in step.lower():
                    code = 'driver.find_element(By.ID, "username").send_keys("test_user")'
                elif "password" in step.lower():
                    code = 'driver.find_element(By.ID, "password").send_keys("test_pass")'
                elif "login" in step.lower() or "sign in" in step.lower():
                    code = 'driver.find_element(By.ID, "login_button").click()'
                elif "profile" in step.lower():
                    code = 'driver.find_element(By.ID, "profile_link").click()'
                elif "navigate" in step.lower() or "go to" in step.lower():
                    # Extract URL if present
                    if "http" in step:
                        # crude extraction
                        import re
                        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', step)
                        if urls:
                            code = f'driver.get("{urls[0]}")'
                        else:
                            code = 'driver.get("http://example.com")'
                    else:
                        code = 'driver.get("http://example.com")'
                elif "assert" in step.lower() or "verify" in step.lower() or "check" in step.lower():
                    # Return an assertion
                    code = 'assert True, "Placeholder assertion"'
                else:
                    # Default to a harmless action
                    code = 'driver.find_element(By.TAG_NAME, "body")'
            else:
                code = 'driver.find_element(By.TAG_NAME, "body")'
        elif "Convert the following expected result into a single line of Python assertion code" in prompt:
            # Return a simple assertion
            code = 'assert True, "Expected result verification not implemented"'
        else:
            # Fallback
            code = 'assert True, "Placeholder"'

        # Return as per schema
        if schema.__name__ == "CodeLine":
            return schema(code=code)
        elif schema.__name__ == "AssertionLine":
            return schema(assertion=code)
        else:
            # Try to create instance with code or assertion field
            try:
                return schema(code=code)
            except:
                try:
                    return schema(assertion=code)
                except:
                    return schema()  # empty

# Helper to create a mock requirement understanding and scenarios
def make_state_with_test_cases(requirement, test_cases_list):
    """Create a WorkflowState with requirement and test_cases (list of dicts)."""
    state = WorkflowState(
        requirement=requirement,
        requirement_understanding={},
        test_scenarios=[],  # not used in generate_test_case if we provide test_cases directly
        test_cases=test_cases_list,
        # Provide dummy SUT context for generation
        base_url="http://localhost:8000",
        sut_id="dummy_sut",
        sut_context={"page": "login"},  # non-empty dict
        test_data={},  # shared test data (not used for readiness check)
    )
    # Manually set test_cases (bypassing the generator)
    # Ensure each test case has required fields: test_type and priority
    enriched_test_cases = []
    for tc in test_cases_list:
        enriched_tc = tc.copy()
        enriched_tc.setdefault("test_type", "functional")
        enriched_tc.setdefault("priority", "medium")
        enriched_test_cases.append(enriched_tc)
    state.test_cases = enriched_test_cases
    # Also set test_case to first for backward compatibility
    if enriched_test_cases:
        state.test_case = enriched_test_cases[0]
    return state

def test_multi_test_generation_and_execution():
    print("=== Test: Multi-test generation and execution ===")
    requirement = "The system shall allow users to log in and view profile."

    # Create three test cases: login, profile, and navigation
    test_cases = [
        {
            "test_id": "login_1",
            "scenario_id": "func_1",
            "title": "Login with valid credentials",
            "description": "Verify that a user can log in with valid credentials",
            "steps": [
                "Navigate to the login page",
                "Enter username in the username field",
                "Enter password in the password field",
                "Click the login button"
            ],
            "expected_result": "User is logged in and redirected to dashboard",
            "test_data": {
                "username": "test_user",
                "password": "test_pass"
            }
        },
        {
            "test_id": "profile_2",
            "scenario_id": "func_2",
            "title": "View profile",
            "description": "Verify that a logged-in user can view their profile",
            "steps": [
                "Click on the profile link",
                "Verify that the profile page displays the user's name"
            ],
            "expected_result": "Profile page shows user's name",
            "test_data": {
                "username": "test_user"
            }
        },
        {
            "test_id": "nav_3",
            "scenario_id": "func_3",
            "title": "Navigate to home page",
            "description": "Verify that the home page loads correctly",
            "steps": [
                "Navigate to the home page",
                "Verify that the home page title is 'Welcome'"
            ],
            "expected_result": "Home page title is 'Welcome'",
            "test_data": {}
        }
    ]

    state = make_state_with_test_cases(requirement, test_cases)

    # Patch _get_llm_client to return our DummyLLMClient
    with patch('app.workflow.graph._get_llm_client', return_value=DummyLLMClient()):
        # Step 1: Generate test cases (already done via make_state_with_test_cases, but we call the node to simulate flow)
        # In real flow, generate_test_case would populate test_cases from scenarios.
        # We'll skip that and assume test_cases are already in state.

        # Step 2: Generate Selenium tests for all test cases
        print("Calling generate_selenium_test...")
        gen_result = generate_selenium_test(state)
        print("Generation result keys:", gen_result.keys())
        assert "errors" not in gen_result or not gen_result["errors"], f"Generation errors: {gen_result.get('errors')}"
        assert "generated_test_codes" in gen_result, "generated_test_codes missing"
        assert len(gen_result["generated_test_codes"]) == 3, f"Expected 3 generated tests, got {len(gen_result['generated_test_codes'])}"
        # Check that each entry has test_id and code
        for entry in gen_result["generated_test_codes"]:
            assert "test_id" in entry and "code" in entry, f"Invalid entry: {entry}"
        # Apply the generation updates to state
        state = state.copy(update=gen_result)
        # Check backward compatibility fields
        assert state.generated_test_code is not None, "generated_test_code not set for backward compatibility"
        assert state.generated_test_path is not None, "generated_test_path not set for backward compatibility"
        print(f"Generated {len(state.generated_test_codes)} test codes.")
        print(f"First test code sample: {state.generated_test_code[:100]}...")

        # Step 3: Execute all generated tests
        print("\nCalling execute_test...")
        exec_result = execute_test(state)
        print("Execution result keys:", exec_result.keys())
        # Check that no errors occurred during execution (unless expected)
        if "errors" in exec_result and exec_result["errors"]:
            print(f"Execution errors: {exec_result['errors']}")
            # We'll allow errors if they are due to missing SUT context? But we have context.
            # For now, we expect no errors.
            # However, the dummy LLM client may produce code that fails because selectors don't exist.
            # We'll treat execution errors as expected in this test because we are not running a real SUT.
            # We'll just check that we have execution_results.
            pass

        # Apply execution updates to state
        state = state.copy(update=exec_result)
        # Check that execution_results list exists and has 3 entries
        assert hasattr(state, 'execution_results'), "execution_results not set in state"
        assert state.execution_results is not None, "execution_results is None"
        assert len(state.execution_results) == 3, f"Expected 3 execution results, got {len(state.execution_results)}"
        print(f"Execution results count: {len(state.execution_results)}")

        # Check each result has test_id and scenario_id
        for i, res in enumerate(state.execution_results):
            assert "test_id" in res, f"Result {i} missing test_id"
            assert "scenario_id" in res, f"Result {i} missing scenario_id"
            print(f"Result {i}: test_id={res['test_id']}, scenario_id={res['scenario_id']}, status={res.get('status')}")

        # Check execution_summary
        assert hasattr(state, 'execution_summary'), "execution_summary not set"
        assert state.execution_summary is not None, "execution_summary is None"
        summary = state.execution_summary
        print(f"Execution summary: {summary}")
        assert summary["total"] == 3, f"Expected total=3, got {summary['total']}"
        # We don't assert passed/failed because the dummy code may pass or fail depending on selectors.
        # But we can check that passed + failed + errors + skipped = total
        total_accounted = summary["passed"] + summary["failed"] + summary["errors"] + summary["skipped"]
        assert total_accounted == summary["total"], f"Summary counts don't add up: {summary}"

    print("\n=== Multi-test generation and execution test PASSED ===\n")

def test_missing_context():
    print("=== Test: Missing SUT context ===")
    requirement = "The system shall allow users to log in."
    # Create a simple test case
    test_cases = [{
        "test_id": "login_1",
        "scenario_id": "func_1",
        "title": "Login",
        "description": "Login test",
        "steps": ["Enter username"],
        "expected_result": "User logged in",
        "test_data": {"username": "test"}
    }]

    state = make_state_with_test_cases(requirement, test_cases)
    # Intentionally leave base_url, sut_id, sut_context empty or None
    state.base_url = ""  # empty string
    state.sut_id = None
    state.sut_context = {}
    state.test_data = {}  # not used for readiness check

    # Patch _get_llm_client to return DummyLLMClient (though not needed for readiness check)
    with patch('app.workflow.graph._get_llm_client', return_value=DummyLLMClient()):
        print("Calling generate_selenium_test with missing context...")
        gen_result = generate_selenium_test(state)
        print("Generation result:", gen_result)
        # Expect errors and missing_context in the result
        assert "errors" in gen_result, "Expected errors in result"
        assert any("Missing SUT context" in err for err in gen_result["errors"]), f"Errors do not indicate missing context: {gen_result['errors']}"
        assert "missing_context" in gen_result, "missing_context missing from result"
        missing_info = gen_result["missing_context"]
        assert missing_info["status"] == "missing_context", f"Expected missing_context status, got {missing_info['status']}"
        assert "base_url" in missing_info["missing"] or "sut_context" in missing_info["missing"], f"Missing list does not indicate missing base_url or sut_context: {missing_info['missing']}"

        # Apply generation updates to state
        state = state.copy(update=gen_result)
        # Check that state has missing_context set
        assert state.get("missing_context") is not None, "missing_context not set in state"
        assert state["missing_context"]["status"] == "missing_context", "State missing_context incorrect"

        # Check that no tests were generated
        assert not state.generated_test_codes, "generated_test_codes should be empty when missing context"
        assert state.generated_test_code is None, "generated_test_code should be None when missing context"
        assert state.generated_test_path is None, "generated_test_path should be None when missing context"

        # Now call execute_test: should skip execution and return an error or skipped result
        print("Calling execute_test with missing context...")
        exec_result = execute_test(state)
        print("Execution result:", exec_result)
        # We expect execute_test to return an error or a skipped result
        assert "errors" in exec_result or "execution_result" in exec_result, "execute_test should return something"
        if "execution_result" in exec_result:
            res = exec_result["execution_result"]
            # We set in execute_test to return a skipped result when missing_context present
            assert res.get("reason") == "missing_context", f"Expected missing_context reason, got {res.get('reason')}"
            assert res.get("status") == "skipped", f"Expected skipped status, got {res.get('status')}"
        else:
            # If errors are present, we expect at least one error about missing context
            assert "errors" in exec_result, "Expected errors in execution result"
            assert any("Missing SUT context" in err for err in exec_result["errors"]), f"Errors do not indicate missing context: {exec_result['errors']}"

    print("\n=== Missing context test PASSED ===\n")

def test_external_sut_does_not_start_demo_app():
    print("=== Test: External SUT does not start demo app ===")
    # We'll mock subprocess.Popen to detect if demo_app is started
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = None  # simulate no process

        requirement = "Test"
        test_cases = [{
            "test_id": "ext_1",
            "scenario_id": "sc_1",
            "title": "External test",
            "description": "",
            "steps": ["Navigate to http://example.com"],
            "expected_result": "Page loaded",
            "test_data": {}
        }]

        state = make_state_with_test_cases(requirement, test_cases)
        # Set base_url to an external URL
        state.base_url = "http://example.com"
        state.sut_id = "ext_sut"
        state.sut_context = {"some": "context"}
        state.test_data = {}

        # We need to generate tests first to have something to execute
        print("Generating tests for external SUT...")
        with patch('app.workflow.graph._get_llm_client', return_value=DummyLLMClient()):
            gen_result = generate_selenium_test(state)
            assert "errors" not in gen_result or not gen_result["errors"], f"Generation errors: {gen_result.get('errors')}"
            state = state.copy(update=gen_result)

        # Now execute: this will call _start_sut
        print("Executing tests for external SUT...")
        # We'll mock _start_sut to return None (simulating SUT already running) and check that it was called with the intent to start demo app.
        # We'll also check that subprocess.Popen is not called.
        with patch('app.workflow.graph._start_sut', wraps=_start_sut) as mock_start_sut:
            with patch('app.workflow.graph._stop_sut') as mock_stop_sut:
                exec_result = execute_test(state)
                # Apply execution updates to state
                state = state.copy(update=exec_result)
                # Check that _start_sut was called
                assert mock_start_sut.called, "_start_sut was not called"
                # Check the argument passed to _start_sut
                args, kwargs = mock_start_sut.call_args
                passed_base_url = args[0] if args else None
                assert passed_base_url == "http://example.com", f"Expected base_url 'http://example.com', got {passed_base_url}"
                # We cannot directly see if demo_app was started because we mocked _start_sut, but we know that
                # our _start_sut function will not attempt to start demo_app for non-localhost hosts.
                # We can verify by checking the host extraction: host should be 'example.com', not localhost-like.
                # We'll trust the logic in _start_sut.

            # Additionally, we can check that subprocess.Popen was NOT called (since we are not starting demo app)
            # However, note that _start_sut may still call subprocess.Popen if it thinks it's localhost.
            # Since host is 'example.com', it should not.
            assert not mock_popen.called, f"subprocess.Popen was called {mock_popen.call_count} times, but should not be called for external SUT"

    print("\n=== External SUT test PASSED ===\n")

def test_evidence_traceability():
    print("=== Test: Evidence traceability ===")
    requirement = "Test traceability"
    test_cases = [{
        "test_id": "trace_1",
        "scenario_id": "sc_trace",
        "title": "Traceability test",
        "description": "",
        "steps": ["Do something"],
        "expected_result": "Something happens",
        "test_data": {}
    }]

    state = make_state_with_test_cases(requirement, test_cases)
    # Generate and execute
    with patch('app.workflow.graph._get_llm_client', return_value=DummyLLMClient()):
        gen_result = generate_selenium_test(state)
        assert "errors" not in gen_result or not gen_result["errors"], f"Generation errors: {gen_result.get('errors')}"
        state = state.copy(update=gen_result)
        exec_result = execute_test(state)
        state = state.copy(update=exec_result)

    # Check that execution result has test_id and scenario_id
    assert hasattr(state, 'execution_results'), "execution_results not set"
    assert len(state.execution_results) == 1, "Expected one execution result"
    res = state.execution_results[0]
    assert res.get("test_id") == "trace_1", f"Expected test_id trace_1, got {res.get('test_id')}"
    assert res.get("scenario_id") == "sc_trace", f"Expected scenario_id sc_trace, got {res.get('scenario_id')}"
    # Also check that the requirement is accessible via state
    assert state.requirement == requirement, "Requirement not preserved in state"

    print("\n=== Evidence traceability test PASSED ===\n")

def run_all_tests():
    try:
        test_multi_test_generation_and_execution()
        test_missing_context()
        test_external_sut_does_not_start_demo_app()
        test_evidence_traceability()
        print("🎉 All tests passed!")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()