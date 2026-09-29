#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client that returns predictable outputs
class MockLLMClient(LLMClient):
    def generate_structured(self, prompt, schema):
        # For _step_to_selenium_command, return a find_element command
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            # Extract the step from prompt to determine what to return
            if "name" in prompt.lower() and ("send" in prompt.lower() or "type" in prompt.lower() or "enter" in prompt.lower()):
                # Return a find_element command for name field
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
            elif "submit" in prompt.lower() or "button" in prompt.lower() or "click" in prompt.lower():
                # Return a click command for submit button
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "say-hello").click()')
            elif "greeting" in prompt.lower() or "text" in prompt.lower() or "assert" in prompt.lower():
                # Return an assertion for greeting
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='assert "Hello, Alice" in driver.find_element(By.ID, "greeting").text')
            else:
                # Default fallback
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
        # For _expected_result_to_assertion, return an assertion
        elif "Convert the following expected result into a single line of Python assertion code" in prompt:
            from pydantic import BaseModel
            class AssertionLine(BaseModel):
                assertion: str
            return AssertionLine(assertion='assert "Hello, Alice" in driver.find_element(By.ID, "greeting").text')
        else:
            # Fallback
            from pydantic import BaseModel
            class CodeLine(BaseModel):
                code: str
            return CodeLine(code='# TODO: Implement step')

# Create test case
test_case = TestCase(
    test_id="tc_hello_001",
    scenario_id="hello_scenario",
    title="Hello Test",
    description="Test the hello functionality",
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

# Create TestAutomationAgent
agent = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context={
        "route": "/hello",
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)

# Generate test
print("Generating test...")
file_path = agent.generate_test(test_case)
print(f"Generated test saved to: {file_path}")

# Read and display the generated code
with open(file_path, 'r') as f:
    code = f.read()

print("\n" + "="*60)
print("GENERATED TEST CODE:")
print("="*60)
print(code)
print("="*60)

# Check if driver.get appears before first find_element
lines = code.split('\n')
driver_get_line = None
first_find_element_line = None

for i, line in enumerate(lines):
    stripped = line.strip()
    # Skip comments and empty lines for detection
    if not stripped or stripped.startswith('#'):
        continue

    if 'driver.get(' in line and driver_get_line is None:
        driver_get_line = i
        print(f"Found driver.get at line {i+1}: {line}")

    if ('find_element' in line or 'find_elements' in line) and first_find_element_line is None:
        first_find_element_line = i
        print(f"First find_element/find_elements at line {i+1}: {line}")

print("\n" + "="*60)
print("ANALYSIS:")
print("="*60)
if driver_get_line is not None and first_find_element_line is not None:
    if driver_get_line < first_find_element_line:
        print("✓ PASS: driver.get() appears BEFORE first find_element")
    else:
        print("✗ FAIL: driver.get() appears AFTER first find_element")
elif driver_get_line is None:
    print("✗ FAIL: No driver.get() found in generated code")
else:
    print("? INFO: No find_element/find_elements found in generated code")

# Also check the specific URL
expected_url = 'http://127.0.0.1:8001/hello'
if expected_url in code:
    print(f"✓ PASS: Expected URL '{expected_url}' found in code")
else:
    print(f"✗ FAIL: Expected URL '{expected_url}' NOT found in code")

print("\n" + "="*60)
print("TARGET URL: http://127.0.0.1:8001/hello")
print("="*60)