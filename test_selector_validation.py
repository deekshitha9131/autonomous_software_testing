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

# Test case that will trigger both name and submit steps
test_case = TestCase(
    test_id="tc_hello_001",
    scenario_id="hello_scenario",
    title="Hello Test",
    description="Test the hello functionality",
    preconditions=["Browser is open"],
    steps=[
        "Enter 'Alice' in the name field",      # Should use #name (correct)
        "Click the submit button",              # Should use #say-hello but we'll invent input[type='submit']
        "Verify greeting shows 'Hello, Alice'"  # Should use #greeting (correct)
    ],
    test_data=[TestDataItem(key="name", value="Alice")],
    expected_result="Greeting should show 'Hello, Alice'",
    test_type="functional",
    priority="medium"
)

print("SELECTOR VALIDATION TEST")
print("=" * 50)
print(f"base_url: {agent.base_url}")
print(f"sut_context: {agent.sut_context}")
print(f"AUTHORITATIVE SELECTORS:")
print(f"  name_selector: {agent.sut_context.get('name_selector')}")
print(f"  submit_selector: {agent.sut_context.get('submit_selector')}")  # This is #say-hello
print(f"  greeting_selector: {agent.sut_context.get('greeting_selector')}")
print()

# Generate test
print("Generating test with MOCK LLM that returns INVENTED selector...")
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

    # Analyze the selectors used
    import re

    # Find all find_element and find_elements calls
    find_pattern = r'find_element\s*\(\s*([^,]+)\s*,\s*([^)]+)'
    find_elements_pattern = r'find_elements\s*\(\s*([^,]+)\s*,\s*([^)]+)'

    print("\nSELECTOR USAGE ANALYSIS:")
    print("-" * 30)

    # Check find_element calls
    for match in re.finditer(find_pattern, code):
        strategy = match.group(1).strip()
        selector = match.group(2).strip()
        print(f"find_element({strategy}, {selector})")

    # Check find_elements calls
    for match in re.finditer(find_elements_pattern, code):
        strategy = match.group(1).strip()
        selector = match.group(2).strip()
        print(f"find_elements({strategy}, {selector})")

    # Check for specific problematic patterns
    print("\nPROBLEMATIC PATTERN CHECK:")
    print("-" * 30)

    # Check if the invented selector was used
    if "input[type='submit']" in code:
        print("✗ FOUND INVENTED SELECTOR: input[type='submit']")
    else:
        print("✓ No invented selector: input[type='submit']")

    if "#submit" in code:
        print("✗ FOUND INVENTED SELECTOR: #submit")
    else:
        print("✓ No invented selector: #submit")

    # Check if the authoritative selector was used
    if 'By.ID, "say-hello"' in code or 'By.CSS_SELECTOR, "#say-hello"' in code:
        print("✓ Authoritative selector #say-hello used correctly")
    else:
        print("✗ Authoritative selector #say-hello NOT used")

    # Check if name selector is correct
    if 'By.ID, "name"' in code:
        print("✓ Authoritative selector #name used correctly (as By.ID, \"name\")")
    else:
        print("✗ Authoritative selector #name NOT used correctly")

    # Check if greeting selector is correct
    if 'By.ID, "greeting"' in code:
        print("✓ Authoritative selector #greeting used correctly (as By.ID, \"greeting\")")
    else:
        print("✗ Authoritative selector #greeting NOT used correctly")

    print("\n" + "="*60)
    print("VALIDATION RESULT:")
    print("="*60)

    # The key question: Did the code pass validation despite having invented selectors?
    # If it got here without throwing an exception, then validation passed
    print("✓ CODE GENERATION SUCCESSFUL (no validation exception thrown)")
    print("  This means the current _validate_code() did NOT catch the invented selector")
    print("  INVENTED SELECTORS CAN REACH EXECUTION: YES")

except Exception as e:
    print(f"\n✗ CODE GENERATION FAILED: {e}")
    print("  This means validation caught the problem")
    print("  INVENTED SELECTORS CAN REACH EXECUTION: NO")

print("\n" + "="*60)
print("ROOT CAUSE ANALYSIS:")
print("="*60)
print("The current _validate_code() method in service.py:")
print("1. Validates Python syntax ✓")
print("2. Checks for placeholder content ✓")
print("3. Validates Selenium locator strategy (requires By.*) ✓")
print("4. BUT does NOT validate that selectors are from authoritative sut_context ✗")
print()
print("This allows LLMs to invent selectors like:")
print("  input[type='submit']  (instead of #say-hello)")
print("  #submit               (instead of #say-hello)")
print("  button[name='submit'] (instead of #say-hello)")
print()
print("These pass the current validation because:")
print("  - They use proper Selenium strategies (By.CSS_SELECTOR)")
print("  - They are valid Python syntax")
print("  - They contain no placeholder content")
print()
print("The fix would be to add selector grounding validation to _validate_code()")
print("that checks if used selectors match those in sut_context.")