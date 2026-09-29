import pytest
from unittest.mock import Mock, patch

from app.test_automation_agent.service import TestAutomationAgent
from app.requirement_to_testcase.schema import TestCase


@patch("app.llm.client.OpenAIClient")
def test_agent_init_default_client(mock_openai_client):
    """Test that the agent initializes with a default OpenAIClient when none provided."""
    mock_openai_client.return_value = Mock()
    agent = TestAutomationAgent()
    assert agent.llm_client is not None
    mock_openai_client.assert_called_once()


def test_agent_init_with_client():
    """Test that the agent uses the provided LLM client."""
    mock_client = Mock()
    agent = TestAutomationAgent(llm_client=mock_client)
    assert agent.llm_client == mock_client

@patch("app.llm.client.OpenAIClient")
def test_generate_test_success(mock_openai_client):
    """Test successful generation of a test file."""
    # Setup mock for the LLM client
    mock_instance = Mock()
    # We need to mock the generate_structured method to return a CodeLine or AssertionLine
    # For simplicity, we'll have it return a fixed string for steps and assertions.
    # We'll create a mock that returns a Pydantic model with a code/assertion field.
    from pydantic import BaseModel

    class CodeLine(BaseModel):
        code: str

    class AssertionLine(BaseModel):
        assertion: str

    # Configure the mock to return specific values for different prompts
    def mock_generate_structured(prompt, schema):
        if "Convert the following test step" in prompt:
            # Return a simple Selenium command for the step
            return schema(code="driver.get('https://example.com')")
        elif "Convert the following expected result" in prompt:
            # Return an assertion
            return schema(assertion="assert 'Example' in driver.title")
        else:
            # Fallback
            return schema(code="# TODO")

    mock_instance.generate_structured.side_effect = mock_generate_structured
    mock_openai_client.return_value = mock_instance

    # Create a sample TestCase
    test_case = TestCase(
        test_id="TC001",
        title="Test Title",
        description="Test Description",
        preconditions=[],
        steps=["Navigate to the example website"],
        expected_result="The page title should contain 'Example'",
        test_type="functional",
        priority="high",
    )

    agent = TestAutomationAgent()
    file_path = agent.generate_test(test_case)

    # Check that the file was created
    assert file_path.endswith("TC001.py")
    # Read the file and check its content
    with open(file_path, "r") as f:
        content = f.read()

    # Check that the content contains the expected elements
    assert "def test_TC001(driver):" in content
    assert "driver.get('https://example.com')" in content
    assert "assert 'Example' in driver.title" in content
    # Clean up the generated file
    import os
    os.remove(file_path)

@patch("app.llm.client.OpenAIClient")
def test_generate_test_invalid_code_retry(mock_openai_client):
    """Test that the agent retries on invalid code generation."""
    from pydantic import BaseModel

    class CodeLine(BaseModel):
        code: str

    class AssertionLine(BaseModel):
        assertion: str

    # First call returns unsafe code, second returns safe
    mock_instance = Mock()
    mock_instance.generate_structured.side_effect = [
        # First call for step: returns unsafe code (with import)
        CodeLine(code="import os"),
        # Second call for step: returns safe code
        CodeLine(code="driver.get('https://example.com')"),
        # For expected result: returns safe assertion
        AssertionLine(assertion="assert True"),
    ]
    mock_openai_client.return_value = mock_instance

    test_case = TestCase(
        test_id="TC002",
        title="Test Title",
        description="Test Description",
        preconditions=[],
        steps=["Do something"],
        expected_result="Something happens",
        test_type="functional",
        priority="high",
    )

    agent = TestAutomationAgent()
    file_path = agent.generate_test(test_case)

    # Check that the file was created and contains the safe code (second attempt)
    with open(file_path, "r") as f:
        content = f.read()
    assert "import os" not in content  # The unsafe code should not be present
    assert "driver.get('https://example.com')" in content
    # Clean up
    import os
    os.remove(file_path)

