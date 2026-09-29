#!/usr/bin/env python3
import os
import sys
from unittest.mock import MagicMock, patch

# Set dummy env vars so LLM client initialization doesn't fail immediately
os.environ["GROQ_API_KEY"] = "dummy"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b"

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import generate_test_scenarios
from app.workflow.state import WorkflowState
from app.requirement_understanding.schema import RequirementUnderstanding
from app.workflow.graph import ScenarioList, Scenario

# Mock LLMClient that returns predefined scenarios
class MockLLMClient:
    def __init__(self, scenarios_to_return):
        self.scenarios_to_return = scenarios_to_return
    def generate_structured(self, prompt, schema):
        # Ignore prompt, return the predefined scenarios
        if schema == ScenarioList:
            return self.scenarios_to_return
        else:
            raise ValueError(f"Unexpected schema {schema}")

def run_test(requirement, understanding_dict=None, mock_scenarios=None, expect_empty=False, test_name=""):
    """
    understanding_dict: dict to set as requirement_understanding, or None
    mock_scenarios: ScenarioList to return from mocked LLM, or None (will use default)
    expect_empty: if True, expect empty scenarios list
    """
    with patch('app.workflow.graph._get_llm_client') as mock_get_llm:
        # Setup mock LLM client
        if mock_scenarios is None:
            # Default to two simple scenarios
            mock_scenarios = ScenarioList(
                scenarios=[
                    Scenario(scenario_id="s1", scenario_type="functional", title="Test scenario 1", description="Desc 1"),
                    Scenario(scenario_id="s2", scenario_type="negative", title="Test scenario 2", description="Desc 2")
                ]
            )
        mock_llm = MockLLMClient(mock_scenarios)
        mock_get_llm.return_value = mock_llm

        state_dict = {
            "requirement": requirement,
            "requirement_understanding": understanding_dict
        }
        # Remove understanding if None
        if understanding_dict is None:
            del state_dict["requirement_understanding"]
        state = WorkflowState(**state_dict)
        result = generate_test_scenarios(state)
        print(f"{test_name}: result test_scenarios length = {len(result.get('test_scenarios', []))}")
        if expect_empty:
            assert result.get("test_scenarios") == [], f"Expected empty scenarios, got {result.get('test_scenarios')}"
            assert result.get("test_cases") == []
            print(f"  PASS: empty scenarios as expected")
        else:
            assert len(result.get("test_scenarios", [])) > 0, "Expected non-empty scenarios"
            assert result.get("test_cases") == result.get("test_scenarios")
            # Check each scenario has required fields
            for sc in result["test_scenarios"]:
                assert "scenario_id" in sc
                assert "scenario_type" in sc
                assert "title" in sc
                assert "description" in sc
            print(f"  PASS: non-empty scenarios with correct fields")
        return result

print("=== Test A: Login requirement ===")
# Login requirement, understanding testable
run_test(
    requirement="Verify that a user can log in with valid credentials",
    understanding_dict=RequirementUnderstanding(
        feature="Login",
        objective="Allow users to authenticate",
        actors=["User"],
        inputs=["username", "password"],
        preconditions=["User is on login page"],
        expected_behavior="User is redirected to home page",
        constraints=[],
        ambiguities=[],
        status="testable"
    ).dict(),
    mock_scenarios=ScenarioList(
        scenarios=[
            Scenario(scenario_id="login_1", scenario_type="functional", title="Valid login", description="User can log in with correct credentials"),
            Scenario(scenario_id="login_2", scenario_type="negative", title="Invalid password", description="Error shown when password is wrong"),
            Scenario(scenario_id="login_3", scenario_type="negative", title="Invalid username", description="Error shown when username is wrong"),
            Scenario(scenario_id="login_4", scenario_type="boundary", title="Empty username", description="System handles empty username"),
            Scenario(scenario_id="login_5", scenario_type="boundary", title="Empty password", description="System handles empty password")
        ]
    ),
    test_name="Test A"
)

