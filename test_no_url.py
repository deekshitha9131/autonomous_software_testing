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

print("TEST CASE 1: Normal case (should work)")
print("-" * 40)
agent1 = TestAutomationAgent(
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
target_url1 = agent1._build_target_url()
print(f"base_url: {agent1.base_url}")
print(f"sut_context: {agent1.sut_context}")
print(f"_build_target_url() returned: {target_url1}")
print()

print("TEST CASE 2: Empty base_url")
print("-" * 40)
agent2 = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url="",  # Empty string
    sut_id="hello_sut",
    sut_context={
        "route": "/hello",
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)
target_url2 = agent2._build_target_url()
print(f"base_url: '{agent2.base_url}'")
print(f"sut_context: {agent2.sut_context}")
print(f"_build_target_url() returned: {target_url2}")
print()

print("TEST CASE 3: None base_url")
print("-" * 40)
agent3 = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url=None,  # None
    sut_id="hello_sut",
    sut_context={
        "route": "/hello",
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)
target_url3 = agent3._build_target_url()
print(f"base_url: {agent3.base_url}")
print(f"sut_context: {agent3.sut_context}")
print(f"_build_target_url() returned: {target_url3}")
print()

print("TEST CASE 4: sut_context not a dict")
print("-" * 40)
agent4 = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context="not a dict",  # Not a dict
    test_data=[{"key": "name", "value": "Alice"}]
)
target_url4 = agent4._build_target_url()
print(f"base_url: {agent4.base_url}")
print(f"sut_context: {agent4.sut_context} (type: {type(agent4.sut_context)})")
print(f"_build_target_url() returned: {target_url4}")
print()

print("TEST CASE 5: sut_context is dict but missing 'route' key")
print("-" * 40)
agent5 = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context={  # Missing 'route' key
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)
target_url5 = agent5._build_target_url()
print(f"base_url: {agent5.base_url}")
print(f"sut_context: {agent5.sut_context}")
print(f"_build_target_url() returned: {target_url5}")
print()

print("TEST CASE 6: sut_context has empty route")
print("-" * 40)
agent6 = TestAutomationAgent(
    llm_client=MockLLMClient(),
    base_url="http://127.0.0.1:8001",
    sut_id="hello_sut",
    sut_context={  # Empty route
        "route": "",
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting"
    },
    test_data=[{"key": "name", "value": "Alice"}]
)
target_url6 = agent6._build_target_url()
print(f"base_url: {agent6.base_url}")
print(f"sut_context: {agent6.sut_context}")
print(f"_build_target_url() returned: {target_url6}")
print()