@patch("app.llm.client.OpenAIClient")
def test_generate_test_max_retries_exceeded(mock_openai_client):
    """Test that the agent falls back to a placeholder after max retries."""
    from pydantic import BaseModel

    class CodeLine(BaseModel):
        code: str

    class AssertionLine(BaseModel):
        assertion: str

    # All calls return unsafe code
    mock_instance = Mock()
    mock_instance.generate_structured.side_effect = [
        CodeLine(code="import os"),  # unsafe
        CodeLine(code="subprocess.call(['ls']"),  # unsafe
        CodeLine(code="eval('bad')"),  # unsafe
        AssertionLine(assertion="import os"),  # unsafe assertion
    ]
    mock_openai_client.return_value = mock_instance

    test_case = TestCase(
        test_id="TC003",
        title="Test Title",
        description="Test Description",
        preconditions=[],
        steps=["Do something"],
        expected_result="Something happens",
        test_type="functional",
        priority="high",
    )

    agent = TestAutomationAgent()
    file_path = agent.generate_test(test_case)

    # Check that the file contains the fallback placeholder
    with open(file_path, "r") as f:
        content = f.read()
    assert "# TODO: Implement step: Do something" in content
    assert "assert True, \"Expected result verification not implemented\"" in content
    # Clean up
    import os
    os.remove(file_path)

@patch("app.llm.client.OpenAIClient")
def test_validate_code(mock_openai_client):
    """Test the code validation method."""
    mock_openai_client.return_value = Mock()
    agent = TestAutomationAgent()
    # Valid code
    agent._validate_code("def foo(): pass")
    # Invalid code
    with pytest.raises(SyntaxError):
        agent._validate_code("def foo(: pass")


def test_fix_invalid_code_prompt_includes_authoritative_sut_context():
    class RepairClient:
        prompt = None

        def generate_structured(self, prompt, schema):
            self.prompt = prompt
            return schema(code='assert driver.find_element(By.CSS_SELECTOR, "#greeting").text == "Hello, Stranger!"')

    client = RepairClient()
    agent = TestAutomationAgent(
        llm_client=client,
        base_url="http://127.0.0.1:8001",
        sut_context={
            "route": "/hello",
            "name_selector": "#name",
            "submit_selector": "#say-hello",
            "greeting_selector": "#greeting",
        },
    )
    test_case = TestCase(
        test_id="tc_empty_name",
        scenario_id="empty_name",
        title="Empty name fallback",
        description="Submit an empty name and inspect the greeting.",
        steps=["Submit the form without a name"],
        expected_result="Hello, Stranger! is displayed",
        test_type="negative",
        priority="medium",
    )

    repaired = agent._fix_invalid_code(
        test_case,
        "test_tc_empty_name",
        'assert driver.find_element(By.CSS_SELECTOR, "#error").text',
        'Selector "#error" is not grounded. Authorized selector: "#greeting".',
    )

    assert '#greeting' in client.prompt
    assert '#error' in client.prompt
    assert 'Use only selectors explicitly present' in client.prompt
    assert 'VALIDATION ERROR' in client.prompt
    assert '#greeting' in repaired


def test_step_assertion_cannot_conflict_with_final_expected_result():
    from pydantic import BaseModel

    class CodeLine(BaseModel):
        code: str

    class AssertionLine(BaseModel):
        assertion: str

    class ConflictingAssertionClient:
        def generate_structured(self, prompt, schema):
            if "Convert the following test step" in prompt:
                return schema(
                    code='assert driver.find_element(By.CSS_SELECTOR, "#greeting").text == "Hello, <name>!"'
                )
            return schema(
                assertion='assert driver.find_element(By.CSS_SELECTOR, "#greeting").text == "Hello, " + "A" * 256 + "!"'
            )

    test_case = TestCase(
        test_id="tc_long_name",
        scenario_id="maximum_name",
        route="/hello",
        title="Maximum length name",
        description="Show all 256 name characters",
        steps=["Verify the greeting equals Hello, <name>!"],
        expected_result="The greeting contains all 256 submitted characters",
        test_type="boundary",
        priority="medium",
    )
    agent = TestAutomationAgent(
        llm_client=ConflictingAssertionClient(),
        base_url="http://127.0.0.1:8001",
        sut_context={"route": "/hello", "greeting_selector": "#greeting"},
    )

    code = agent._generate_test_code(test_case, "test_tc_long_name")

    assert '"Hello, <name>!"' not in code
    assert '"A" * 256' in code
