import os
from unittest.mock import Mock, patch

from app.regression_test_agent.service import RegressionTestAgent
from app.regression_test_agent.schema import RegressionTestCase


def test_regression_test_agent_init_default_client():
    """Test that the agent initializes with a default OpenAIClient when none provided."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    agent = RegressionTestAgent()
    assert agent.llm_client is not None


def test_regression_test_agent_init_with_client():
    """Test that the agent uses the provided LLM client."""
    mock_client = Mock()
    agent = RegressionTestAgent(llm_client=mock_client)
    assert agent.llm_client == mock_client


def test_regression_test_agent_generate_returns_regression_test_case():
    """Test that the generate method returns a RegressionTestCase."""
    agent = RegressionTestAgent()
    requirement = "The system shall allow users to log in."
    test_case = {"test_id": "TC001", "title": "Login Test", "description": "Test login", "steps": ["Enter credentials"], "expected_result": "Login successful", "priority": "high"}
    result = agent.generate(requirement=requirement, test_case=test_case)
    assert isinstance(result, RegressionTestCase)
    assert result.test_id == "REG001"
    assert result.title == "Regression test for requirement"
    assert result.description == f"Regression test to ensure the requirement '{requirement}' continues to work."
    assert result.steps == [
        "1. Navigate to the application",
        "2. Perform the actions described in the requirement",
        "3. Verify the expected outcome"
    ]
    assert result.expected_result == "The application behaves as specified in the requirement."
    assert result.priority == "medium"
    # Check optional fields
    assert result.preconditions == []
    assert result.test_type == "regression"