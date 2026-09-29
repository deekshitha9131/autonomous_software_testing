#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from test_automation_agent.service import TestAutomationAgent
from llm.client import LLMClient
from requirement_to_testcase.schema import TestCase, TestDataItem

# Mock LLM client for testing
class MockLLMClient(LLMClient):
    def __init__(self, return_code=""):
        self.return_code = return_code

    def generate_structured(self, prompt, schema):
        # Return a simple structured response
        from pydantic import BaseModel
        if "test step" in prompt.lower():
            class CodeLine(BaseModel):
                code: str
            return CodeLine(code=self.return_code or 'driver.find_element(By.ID, "username").send_keys("testuser")')
        elif "expected result" in prompt.lower():
            class AssertionLine(BaseModel):
                assertion: str
            return AssertionLine(assertion='assert True')
        else:
            class CodeLine(BaseModel):
                code: str
            return CodeLine(code='# TODO: Implement step')

def test_case_a():
    """CASE A: Generated code with proper assertion should PASS"""
    print("Testing CASE A: Proper assertion (should PASS)")

    agent = TestAutomationAgent(
        llm_client=MockLLMClient(),
        base_url="http://127.0.0.1:8001",
        sut_id="test_sut",
        sut_context={
            "route": "/test",
            "username_selector": "#username",
            "password_selector": "#password",
            "login_button_selector": "#login-button"
        },
        test_data=[]
    )

    test_case = TestCase(
        test_id="tc_a",
        scenario_id="scenario_a",
        title="Valid Login Test",
        description="Test valid login",
        preconditions=["Browser is open"],
        steps=[
            "Navigate to login page",
            "Enter username",
            "Enter password",
            "Click login button"
        ],
        test_data=[],
        expected_result="User should be redirected to dashboard",
        test_type="functional",
        priority="medium"
    )

    # Override the mock to return code with proper assertion
    agent.llm_client = MockLLMClient('assert "Dashboard" in driver.title')

    try:
        # Test the validation directly
        test_code = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_a(driver):
    """Valid Login Test"""
    driver.get("http://127.0.0.1:8001/test")
    # Enter username
    driver.find_element(By.ID, "username").send_keys("testuser")
    # Enter password
    driver.find_element(By.ID, "password").send_keys("testpass")
    # Click login button
    driver.find_element(By.ID, "login-button").click()
    # Verify login successful
    assert "Dashboard" in driver.title
'''
        agent._validate_code(test_code, test_case)
        print("  RESULT: PASS - Correctly accepted valid assertion")
        return True
    except SyntaxError as e:
        print(f"  RESULT: FAIL - Incorrectly rejected valid assertion: {e}")
        return False

def test_case_b():
    """CASE B: Generated code with only comment about missing selectors should FAIL"""
    print("Testing CASE B: Comment about missing selectors (should FAIL)")

    agent = TestAutomationAgent(
        llm_client=MockLLMClient(),
        base_url="http://127.0.0.1:8001",
        sut_id="test_sut",
        sut_context={
            "route": "/test",
            "username_selector": "#username",
            "password_selector": "#password",
            "login_button_selector": "#login-button"
        },
        test_data=[]
    )

    test_case = TestCase(
        test_id="tc_b",
        scenario_id="scenario_b",
        title="Missing Selectors Test",
        description="Test with missing selectors",
        preconditions=["Browser is open"],
        steps=[
            "Navigate to login page",
            "Enter username",
            "Enter password",
            "Click login button"
        ],
        test_data=[],
        expected_result="User should be logged in",
        test_type="functional",
        priority="medium"
    )

    try:
        # Test the validation directly
        test_code = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_b(driver):
    """Missing Selectors Test"""
    driver.get("http://127.0.0.1:8001/test")
    # Enter username
    driver.find_element(By.ID, "username").send_keys("testuser")
    # Enter password
    driver.find_element(By.ID, "password").send_keys("testpass")
    # Click login button
    driver.find_element(By.ID, "login-button").click()
    # Expected result: A personalized greeting message ...
    # Required selectors or URL are not provided in the SUT context.
'''
        agent._validate_code(test_code, test_case)
        print("  RESULT: FAIL - Should have rejected code with only comments")
        return False
    except SyntaxError as e:
        if "lacks executable verification" in str(e):
            print("  RESULT: PASS - Correctly rejected code with only comments")
            return True
        else:
            print(f"  RESULT: FAIL - Wrong error: {e}")
            return False

def test_case_c():
    """CASE C: Generated code with assert True should FAIL"""
    print("Testing CASE C: assert True (should FAIL)")

    agent = TestAutomationAgent(
        llm_client=MockLLMClient(),
        base_url="http://127.0.0.1:8001",
        sut_id="test_sut",
        sut_context={
            "route": "/test",
            "username_selector": "#username",
            "password_selector": "#password",
            "login_button_selector": "#login-button"
        },
        test_data=[]
    )

    test_case = TestCase(
        test_id="tc_c",
        scenario_id="scenario_c",
        title="Assert True Test",
        description="Test with assert True",
        preconditions=["Browser is open"],
        steps=[
            "Navigate to login page",
            "Enter username",
            "Enter password",
            "Click login button"
        ],
        test_data=[],
        expected_result="User should be logged in",
        test_type="functional",
        priority="medium"
    )

    try:
        # Test the validation directly
        test_code = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_c(driver):
    """Assert True Test"""
    driver.get("http://127.0.0.1:8001/test")
    # Enter username
    driver.find_element(By.ID, "username").send_keys("testuser")
    # Enter password
    driver.find_element(By.ID, "password").send_keys("testpass")
    # Click login button
    driver.find_element(By.ID, "login-button").click()
    assert True
