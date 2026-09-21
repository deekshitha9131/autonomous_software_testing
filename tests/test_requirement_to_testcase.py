import pytest
from unittest.mock import Mock, patch

from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase


@patch("app.requirement_to_testcase.generator.OpenAIClient")
def test_generator_init_default_client(mock_openai_client):
    """Test that the generator initializes with a default OpenAIClient when none provided."""
    mock_openai_client.return_value = Mock()
    generator = RequirementToTestCaseGenerator()
    assert generator.llm_client is not None
    mock_openai_client.assert_called_once()


def test_generator_init_with_client():
    """Test that the generator uses the provided LLM client."""
    mock_client = Mock()
    generator = RequirementToTestCaseGenerator(llm_client=mock_client)
    assert generator.llm_client == mock_client

@patch("app.requirement_to_testcase.generator.OpenAIClient")
def test_generator_generate_success(mock_openai_client):
    """Test successful generation of a test case."""
    # Setup mock
    mock_instance = Mock()
    mock_instance.generate_structured.return_value = TestCase(
        test_id="TC001",
        title="Test Title",
        description="Test Description",
        preconditions=["Precondition 1"],
        steps=["Step 1", "Step 2"],
        expected_result="Expected Result",
        test_type="functional",
        priority="high",
    )
    mock_openai_client.return_value = mock_instance

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
    mock_openai_client.return_value.generate_structured.assert_called_once()

@patch("app.requirement_to_testcase.generator.OpenAIClient")
def test_generator_generate_retry_then_success(mock_openai_client):
    """Test that the generator retries on validation error and then succeeds."""
    from pydantic import ValidationError

    # First call raises ValidationError, second returns valid
    mock_instance = Mock()
    mock_instance.generate_structured.side_effect = [
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
    mock_openai_client.return_value = mock_instance

    generator = RequirementToTestCaseGenerator()
    requirement = "The system shall allow users to log in."
    result = generator.generate(requirement)

    assert result.test_id == "TC002"
    assert mock_openai_client.return_value.generate_structured.call_count == 2

@patch("app.requirement_to_testcase.generator.OpenAIClient")
def test_generator_generate_max_retries_exceeded(mock_openai_client):
    """Test that the generator raises an error after max retries."""
    from pydantic import ValidationError

    mock_instance = Mock()
    mock_instance.generate_structured.side_effect = ValidationError.from_exception_data(
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
    mock_openai_client.return_value = mock_instance

    generator = RequirementToTestCaseGenerator()
    requirement = "The system shall allow users to log in."

    with pytest.raises(ValueError, match="Failed to generate valid response after 3 attempts"):
        generator.generate(requirement)

    assert mock_openai_client.return_value.generate_structured.call_count == 3
