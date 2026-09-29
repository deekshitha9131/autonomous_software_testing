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

# Create TestAutomationAgent with Hello context
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

# Test _ensure_navigation directly
test_code_without_nav = '''import pytest
from selenium.webdriver.common.by import By

def test_hello(driver):
    """Test hello"""
    # Step 1: Enter name
    driver.find_element(By.ID, "name").send_keys("Alice")
'''

print("INPUT CODE TO _ensure_navigation:")
print("="*50)
print(test_code_without_nav)
print("="*50)

# Call _ensure_navigation
target_url = agent._build_target_url()
print(f"\nTarget URL from _build_target_url(): {target_url}")

result_code = agent._ensure_navigation(test_code_without_nav, target_url)

print("\nOUTPUT CODE FROM _ensure_navigation:")
print("="*50)
print(result_code)
print("="*50)

# Check result
lines = result_code.split('\n')
driver_get_line = None
first_find_element_line = None

for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        continue

    if 'driver.get(' in line and driver_get_line is None:
        driver_get_line = i
        print(f"Found driver.get at line {i+1}: {line}")

    if ('find_element' in line or 'find_elements' in line) and first_find_element_line is None:
        first_find_element_line = i
        print(f"First find_element/find_elements at line {i+1}: {line}")

print("\nRESULT:")
if driver_get_line is not None and first_find_element_line is not None:
    if driver_get_line < first_find_element_line:
        print("✓ PASS: driver.get() is BEFORE first find_element")
    else:
        print("✗ FAIL: driver.get() is AFTER first find_element")
elif driver_get_line is None:
    print("✗ FAIL: No driver.get() found")
else:
    print("? No find_elements found")