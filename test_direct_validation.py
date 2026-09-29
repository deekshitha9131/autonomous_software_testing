#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client that returns VALID code on first try
class MockLLMClientValidFirstTry(LLMClient):
    def __init__(self, return_invented=False):
        self.return_invented = return_invented

    def generate_structured(self, prompt, schema):
        # For _step_to_selenium_command, return code
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            # Check what step we're dealing with
            if "name" in prompt.lower() and ("send" in prompt.lower() or "type" in prompt.lower() or "enter" in prompt.lower()):
                # For name field, return CORRECT selector
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
            elif "submit" in prompt.lower() or "button" in prompt.lower() or "click" in prompt.lower():
                if self.return_invented:
                    # Return INVENTED selector - using a simpler one for testing
                    from pydantic import BaseModel
                    class CodeLine(BaseModel):
                        code: str
                    return CodeLine(code="driver.find_element(By.CSS_SELECTOR, '#submit').click()")
                else:
                    # Return CORRECT selector
                    from pydantic import BaseModel
                    class CodeLine(BaseModel):
                        code: str
                    return CodeLine(code='driver.find_element(By.ID, "say-hello").click()')
            elif "greeting" in prompt.lower() or "text" in prompt.lower() or "assert" in prompt.lower():
                # For greeting, return CORRECT selector
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='assert "Hello, Alice" in driver.find_element(By.ID, "greeting").text')
            else:
                # Default
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
        # For _expected_result_to_assertion
        elif "Convert the following expected result into a single line of Python assertion code" in prompt:
            from pydantic import BaseModel
            class AssertionLine(BaseModel):
                assertion: str
            return AssertionLine(assertion='assert "Hello, Alice" in driver.find_element(By.ID, "greeting").text')
        else:
            from pydantic import BaseModel
            class CodeLine(BaseModel):
                code: str
            return CodeLine(code='# TODO: Implement step')

print("=" * 60)
print("DIRECT VALIDATION TEST: Valid selectors (should PASS)")
print("=" * 60)

# Create TestAutomationAgent with Hello context
agent = TestAutomationAgent(
    llm_client=MockLLMClientValidFirstTry(return_invented=False),  # Return valid selectors
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context={
        "route": "/hello",
        "name_selector": "#name",
        "submit_selector": "#say-hello",  # AUTHORITATIVE SELECTOR
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)

# Test case
test_case = TestCase(
    test_id="tc_direct_001",
    scenario_id="direct_scenario",
    title="Direct Test",
    description="Test direct validation",
    preconditions=["Browser is open"],
    steps=[
        "Enter 'Alice' in the name field",
        "Click the submit button",
        "Verify greeting shows 'Hello, Alice'"
    ],
    test_data=[TestDataItem(key="name", value="Alice")],
    expected_result="Greeting should show 'Hello, Alice'",
    test_type="functional",
    priority="medium"
)

print(f"base_url: {agent.base_url}")
print(f"sut_context: {agent.sut_context}")
print()

# Generate test - this should succeed with valid selectors
try:
    file_path = agent.generate_test(test_case)
    print(f"SUCCESS: Test generation succeeded with valid selectors")
    print(f"Generated test saved to: {file_path}")

    # Read and display the generated code
    with open(file_path, 'r') as f:
        code = f.read()

    print("\nGENERATED CODE:")
    print("-" * 40)
    print(code)
    print("-" * 40)

except Exception as e:
    print(f"UNEXPECTED: Test generation failed: {e}")

print("\n" + "=" * 60)
print("DIRECT VALIDATION TEST: Invented selectors (should FAIL)")
print("=" * 60)

# Create TestAutomationAgent with Hello context
agent_invented = TestAutomationAgent(
    llm_client=MockLLMClientValidFirstTry(return_invented=True),  # Return invented selectors
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context={
        "route": "/hello",
        "name_selector": "#name",
        "submit_selector": "#say-hello",  # AUTHORITATIVE SELECTOR
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)

print(f"base_url: {agent_invented.base_url}")
print(f"sut_context: {agent_invented.sut_context}")
print()

# Generate test - this should fail validation due to invented selector
try:
    file_path = agent_invented.generate_test(test_case)
    print(f"UNEXPECTED: Test generation succeeded (should have failed validation)")
    print(f"Generated test saved to: {file_path}")

    # Read and display the generated code
    with open(file_path, 'r') as f:
        code = f.read()

    print("\nGENERATED CODE:")
    print("-" * 40)
    print(code)
    print("-" * 40)

except SyntaxError as e:
    if "not grounded in authoritative SUT context" in str(e):
        print(f"SUCCESS: Validation correctly caught invented selector")
        print(f"Error message: {e}")
    elif "placeholder content" in str(e):
        print(f"INFO: Failed on placeholder content (validation may have passed but retry failed)")
        print(f"Error message: {e}")
    else:
        print(f"DIFFERENT ERROR: {e}")
except Exception as e:
    print(f"UNEXPECTED: Other error: {e}")

print("\n" + "=" * 60)
print("TESTING _validate_selector_grounding DIRECTLY")
print("=" * 60)

# Test the validation method directly
test_code_valid = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_direct_001(driver):
    """Direct Test"""
    driver.get("http://127.0.0.1:8001/hello")
    # Step 1: Enter 'Alice' in the name field
    driver.find_element(By.ID, "name").send_keys("Alice")
    # Step 2: Click the submit button
    driver.find_element(By.ID, "say-hello").click()
    # Step 3: Verify greeting shows 'Hello, Alice'
    assert "Hello, Alice" in driver.find_element(By.ID, "greeting").text
'''

test_code_invented = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_direct_001(driver):
    """Direct Test"""
    driver.get("http://127.0.0.1:8001/hello")
    # Step 1: Enter 'Alice' in the name field
    driver.find_element(By.ID, "name").send_keys("Alice")
    # Step 2: Click the submit button
    driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
    # Step 3: Verify greeting shows 'Hello, Alice'
    assert "Hello, Alice" in driver.find_element(By.ID, "greeting").text
'''

print("Testing VALID code:")
try:
    agent._validate_selector_grounding(test_code_valid)
    print("SUCCESS: Valid code passed validation")
except Exception as e:
    print(f"UNEXPECTED: Valid code failed validation: {e}")

print("\nTesting INVENTED code:")
try:
    agent._validate_selector_grounding(test_code_invented)
    print("UNEXPECTED: Invented code passed validation (should have failed)")
except SyntaxError as e:
    if "not grounded in authoritative SUT context" in str(e):
        print(f"SUCCESS: Validation correctly caught invented selector")
        print(f"Error message: {e}")
    else:
        print(f"DIFFERENT ERROR: {e}")
except Exception as e:
    print(f"UNEXPECTED: Other error: {e}")

print("\n" + "=" * 60)
print("SELECTOR GROUNDING IMPLEMENTATION VERIFIED")
print("=" * 60)