'''
        agent._validate_code(test_code, test_case)
        print("  RESULT: FAIL - Should have rejected assert True")
        return False
    except SyntaxError as e:
        if "placeholder" in str(e).lower():
            print("  RESULT: PASS - Correctly rejected assert True as placeholder")
            return True
        else:
            print(f"  RESULT: FAIL - Wrong error: {e}")
            return False

def test_case_d():
    """CASE D: Generated code with TODO comment should FAIL"""
    print("Testing CASE D: TODO comment (should FAIL)")

    agent = TestAutomationAgent(
        llm_client=MockLLMClient(),
        base_url="http://127.0.0.1:8001",
        sut_id="test_sut",
        sut_context={
            "route": "/test",
            "username_selector": "#username",
            "password_selector": "#password",
            "login_button_selector": "#login-button"
        },
        test_data=[]
    )

    test_case = TestCase(
        test_id="tc_d",
        scenario_id="scenario_d",
        title="TODO Comment Test",
        description="Test with TODO comment",
        preconditions=["Browser is open"],
        steps=[
            "Navigate to login page",
            "Enter username",
            "Enter password",
            "Click login button"
        ],
        test_data=[],
        expected_result="User should be logged in",
        test_type="functional",
        priority="medium"
    )

    try:
        # Test the validation directly
        test_code = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_d(driver):
    """TODO Comment Test"""
    driver.get("http://127.0.0.1:8001/test")
    # Enter username
    driver.find_element(By.ID, "username").send_keys("testuser")
    # Enter password
    driver.find_element(By.ID, "password").send_keys("testpass")
    # Click login button
    driver.find_element(By.ID, "login-button").click()
    # TODO: verify result
'''
        agent._validate_code(test_code, test_case)
        print("  RESULT: FAIL - Should have rejected TODO comment")
        return False
    except SyntaxError as e:
        if "placeholder" in str(e).lower():
            print("  RESULT: PASS - Correctly rejected TODO comment")
            return True
        else:
            print(f"  RESULT: FAIL - Wrong error: {e}")
            return False

def test_case_e():
    """CASE E: Legitimate negative test with executable assertion should PASS"""
    print("Testing CASE E: Legitimate negative test (should PASS)")

    agent = TestAutomationAgent(
        llm_client=MockLLMClient(),
        base_url="http://127.0.0.1:8001",
        sut_id="test_sut",
        sut_context={
            "route": "/test",
            "username_selector": "#username",
            "password_selector": "#password",
            "login_button_selector": "#login-button",
            "error_message_selector": "#error-message"
        },
        test_data=[]
    )

    test_case = TestCase(
        test_id="tc_e",
        scenario_id="scenario_e",
        title="Negative Login Test",
        description="Test invalid login",
        preconditions=["Browser is open"],
        steps=[
            "Navigate to login page",
            "Enter invalid username",
            "Enter password",
            "Click login button"
        ],
        test_data=[],
        expected_result="Login should fail with error message",
        test_type="functional",
        priority="medium"
    )

    # Override the mock to return code with proper assertion
    agent.llm_client = MockLLMClient('assert "Invalid credentials" in driver.find_element(By.ID, "error-message").text')

    try:
        # Test the validation directly
        test_code = '''
import pytest
from selenium.webdriver.common.by import By

def test_tc_e(driver):
    """Negative Login Test"""
    driver.get("http://127.0.0.1:8001/test")
    # Enter invalid username
    driver.find_element(By.ID, "username").send_keys("invaliduser")
    # Enter password
    driver.find_element(By.ID, "password").send_keys("testpass")
    # Click login button
    driver.find_element(By.ID, "login-button").click()
    # Verify error message is shown
    assert "Invalid credentials" in driver.find_element(By.ID, "error-message").text
'''
        agent._validate_code(test_code, test_case)
        print("  RESULT: PASS - Correctly accepted legitimate negative test")
        return True
    except SyntaxError as e:
        print(f"  RESULT: FAIL - Incorrectly rejected legitimate negative test: {e}")
        return False

def run_all_tests():
    """Run all test cases"""
    print("=" * 60)
    print("COMPLETENESS VALIDATION TESTS")
    print("=" * 60)

    results = []
    results.append(("CASE A", test_case_a()))
    results.append(("CASE B", test_case_b()))
    results.append(("CASE C", test_case_c()))
    results.append(("CASE D", test_case_d()))
    results.append(("CASE E", test_case_e()))

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("All tests PASSED!")
        return True
    else:
        print("Some tests FAILED!")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)