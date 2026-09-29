import os
import sys
from unittest.mock import Mock, patch

# Ensure we use the deterministic SUT-aware LLM client (no API key)
os.environ["OPENAI_API_KEY"] = ""

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import generate_test_case
from app.workflow.state import WorkflowState

def test_generate_test_case_from_scenarios():
    print("Testing generate_test_case with scenarios...")

    # Sample requirement
    requirement = "The system shall allow users to log in with email and password."

    # Sample requirement understanding (as would be produced by Phase 2)
    requirement_understanding = {
        "feature": "User Login",
        "objective": "Allow authenticated access to the system",
        "actors": ["User", "System"],
        "inputs": ["email", "password"],
        "preconditions": ["User is on the login page", "System is available"],
        "expected_behavior": "System validates credentials and grants access",
        "constraints": ["Password must be at least 8 characters"],
        "ambiguities": ["What happens if account is locked?"]
    }

    # Sample test scenarios (as would be produced by Phase 3)
    test_scenarios = [
        {
            "scenario_id": "func_1",
            "scenario_type": "functional",
            "title": "Login with valid credentials",
            "description": "Verify that a user can log in with correct email and password",
        },
        {
            "scenario_id": "neg_1",
            "scenario_type": "negative",
            "title": "Login with invalid password",
            "description": "Verify that a user sees an error message when password is incorrect",
        },
        {
            "scenario_id": "bound_1",
            "scenario_type": "boundary",
            "title": "Empty email",
            "description": "Verify that the system handles empty email input",
        }
    ]

    # Build state
    state = WorkflowState(
        requirement=requirement,
        requirement_understanding=requirement_understanding,
        test_scenarios=test_scenarios
    )

    # Call the node function
    result = generate_test_case(state)

    print("Result:", result)

    # Assertions
    assert "test_case" in result, "test_case should be present for backward compatibility"
    assert result["test_case"] is not None, "test_case should not be None"
    assert "test_cases" in result, "test_cases should be present"
    assert isinstance(result["test_cases"], list), "test_cases should be a list"
    assert len(result["test_cases"]) == len(test_scenarios), f"Should generate {len(test_scenarios)} test cases"

    # Check each test case has scenario_id matching
    for i, tc in enumerate(result["test_cases"]):
        assert tc["scenario_id"] == test_scenarios[i]["scenario_id"], f"Test case {i} scenario_id mismatch"
        assert tc["test_id"], f"Test case {i} should have a test_id"
        assert isinstance(tc["test_data"], dict), f"Test case {i} test_data should be dict"
        # Ensure no hardcoded login fields (we can't fully test but we can check that steps are not containing hardcoded selectors)
        # We'll just print steps for inspection
        print(f"Test case {i} steps: {tc.get('steps', [])}")

    # The errors field may be absent if no errors; if present, should be a list
    if "errors" in result:
        assert isinstance(result["errors"], list), "errors should be list"
        # Since we didn't set any prior errors, errors should be empty
        assert result["errors"] == [], f"Expected no errors, got {result['errors']}"

    print("All tests passed!")

if __name__ == "__main__":
    test_generate_test_case_from_scenarios()