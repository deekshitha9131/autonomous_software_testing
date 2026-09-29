#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client that returns the exact problematic output
class MockLLMClient(LLMClient):
    def generate_structured(self, prompt, schema):
        # For _step_to_selenium_command, always return the problematic find_element
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            from pydantic import BaseModel
            class CodeLine(BaseModel):
                code: str
            return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
        # For _expected_result_to_assertion, return a simple assertion
        elif "Convert the following expected result into a single line of Python assertion code" in prompt:
            from pydantic import BaseModel
            class AssertionLine(BaseModel):
                assertion: str
            return AssertionLine(assertion='assert True')
        else:
            from pydantic import BaseModel
            class CodeLine(BaseModel):
                code: str
            return CodeLine(code='# TODO: Implement step')

# Create TestAutomationAgent with MISSING 'route' key in sut_context
# This simulates the failure case where _build_target_url() returns None
agent = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url="http://127.0.0.1:8001",  # This is valid
    sut_id="hello_sut",
    sut_context={  # MISSING 'route' key - this is the problem
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting"
        # Note: no 'route' key here
    },
    test_data=[{"key": "name", "value": "Alice"}]
)

# Test case
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

print("TESTING FAILURE CASE: sut_context missing 'route' key")
print("=" * 60)
print(f"base_url: {agent.base_url}")
print(f"sut_context: {agent.sut_context}")
print(f"_build_target_url() returns: {agent._build_target_url()}")
print()

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

# Check if driver.get appears
if "driver.get(" in code:
    print("\n✓ UNEXPECTED: driver.get() FOUND in generated code")
    # Find the line
    lines = code.split('\n')
    for i, line in enumerate(lines):
        if 'driver.get(' in line:
            print(f"  Found at line {i+1}: {line.strip()}")
else:
    print("\n✓ EXPECTED: driver.get() NOT FOUND in generated code")
    print("  This confirms the failure case!")

# Check what the first interaction is
lines = code.split('\n')
first_interaction_line = None
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        continue
    if 'find_element' in line or 'find_elements' in line:
        first_interaction_line = i
        break

if first_interaction_line is not None:
    print(f"\nFirst interaction: line {first_interaction_line+1}: {lines[first_interaction_line].strip()}")
    if "send_keys" in lines[first_interaction_line] and '"name"' in lines[first_interaction_line]:
        print("  This matches the user's reported failure!")
    else:
        print("  This is a different interaction than reported")
else:
    print("\nNo find_element/find_elements found in generated code")

print("\n" + "="*60)
print("ROOT CAUSE ANALYSIS:")
print("="*60)
print("When sut_context is missing the 'route' key:")
print("1. _build_target_url() returns None (because route is None)")
print("2. In generate_test(): if target_url: evaluates to False")
print("3. Therefore _ensure_navigation() is NEVER called")
print("4. No driver.get() is added to the test code")
print("5. First interaction happens without navigation → NoSuchElementException")
print("="*60)