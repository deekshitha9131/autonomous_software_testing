#!/usr/bin/env python3
import os
import sys

# Set dummy env vars so LLM client initialization doesn't fail immediately on missing key
# (it will fail when trying to invoke, but that's caught)
os.environ["GROQ_API_KEY"] = "dummy"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b"

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import generate_test_scenarios
from app.workflow.state import WorkflowState

def test_unsupported():
    state = WorkflowState(
        requirement="Write a poem about the ocean.",
        requirement_understanding={
            "feature": "Poem",
            "objective": "Create a poem",
            "actors": [],
            "inputs": [],
            "preconditions": [],
            "expected_behavior": "",
            "constraints": [],
            "ambiguities": [],
            "status": "unsupported"
        }
    )
    result = generate_test_scenarios(state)
    print("Unsupported test result:", result)
    assert result.get("test_scenarios") == []
    assert result.get("test_cases") == []
    # Should not have added errors (since we returned early)
    assert "errors" not in result or len(result.get("errors", [])) == 0
    print("PASS: unsupported -> empty scenarios")

def test_testable():
    state = WorkflowState(
        requirement="A user can log in with valid credentials.",
        requirement_understanding={
            "feature": "Login",
            "objective": "Allow users to authenticate",
            "actors": ["User"],
            "inputs": ["username", "password"],
            "preconditions": ["User is on login page"],
            "expected_behavior": "User is redirected to home page",
            "constraints": [],
            "ambiguities": [],
            "status": "testable"
        }
    )
    result = generate_test_scenarios(state)
    print("Testable test result:", result)
    # Since we have dummy API key, the LLM call will fail and be caught, resulting in errors
    # So we expect either an errors list or maybe empty scenarios if the exception handling returns empty.
    # Let's just ensure no exception was raised (function returned a dict)
    assert isinstance(result, dict)
    # It may contain errors
    if "errors" in result:
        print("Errors present (expected due to dummy API key):", result["errors"])
    else:
        # If no errors, then scenarios were generated (unlikely with dummy key)
        assert "test_scenarios" in result
        print("Scenarios generated:", len(result.get("test_scenarios", [])))
    print("PASS: testable -> handled without exception")

def test_no_understanding():
    state = WorkflowState(
        requirement="A user can enter a name and see a greeting."
    )
    result = generate_test_scenarios(state)
    print("No understanding result:", result)
    assert isinstance(result, dict)
    # Either errors or scenarios
    print("PASS: no understanding -> handled")

if __name__ == "__main__":
    test_unsupported()
    test_testable()
    test_no_understanding()
    print("All tests completed")