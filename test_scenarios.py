#!/usr/bin/env python3
import os
import sys
from unittest.mock import MagicMock, patch

# Set dummy env vars for LLM client initialization (won't be used due to mock)
os.environ["GROQ_API_KEY"] = "dummy"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b"

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import generate_test_scenarios, ScenarioList
from app.workflow.state import WorkflowState
from app.requirement_understanding.schema import RequirementUnderstanding

# Mock LLMClient and its with_structured_output method
class MockLLMClient:
    def with_structured_output(self, schema, method=None):
        # Return a mock that has an invoke method returning a predefined ScenarioList
        mock = MagicMock()
        if schema == ScenarioList:
            # Return a list with two scenarios
            mock.invoke.return_value = ScenarioList(
                scenarios=[
                    ScenarioList.model_fields['scenarios'].type_(  # This is wrong; we need to construct Scenario instances
                        scenario_id="scen_1",
                        scenario_type="functional",
                        title="Test scenario 1",
                        description="First scenario"
                    ),
                    ScenarioList.model_fields['scenarios'].type_(
                        scenario_id="scen_2",
                        scenario_type="negative",
                        title="Test scenario 2",
                        description="Second scenario"
                    )
                ]
            )
        return mock

# Actually easier: we can directly patch _get_llm_client to return an object
# whose with_structured_output returns a mock with invoke returning our ScenarioList.

def test_generate_test_scenarios():
    with patch('app.workflow.graph._get_llm_client') as mock_get_llm:
        # Setup mock LLM client
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        # Define the return value when invoke is called
        mock_structured.invoke.return_value = ScenarioList(
            scenarios=[
                # We need to create Scenario instances
                # Since we don't have Scenario imported in this scope, we can import it
                from app.workflow.graph import Scenario
                Scenario(
                    scenario_id="scen_1",
                    scenario_type="functional",
                    title="Test scenario 1",
                    description="First scenario"
                ),
                Scenario(
                    scenario_id="scen_2",
                    scenario_type="negative",
                    title="Test scenario 2",
                    description="Second scenario"
                )
            ]
        )
        mock_get_llm.return_value = mock_llm

        # Test case 1: requirement with testable understanding
        state = WorkflowState(
            requirement="A user can log in with valid credentials.",
            requirement_understanding=RequirementUnderstanding(
                feature="Login",
                objective="Allow users to authenticate",
                actors=["User"],
                inputs=["username", "password"],
                preconditions=["User is on login page"],
                expected_behavior="User is redirected to home page",
                constraints=[],
                ambiguities=[],
                status="testable"
            )
        ).dict()

        result = generate_test_scenarios(state)
        print("Test 1 result:", result)
        assert "test_scenarios" in result
        assert len(result["test_scenarios"]) == 2
        assert result["test_scenarios"][0]["title"] == "Test scenario 1"
        assert result["test_cases"] == result["test_scenarios"]
        print("Test 1 passed")

        # Test case 2: requirement with unsupported understanding
        state2 = WorkflowState(
            requirement="Write a poem about the ocean.",
            requirement_understanding=RequirementUnderstanding(
                feature="Poem",
                objective="Create a poem",
                actors=[],
                inputs=[],
                preconditions=[],
                expected_behavior="",
                constraints=[],
                ambiguities=[],
                status="unsupported"
            )
        ).dict()

        result2 = generate_test_scenarios(state2)
        print("Test 2 result:", result2)
        assert result2["test_scenarios"] == []
        assert result2["test_cases"] == []
        # No errors added
        assert "errors" not in result2 or len(result2.get("errors", [])) == 0
        print("Test 2 passed")

        # Test case 3: requirement with no understanding (None)
        state3 = WorkflowState(
            requirement="A user can enter a name and see a greeting."
        ).dict()

        result3 = generate_test_scenarios(state3)
        print("Test 3 result:", result3)
        # Should have attempted to generate scenarios via LLM (mock)
        assert "test_scenarios" in result3
        assert len(result3["test_scenarios"]) == 2
        print("Test 3 passed")

        # Test case 4: empty requirement (should have been caught by validate_requirement, but we test anyway)
        state4 = WorkflowState(
            requirement=""
        ).dict()
        # In real flow, validation would add error and route to end, but we still test function
        result4 = generate_test_scenarios(state4)
        print("Test 4 result:", result4)
        # Since requirement is empty string, we still process; but we expect LLM to be called.
        # However, we can just accept whatever.
        print("Test 4 executed")

if __name__ == "__main__":
    test_generate_test_scenarios()