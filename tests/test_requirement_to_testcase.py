import pytest
import os
from unittest.mock import Mock, patch

from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase


@patch("app.llm.client.OpenAIClient")
def test_generator_init_default_client(mock_openai_client):
    """Test that the generator initializes with a default OpenAIClient when none provided."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    mock_openai_client.return_value = Mock()
    generator = RequirementToTestCaseGenerator()
    assert generator.llm_client is not None
    mock_openai_client.assert_called_once()


def test_generator_init_with_client():
    """Test that the generator uses the provided LLM client."""
    mock_client = Mock()
    generator = RequirementToTestCaseGenerator(llm_client=mock_client)
    assert generator.llm_client == mock_client

@patch("langchain_openai.ChatOpenAI.with_structured_output")
def test_generator_generate_success(mock_with_structured_output):
    """Test successful generation of a test case."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    # Setup mock
    mock_invoke = Mock()
    mock_with_structured_output.return_value.invoke = mock_invoke
    mock_invoke.return_value = TestCase(
        test_id="TC001",
        title="Test Title",
        description="Test Description",
        preconditions=["Precondition 1"],
        steps=["Step 1", "Step 2"],
        expected_result="Expected Result",
        test_type="functional",
        priority="high",
    )

    generator = RequirementToTestCaseGenerator()
    requirement = "The system shall allow users to log in."
    result = generator.generate(requirement)

    assert isinstance(result, TestCase)
    assert result.test_id == "TC001"
    assert result.title == "Test Title"
    assert result.description == "Test Description"
    assert result.preconditions == ["Precondition 1"]
    assert result.steps == ["Step 1", "Step 2"]
    assert result.expected_result == "Expected Result"
    assert result.test_type == "functional"
    assert result.priority == "high"
    mock_invoke.assert_called_once()

@patch("langchain_openai.ChatOpenAI.with_structured_output")
def test_generator_generate_retry_then_success(mock_with_structured_output):
    """Test that the generator retries on validation error and then succeeds."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    from pydantic import ValidationError

    mock_invoke = Mock()
    # First call raises ValidationError, second returns valid
    mock_invoke.side_effect = [
        ValidationError.from_exception_data(
            "TestCase",
            [
                {
                    "type": "missing",
                    "loc": ("test_id",),
                    "msg": "Field required",
                    "input": {"title": "Test"},
                }
            ],
        ),
        TestCase(
            test_id="TC002",
            title="Test Title",
            description="Test Description",
            preconditions=[],
            steps=["Step 1"],
            expected_result="Expected Result",
            test_type="functional",
            priority="medium",
        ),
    ]
    mock_with_structured_output.return_value.invoke = mock_invoke

    generator = RequirementToTestCaseGenerator()
    requirement = "The system shall allow users to log in."
    result = generator.generate(requirement)

    assert result.test_id == "TC002"
    assert mock_invoke.call_count == 2

@patch("langchain_openai.ChatOpenAI.with_structured_output")
def test_generator_generate_max_retries_exceeded(mock_with_structured_output):
    """Test that the generator raises an error after max retries."""
    os.environ["OPENAI_API_KEY"] = "dummy-test-key"
    from pydantic import ValidationError

    mock_invoke = Mock()
    mock_invoke.side_effect = ValidationError.from_exception_data(
        "TestCase",
        [
            {
                "type": "missing",
                "loc": ("test_id",),
                "msg": "Field required",
                "input": {"title": "Test"},
            }
        ],
    )
    mock_with_structured_output.return_value.invoke = mock_invoke

    generator = RequirementToTestCaseGenerator()
    requirement = "The system shall allow users to log in."

    with pytest.raises(ValueError, match="Failed to generate valid response after 3 attempts"):
        generator.generate(requirement)

    assert mock_invoke.call_count == 3
