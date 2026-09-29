#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client that returns exactly what we want to test
class MockLLMClient(LLMClient):
    def generate_structured(self, prompt, schema):
        # For _step_to_selenium_command, return the specific find_element we want to test
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            # Check if this is for the name field
            if "name" in prompt.lower() and ("send" in prompt.lower() or "type" in prompt.lower() or "enter" in prompt.lower()):
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
            else:
                # For other steps, return something reasonable
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "say-hello").click()')
        # For _expected_result_to_assertion, return an assertion
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

# Create TestAutomationAgent with the EXACT parameters specified
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

# Create a minimal test case that will trigger the name field step
test_case = TestCase(
    test_id="tc_verify_001",
    scenario_id="verify_scenario",
    title="Verification Test",
    description="Test to verify navigation works",
    preconditions=["Browser is open"],
    steps=[
        "Enter 'Alice' in the name field"  # This should generate the find_element we want to test
    ],
    test_data=[TestDataItem(key="name", value="Alice")],
    expected_result="Field should contain 'Alice'",
    test_type="functional",
    priority="medium"
)

print("DIRECT VERIFICATION TEST")
print("=" * 50)
print(f"base_url: {agent.base_url}")
print(f"sut_context: {agent.sut_context}")
print(f"Target URL: {agent._build_target_url()}")
print()

# Generate test
print("Generating test...")
file_path = agent.generate_test(test_case)

# Read the generated code
with open(file_path, 'r') as f:
    final_code = f.read()

print("FINAL CODE RETURNED BY AGENT:")
print("=" * 50)
print(final_code)
print("=" * 50)

# Extract target URL from sut_context
expected_url = agent._build_target_url()
print(f"TARGET URL: {expected_url}")

# Check if FINAL CODE HAS DRIVER.GET
has_driver_get = "driver.get(" in final_code
print(f"FINAL CODE HAS DRIVER.GET: {'YES' if has_driver_get else 'NO'}")

if has_driver_get:
    # Find the driver.get line
    lines = final_code.split('\n')
    driver_get_line = None
    for i, line in enumerate(lines):
        if 'driver.get(' in line:
            driver_get_line = i
            break

    if driver_get_line is not None:
        # Extract the URL from the driver.get line
        import re
        match = re.search(r'driver\.get\s*\(\s*["\']([^"\']*)["\']', final_code)
        if match:
            actual_url = match.group(1)
            print(f"  Found driver.get with URL: {actual_url}")
            print(f"  Matches expected URL: {'YES' if actual_url == expected_url else 'NO'}")

# Check if DRIVER.GET BEFORE FIRST FIND_ELEMENT
lines = final_code.split('\n')
driver_get_line_idx = None
first_find_element_line_idx = None

for i, line in enumerate(lines):
    stripped = line.strip()
    # Skip comments and empty lines
    if not stripped or stripped.startswith('#'):
        continue

    if 'driver.get(' in line and driver_get_line_idx is None:
        driver_get_line_idx = i

    if ('find_element' in line or 'find_elements' in line) and first_find_element_line_idx is None:
        first_find_element_line_idx = i

print(f"DRIVER.GET BEFORE FIRST FIND_ELEMENT: {'YES' if driver_get_line_idx is not None and first_find_element_line_idx is not None and driver_get_line_idx < first_find_element_line_idx else 'NO'}")

if driver_get_line_idx is not None and first_find_element_line_idx is not None:
    print(f"  driver.get() at line: {driver_get_line_idx + 1}")
    print(f"  first find_element at line: {first_find_element_line_idx + 1}")
    if driver_get_line_idx < first_find_element_line_idx:
        print(f"  {first_find_element_line_idx - driver_get_line_idx} line(s) between them")
    else:
        print(f"  {driver_get_line_idx - first_find_element_line_idx} line(s) BEFORE (incorrect order)")

# Show the relevant lines
print("\nRELEVANT LINES FROM FINAL CODE:")
print("-" * 30)
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        continue
    if 'driver.get(' in line or 'find_element' in line or 'find_elements' in line:
        print(f"{i+1:3}: {line}")

print("\n" + "="*50)