import pytest
import os
from unittest.mock import Mock, patch

from app.failure_investigation_agent.service import FailureInvestigationAgent
from app.failure_investigation_agent.schema import FailureAnalysis


@patch("app.llm.client.OpenAIClient")
def test_agent_init_default_client(mock_openai_client):
    """Test that the agent initializes with a default OpenAIClient when none provided."""
    mock_openai_client.return_value = Mock()
    agent = FailureInvestigationAgent()
    assert agent.llm_client is not None
    mock_openai_client.assert_called_once()


def test_agent_init_with_client():
    """Test that the agent uses the provided LLM client."""
    mock_client = Mock()
    agent = FailureInvestigationAgent(llm_client=mock_client)
    assert agent.llm_client == mock_client

@patch("langchain_openai.ChatOpenAI.with_structured_output")
def test_investigate_success(mock_with_structured_output):
    """Test successful failure investigation."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    # Setup mock for the LLM client to return a FailureAnalysis instance
    mock_invoke = Mock()
    mock_with_structured_output.return_value.invoke = mock_invoke
    mock_invoke.return_value = FailureAnalysis(
        failure_summary="Test failed due to timeout",
        probable_root_cause="Element took too long to load",
        evidence=["Exception: TimeoutException", "Screenshot shows loading spinner"],
        severity="medium",
        suggested_owner="frontend-team",
        confidence=0.8,
    )

    agent = FailureInvestigationAgent()
    result = agent.investigate(
        requirement="User can submit a form",
        test_case={"test_id": "TC001", "title": "Form Submission", "steps": ["Fill form", "Submit"]},
        generated_test_code="def test_TC001(driver):\n    pass",
        exception={"type": "TimeoutException", "message": "Timeout waiting for element", "traceback": "..."},
        stdout="Test started",
        stderr="",
        screenshot_path="/tmp/screenshot.png",
        execution_metadata={"duration": 5.0},
    )

    assert isinstance(result, FailureAnalysis)
    assert result.failure_summary == "Test failed due to timeout"
    assert result.probable_root_cause == "Element took too long to load"
    assert result.evidence == ["Exception: TimeoutException", "Screenshot shows loading spinner"]
    assert result.severity == "medium"
    assert result.suggested_owner == "frontend-team"
    assert result.confidence == 0.8
    mock_invoke.assert_called_once()

@patch("langchain_openai.ChatOpenAI.with_structured_output")
def test_investigate_retry_then_success(mock_with_structured_output):
    """Test that the agent retries on validation error and then succeeds."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    from pydantic import ValidationError

    mock_invoke = Mock()
    # First call raises ValidationError, second returns valid
    mock_invoke.side_effect = [
        ValidationError.from_exception_data(
            "FailureAnalysis",
            [
                {
                    "type": "missing",
                    "loc": ("failure_summary",),
                    "msg": "Field required",
                    "input": {"probable_root_cause": "test"},
                }
            ],
        ),
        FailureAnalysis(
            failure_summary="Test failed",
            probable_root_cause="Unknown",
            evidence=[],
            severity="low",
            suggested_owner="unknown",
            confidence=0.1,
        ),
    ]
    mock_with_structured_output.return_value.invoke = mock_invoke

    agent = FailureInvestigationAgent()
    result = agent.investigate(
        requirement="Test",
        test_case={},
        generated_test_code="",
        exception={"type": "TestException", "message": "test", "traceback": ""},
    )

    assert result.failure_summary == "Test failed"
    assert mock_invoke.call_count == 2

@patch("langchain_openai.ChatOpenAI.with_structured_output")
def test_investigate_max_retries_exceeded(mock_with_structured_output):
    """Test that the agent raises an error after max retries."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    from pydantic import ValidationError

    mock_invoke = Mock()
    mock_invoke.side_effect = ValidationError.from_exception_data(
        "FailureAnalysis",
        [
            {
                "type": "missing",
                "loc": ("failure_summary",),
                "msg": "Field required",
                "input": {"probable_root_cause": "test"},
            }
        ],
    )
    mock_with_structured_output.return_value.invoke = mock_invoke

    agent = FailureInvestigationAgent()
    with pytest.raises(ValueError, match="Failed to generate valid response after 3 attempts"):
        agent.investigate(
            requirement="Test",
            test_case={},
            generated_test_code="",
            exception={"type": "TestException", "message": "test", "traceback": ""},
        )

    assert mock_invoke.call_count == 3
