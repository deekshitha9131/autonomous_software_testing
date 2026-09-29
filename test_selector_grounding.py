#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client that returns code with INVENTED selectors
class MockLLMClientInventedSelector(LLMClient):
    def generate_structured(self, prompt, schema):
        # For _step_to_selenium_command, return code with INVENTED selector
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            # Check what step we're dealing with
            if "name" in prompt.lower() and ("send" in prompt.lower() or "type" in prompt.lower() or "enter" in prompt.lower()):
                # For name field, return CORRECT selector (this should work)
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                return CodeLine(code='driver.find_element(By.ID, "name").send_keys("Alice")')
            elif "submit" in prompt.lower() or "button" in prompt.lower() or "click" in prompt.lower():
                # FOR SUBMIT BUTTON: Return INVENTED selector instead of authoritative #say-hello
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                # This is the PROBLEM: inventing input[type='submit'] instead of using #say-hello
                return CodeLine(code='driver.find_element(By.CSS_SELECTOR, "input[type=\'submit\']").click()')
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

# Test Case A: Valid selectors should PASS
print("=" * 60)
print("TEST CASE A: Valid selectors (should PASS)")
print("=" * 60)

# Create TestAutomationAgent with Hello context
agent = TestAutomationAgent(
    llm_client=MockLLMClientInventedSelector(),
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

# Test case with valid steps
test_case_valid = TestCase(
    test_id="tc_valid_001",
    scenario_id="valid_scenario",
    title="Valid Test",
    description="Test with valid selectors",
    preconditions=["Browser is open"],
    steps=[
        "Enter 'Alice' in the name field",      # Should use #name (correct)
        "Click the submit button",              # Should use #say-hello (but our mock will invent)
        "Verify greeting shows 'Hello, Alice'"  # Should use #greeting (correct)
    ],
    test_data=[TestDataItem(key="name", value="Alice")],
    expected_result="Greeting should show 'Hello, Alice'",
    test_type="functional",
    priority="medium"
)

print(f"base_url: {agent.base_url}")
print(f"sut_context: {agent.sut_context}")
print(f"AUTHORITATIVE SELECTORS:")
print(f"  name_selector: {agent.sut_context.get('name_selector')}")
print(f"  submit_selector: {agent.sut_context.get('submit_selector')}")  # This is #say-hello
print(f"  greeting_selector: {agent.sut_context.get('greeting_selector')}")
print()

# Generate test - this should fail validation due to invented selector
try:
    file_path = agent.generate_test(test_case_valid)
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
        print(f"EXPECTED: Validation correctly caught invented selector")
        print(f"Error message: {e}")
    else:
        print(f"UNEXPECTED: Different syntax error: {e}")
except Exception as e:
    print(f"UNEXPECTED: Other error: {e}")

# Test Case B: Test with no sut_context (should PASS - no validation)
print("\n" + "=" * 60)
print("TEST CASE B: No sut_context (should PASS - no validation)")
print("=" * 60)

agent_no_context = TestAutomationAgent(
    llm_client=MockLLMClientInventedSelector(),
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context=None,  # No context
    test_data=[{"key": "name", "value": "Alice"}]
)

try:
    file_path = agent_no_context.generate_test(test_case_valid)
    print(f"EXPECTED: Test generation succeeded (no sut_context = no validation)")
    print(f"Generated test saved to: {file_path}")
except Exception as e:
    print(f"UNEXPECTED: Test generation failed: {e}")

# Test Case C: Test with empty sut_context (should PASS - no validation)
print("\n" + "=" * 60)
print("TEST CASE C: Empty sut_context (should PASS - no validation)")
print("=" * 60)

agent_empty_context = TestAutomationAgent(
    llm_client=MockLLMClientInventedSelector(),
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context={},  # Empty context
    test_data=[{"key": "name", "value": "Alice"}]
)

try:
    file_path = agent_empty_context.generate_test(test_case_valid)
    print(f"EXPECTED: Test generation succeeded (empty sut_context = no validation)")
    print(f"Generated test saved to: {file_path}")
except Exception as e:
    print(f"UNEXPECTED: Test generation failed: {e}")

print("\n" + "=" * 60)
print("SELECTOR GROUNDING IMPLEMENTATION COMPLETE")
print("=" * 60)