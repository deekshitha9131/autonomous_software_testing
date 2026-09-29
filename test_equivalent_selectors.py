#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client that returns EQUIVALENT selector forms
class MockLLMClientEquivalentSelector(LLMClient):
    def generate_structured(self, prompt, schema):
        # For _step_to_selenium_command, return equivalent selector forms
        if "Convert the following test step into a single line of Selenium Python code" in prompt:
            # Check what step we're dealing with
            if "name" in prompt.lower() and ("send" in prompt.lower() or "type" in prompt.lower() or "enter" in prompt.lower()):
                # For name field: return equivalent of #name
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                # This is equivalent to #name: using By.NAME instead of By.ID
                # Actually, let's use By.CSS_SELECTOR with the same value
                return CodeLine(code='driver.find_element(By.CSS_SELECTOR, "#name").send_keys("Alice")')
            elif "submit" in prompt.lower() or "button" in prompt.lower() or "click" in prompt.lower():
                # FOR SUBMIT BUTTON: Return equivalent of #say-hello
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                # This is equivalent to #say-hello
                return CodeLine(code='driver.find_element(By.CSS_SELECTOR, "#say-hello").click()')
            elif "greeting" in prompt.lower() or "text" in prompt.lower() or "assert" in prompt.lower():
                # For greeting: return equivalent of #greeting
                from pydantic import BaseModel
                class CodeLine(BaseModel):
                    code: str
                # This is equivalent to #greeting
                return CodeLine(code='assert "Hello, Alice" in driver.find_element(By.CSS_SELECTOR, "#greeting").text')
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

# Create TestAutomationAgent with Hello context
agent = TestAutomationAgent(
    llm_client=MockLLMClientEquivalentSelector(),
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

print("EQUIVALENT SELECTOR TEST")
print("=" * 40)
print(f"base_url: {agent.base_url}")
print(f"sut_context: {agent.sut_context}")
print()

# Generate test
print("Generating test with MOCK LLM that returns EQUIVALENT selector forms...")
try:
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

    # Analyze
    print("\nEQUIVALENT SELECTOR CHECK:")
    print("-" * 30)

    # Check if equivalent forms were used
    if 'By.CSS_SELECTOR, "#name"' in code:
        print("✓ Equivalent form used for name: By.CSS_SELECTOR, \"#name\" (equivalent to #name)")
    else:
        print("✗ Equivalent form NOT used for name")

    if 'By.CSS_SELECTOR, "#say-hello"' in code:
        print("✓ Equivalent form used for submit: By.CSS_SELECTOR, \"#say-hello\" (equivalent to #say-hello)")
    else:
        print("✗ Equivalent form NOT used for submit")

    if 'By.CSS_SELECTOR, "#greeting"' in code:
        print("✓ Equivalent form used for greeting: By.CSS_SELECTOR, \"#greeting\" (equivalent to #greeting)")
    else:
        print("✗ Equivalent form NOT used for greeting")

    print("\n" + "="*60)
    print("NORMALIZATION CONCEPT:")
    print("="*60)
    print("The current implementation does NOT perform selector normalization.")
    print("It relies on the LLM to use the exact selectors provided in the context.")
    print("However, equivalent forms like:")
    print("  #name ↔ By.ID, \"name\" ↔ By.CSS_SELECTOR, \"#name\"")
    print("  are functionally identical and should be acceptable.")
    print()
    print("For the DIRECT SELECTOR TEST, we need to check if the current")
    print("implementation would accept equivalent forms.")
    print()
    print("Since the current validation only checks for proper Selenium")
    print("strategy (not specific selector values), equivalent forms")
    print("would PASS the current validation.")

except Exception as e:
    print(f"\n✗ CODE GENERATION FAILED: {e}")

print("\n" + "="*60)