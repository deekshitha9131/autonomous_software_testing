#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch
from pydantic import BaseModel

# Set the environment variables for Groq
os.environ["LLM_PROVIDER"] = "groq"
os.environ["GROQ_API_KEY"] = "dummy-key-for-testing"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b"

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import build_workflow
from app.workflow.state import WorkflowState
from app.workflow.graph import ScenarioList, Scenario
from app.requirement_to_testcase.schema import TestCase

# Define the schemas used by TestAutomationAgent internally
class CodeLine(BaseModel):
    code: str

class AssertionLine(BaseModel):
    assertion: str

class FixedCode(BaseModel):
    code: str

class MockLLMClient:
    """Mock LLM client that returns predefined responses based on the schema."""

    def generate_structured(self, prompt: str, schema: type[BaseModel]):
        # Debug: print what's being requested
        print(f"  Mock LLM called with schema: {schema.__name__}")
        print(f"  Prompt preview: {prompt[:200]}...")

        if schema == ScenarioList:
            # Return predefined scenarios for the hello requirement
            print("  Returning mock scenarios")
            return ScenarioList(
                scenarios=[
                    Scenario(
                        scenario_id="hello_1",
                        scenario_type="functional",
                        title="Enter name and see personalized greeting",
                        description="User enters a name in the input field and submits the form to see a personalized greeting"
                    )
                ]
            )
        elif schema == TestCase:
            # Return a predefined test case with all required fields
            print("  Returning mock test case")
            return TestCase(
                test_id="tc_hello_1",
                scenario_id="hello_1",  # Must match the scenario_id from which this was generated
                title="Enter name and see personalized greeting",
                description="User enters a name in the input field and submits the form to see a personalized greeting",
                preconditions=["User is on the hello page"],
                steps=[
                    "Enter 'Alice' into the name input field",
                    "Click the submit button"
                ],
                test_data={"name": "Alice"},
                expected_result="The greeting displays 'Hello, Alice!'",
                test_type="functional",
                priority="high"
            )
        elif schema == CodeLine:
            # Return a Selenium command based on the step in the prompt
            print("  Returning mock Selenium command")
            # For TestAutomationAgent steps, we need to parse the step and return appropriate Selenium
            if "Enter 'Alice' into the name input field" in prompt:
                result = CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
                print(f"  Returning: {result}")
                return result
            elif "Click the submit button" in prompt:
                result = CodeLine(code='driver.find_element(By.ID, "say-hello").click()')
                print(f"  Returning: {result}")
                return result
            elif "Navigate to" in prompt and "hello page" in prompt:
                result = CodeLine(code='driver.get("http://127.0.0.1:8001/hello")')
                print(f"  Returning: {result}")
                return result
            else:
                # Generic fallback - try to extract step and generate appropriate command
                if "input field" in prompt and "Alice" in prompt:
                    result = CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
                elif "submit button" in prompt or "Click" in prompt:
                    result = CodeLine(code='driver.find_element(By.ID, "say-hello").click()')
                else:
                    result = CodeLine(code='driver.get("http://127.0.0.1:8001/hello")')
                print(f"  Returning (generic): {result}")
                return result
        elif schema == AssertionLine:
            # Return an assertion based on the expected result in the prompt
            print("  Returning mock assertion")
            if "Hello, Alice!" in prompt:
                result = AssertionLine(assertion='assert "Hello, Alice!" in driver.page_source')
                print(f"  Returning: {result}")
                return result
            elif "greeting" in prompt.lower() and "hello" in prompt.lower():
                result = AssertionLine(assertion='assert "Hello, Alice!" in driver.page_source')
                print(f"  Returning: {result}")
                return result
            else:
                result = AssertionLine(assertion='assert True  # Placeholder assertion')
                print(f"  Returning: {result}")
                return result
        elif schema == FixedCode:
            # For fixing invalid code, just return a simple valid test
            print("  Returning mock fixed code")
            return FixedCode(code='''import pytest
from selenium.webdriver.common.by import By

def test_tc_hello_1(driver):
    """Enter name and see personalized greeting
    User enters a name in the input field and submits the form to see a personalized greeting"""
    # Step 1: Enter 'Alice' into the name input field
    driver.find_element(By.ID, "name").send_keys("Alice")

    # Step 2: Click the submit button
    driver.find_element(By.ID, "say-hello").click()

    # Expected result: The greeting displays 'Hello, Alice!'
    assert "Hello, Alice!" in driver.page_source
''')
        else:
            # Fallback for any other schema
            print(f"  Unknown schema {schema.__name__}, returning empty instance")
            return schema()