print("\n=== Test B: Hello requirement ===")
run_test(
    requirement="A user can enter a name on the hello page and see a personalized greeting.",
    understanding_dict=RequirementUnderstanding(
        feature="Hello Greeting",
        objective="Display personalized greeting",
        actors=["User"],
        inputs=["name"],
        preconditions=["User is on hello page"],
        expected_behavior="Greeting message displays the entered name",
        constraints=[],
        ambiguities=[],
        status="testable"
    ).dict(),
    mock_scenarios=ScenarioList(
        scenarios=[
            Scenario(scenario_id="hello_1", scenario_type="functional", title="Name entered and greeting shown", description="User enters name and sees greeting with that name"),
            Scenario(scenario_id="hello_2", scenario_type="boundary", title="Empty name", description="System handles empty name input"),
            Scenario(scenario_id="hello_3", scenario_type="functional", title="Special characters in name", description="Greeting works with special characters"),
        ]
    ),
    test_name="Test B"
)

print("\n=== Test C: Paraphrased Hello requirement ===")
run_test(
    requirement="The user inputs their name and receives a customized welcome message.",
    understanding_dict=RequirementUnderstanding(
        feature="Hello Greeting",
        objective="Display personalized greeting",
        actors=["User"],
        inputs=["name"],
        preconditions=["User is on the page"],
        expected_behavior="Welcome message includes the user's name",
        constraints=[],
        ambiguities=[],
        status="testable"
    ).dict(),
    mock_scenarios=ScenarioList(
        scenarios=[
            Scenario(scenario_id="hello_para_1", scenario_type="functional", title="Custom welcome message", description="User inputs name and receives customized welcome"),
            Scenario(scenario_id="hello_para_2", scenario_type="boundary", title="Very long name", description="System handles extremely long name input"),
        ]
    ),
    test_name="Test C"
)

print("\n=== Test D: Cart requirement ===")
run_test(
    requirement="Add a product to the shopping cart and display the updated cart quantity.",
    understanding_dict=RequirementUnderstanding(
        feature="Shopping Cart",
        objective="Allow users to add items and see cart update",
        actors=["User"],
        inputs=["product ID", "quantity"],
        preconditions=["User is on product page"],
        expected_behavior="Cart quantity increases by added quantity",
        constraints=[],
        ambiguities=[],
        status="testable"
    ).dict(),
    mock_scenarios=ScenarioList(
        scenarios=[
            Scenario(scenario_id="cart_1", scenario_type="functional", title="Add single item to cart", description="User adds one product, cart quantity updates"),
            Scenario(scenario_id="cart_2", scenario_type="functional", title="Add multiple items to cart", description="User adds several products, cart reflects total"),
            Scenario(scenario_id="cart_3", scenario_type="boundary", title="Add zero quantity", description="System handles adding zero items"),
            Scenario(scenario_id="cart_4", scenario_type="functional", title="Add item to empty cart", description="Cart shows correct quantity when starting from empty"),
        ]
    ),
    test_name="Test D"
)

print("\n=== Test E: Ambiguous requirement ===")
run_test(
    requirement="Test the page.",
    understanding_dict=RequirementUnderstanding(
        feature="Unknown",
        objective="Unclear what to test",
        actors=[],
        inputs=[],
        preconditions=[],
        expected_behavior="",
        constraints=[],
        ambiguities=["Page not specified", "What aspect to test unclear"],
        status="clarification_needed",
        clarification_reason="Too ambiguous to derive test scenarios"
    ).dict(),
    expect_empty=True,
    test_name="Test E"
)

print("\n=== Test F: Non-software requirement ===")
run_test(
    requirement="Write a poem about the ocean.",
    understanding_dict=RequirementUnderstanding(
        feature="Poem Writing",
        objective="Create a poem about the ocean",
        actors=["Poet"],
        inputs=["inspiration"],
        preconditions=[],
        expected_behavior="A poem is produced",
        constraints=[],
        ambiguities=[],
        status="unsupported"
    ).dict(),
    expect_empty=True,
    test_name="Test F"
)

print("\n=== All tests completed ===")