def test_hello_requirement():
    """Test the hello page requirement with mocked LLM calls"""
    requirement = "A user can enter a name on the hello page and see a personalized greeting."

    print(f"Testing requirement: {requirement}")
    print("=" * 80)

    # Initialize state with the requirement AND SUT context
    initial_state = {
        "requirement": requirement,
        "base_url": "http://127.0.0.1:8001",
        "sut_id": "demo-app",
        "sut_context": {
            "route": "/hello",
            "name_selector": "#name",
            "submit_selector": "#say-hello",
            "greeting_selector": "#greeting"
        },
        "test_data": {"name": "Alice"}
    }

    try:
        # Mock the _get_llm_client function to return our mock LLM client
        with patch('app.workflow.graph._get_llm_client') as mock_get_llm:
            mock_llm = MockLLMClient()
            mock_get_llm.return_value = mock_llm

            # Build and run the workflow
            print("Building workflow...")
            workflow = build_workflow()
            print("Running workflow...")
            result = workflow.invoke(initial_state)

        print("\n" + "=" * 80)
        print("Workflow completed!")
        print(f"Current phase: {result.get('current_phase')}")

        # Check workflow status
        workflow_status = result.get('workflow_status', {})
        if workflow_status:
            print(f"Workflows completed: {list(workflow_status.keys())}")

        # Check generated test cases (plural) - these are actually the scenarios
        if result.get('test_cases'):
            print(f"\nGenerated {len(result['test_cases'])} scenario(s) from test_scenarios:")
            for i, tc in enumerate(result['test_cases']):
                print(f"  Scenario {i+1}: {tc.get('title', 'Unknown')}")
                print(f"    Scenario ID: {tc.get('scenario_id')}")
                print(f"    Type: {tc.get('scenario_type', 'Unknown')}")
                print(f"    Description: {tc.get('description', 'None')[:100]}...")
        else:
            print("\nNo scenarios generated")

        # Check the single generated test case (this is what generate_test_case produces)
        if result.get('test_case'):
            print(f"\nSingle generated test case:")
            tc = result['test_case']
            print(f"  ID: {tc.get('test_id')}")
            print(f"  Title: {tc.get('title')}")
            print(f"  Description: {tc.get('description')}")
            print(f"  Scenario ID: {tc.get('scenario_id')}")
            print(f"  Preconditions: {tc.get('preconditions', [])}")
            print(f"  Steps: {tc.get('steps', [])}")
            print(f"  Test Data: {tc.get('test_data', {})}")
            print(f"  Expected Result: {tc.get('expected_result')}")
            print(f"  Test Type: {tc.get('test_type')}")
            print(f"  Priority: {tc.get('priority')}")
        else:
            print("\nNo single test case generated")

        # Check if any Selenium tests were generated
        if result.get('generated_test_path'):
            print(f"\nGenerated Selenium test file:")
            print(f"  Path: {result['generated_test_path']}")
            if result.get('generated_test_code'):
                print(f"  Content:")
                print(result['generated_test_code'])
        else:
            print("\nNo Selenium test generated")

        # Check if we got to test execution
        if result.get('execution_results'):
            print(f"\nExecution results: {len(result['execution_results'])} test(s) executed")
            for i, exec_result in enumerate(result['execution_results']):
                print(f"  Test {i+1}: {exec_result.get('test_id', 'Unknown')} - Status: {exec_result.get('status', 'Unknown')}")
                if exec_result.get('error_message'):
                    print(f"    Error: {exec_result['error_message']}")
                if exec_result.get('stdout'):
                    print(f"    STDOUT: {exec_result['stdout'][:200]}...")
                if exec_result.get('stderr'):
                    print(f"    STDERR: {exec_result['stderr'][:200]}...")
        else:
            print("\nNo execution results found - workflow may have stopped before execution phase")

        # Check for any errors
        if result.get('errors'):
            print(f"\nErrors encountered: {result['errors']}")

        return result

    except Exception as e:
        print(f"\nError running workflow: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_hello_requirement()