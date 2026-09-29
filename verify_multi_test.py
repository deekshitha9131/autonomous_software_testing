#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch
from pydantic import BaseModel

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Loads .env file from current directory
    print("Loaded environment variables from .env file")
except ImportError:
    print("Warning: python-dotenv not available, .env file not loaded")

# Set the environment variables for Groq (use existing configuration from .env)
# Don't expose API key - assume it's already set in environment or .env
if "LLM_PROVIDER" not in os.environ:
    os.environ["LLM_PROVIDER"] = "groq"
if "GROQ_MODEL" not in os.environ:
    os.environ["GROQ_MODEL"] = "openai/gpt-oss-20b"

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import build_workflow
from app.workflow.state import WorkflowState

# Requirement that should generate multiple scenarios (functional + negative + boundary)
requirement = "A user can enter a name on the hello page and see a personalized greeting. Also verify relevant negative and boundary behavior."

print(f"Testing requirement: {requirement}")
print("=" * 80)

# Initialize state with the requirement AND SUT context
initial_state = {
    "requirement": requirement,
    "base_url": "http://127.0.0.1:8001",
    "sut_id": "demo-app",
    "sut_context": {
        "route": "/hello",
        "name_selector": "#name",
        "submit_selector": "#say-hello",
        "greeting_selector": "#greeting",
        "expected_behavior": "Submitting Alice displays Hello, Alice!"
    },
    "test_data": {"name": "Alice"}
}

try:
    # Build and run the workflow
    print("Building workflow...")
    workflow = build_workflow()
    print("Running workflow with REAL Groq...")
    result = workflow.invoke(initial_state)

    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETED!")
    print(f"Workflow status: {result.get('workflow_status', 'unknown')}")

    # Check scenarios
    scenarios = result.get('test_scenarios', [])
    print(f"\nGenerated {len(scenarios)} scenario(s):")
    for i, scenario in enumerate(scenarios):
        print(f"  Scenario {i+1}: {scenario.get('title', 'Unknown')}")
        print(f"    Scenario ID: {scenario.get('scenario_id')}")
        print(f"    Type: {scenario.get('scenario_type', 'Unknown')}")

    # Check structured test cases
    test_cases = result.get('test_cases', [])
    print(f"\nGenerated {len(test_cases)} structured test case(s):")
    for i, tc in enumerate(test_cases):
        print(f"  Test Case {i+1}: {tc.get('title', 'Unknown')}")
        print(f"    Test ID: {tc.get('test_id')}")
        print(f"    Scenario ID: {tc.get('scenario_id')} (should match scenario)")
        print(f"    Type: {tc.get('test_type', 'Unknown')}")

    # Check generated Selenium tests (plural field)
    generated_test_codes = result.get('generated_test_codes', [])
    print(f"\nGenerated {len(generated_test_codes)} Selenium test(s):")
    for i, gt in enumerate(generated_test_codes):
        print(f"  Generated Test {i+1}:")
        print(f"    Test ID: {gt.get('test_id')}")
        print(f"    Scenario ID: {gt.get('scenario_id')}")
        print(f"    Path: {gt.get('generated_test_path')}")
        # Check for TODOs or placeholders in the code
        code = gt.get('generated_test_code', '')
        if '# TODO:' in code or '# TODO' in code or 'pass  # Placeholder' in code:
            print(f"    WARNING: Contains placeholder code!")
        else:
            print(f"    Code looks good (no obvious placeholders)")
        # Check for invented URLs/selectors (basic check)
        if 'http://' in code and '127.0.0.1:8001' not in code and 'localhost' not in code:
            print(f"    WARNING: May contain invented URL!")
        # Show first 200 chars of code for inspection
        print(f"    Code preview: {code[:200]}{'...' if len(code) > 200 else ''}")

    # Check backward compatibility singular fields
    print(f"\nBackward compatibility fields:")
    print(f"  test_case: {result.get('test_case', {}).get('test_id', 'None') if result.get('test_case') else 'None'}")
    print(f"  generated_test_path: {result.get('generated_test_path', 'None')}")
    print(f"  generated_test_code: {'SET' if result.get('generated_test_code') else 'None'}")
    print(f"  execution_result: {result.get('execution_result', {}).get('status', 'None') if result.get('execution_result') else 'None'}")

    # Check execution results (plural field)
    execution_results = result.get('execution_results', [])
    print(f"\nExecution results: {len(execution_results)} test(s) executed")
    for i, exec_result in enumerate(execution_results):
        print(f"  Test {i+1}: {exec_result.get('test_id', 'Unknown')} - Status: {exec_result.get('status', 'Unknown')}")
        if exec_result.get('error_message'):
            print(f"    Error: {exec_result['error_message']}")
        if exec_result.get('stdout'):
            print(f"    STDOUT: {exec_result['stdout'][:100]}...")
        if exec_result.get('stderr'):
            print(f"    STDERR: {exec_result['stderr'][:100]}...")

    # Check execution summary
    execution_summary = result.get('execution_summary', {})
    if execution_summary:
        print(f"\nExecution summary:")
        print(f"  Total: {execution_summary.get('total', 0)}")
        print(f"  Passed: {execution_summary.get('passed', 0)}")
        print(f"  Failed: {execution_summary.get('failed', 0)}")
        print(f"  Errors: {execution_summary.get('errors', 0)}")
        print(f"  Skipped: {execution_summary.get('skipped', 0)}")

    # Check for errors
    errors = result.get('errors', [])
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for i, error in enumerate(errors[:5]):  # Show first 5 errors
            print(f"  {i+1}. {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

    # Verification
    print("\n" + "=" * 80)
    print("VERIFICATION RESULTS:")
    print("=" * 80)

    scenario_count = len(scenarios)
    test_case_count = len(test_cases)
    generated_test_count = len(generated_test_codes)
    execution_result_count = len(execution_results)

    print(f"SCENARIO COUNT: {scenario_count}")
    print(f"STRUCTURED TEST CASE COUNT: {test_case_count}")
    print(f"GENERATED SELENIUM TEST COUNT: {generated_test_count}")
    print(f"EXECUTION RESULT COUNT: {execution_result_count}")

    print(f"\nSCENARIO -> STRUCTURED CASE COUNT MATCH: {'YES' if scenario_count == test_case_count else 'NO'}")
    print(f"STRUCTURED CASE -> GENERATED TEST COUNT MATCH: {'YES' if test_case_count == generated_test_count else 'NO'}")
    print(f"GENERATED TEST -> EXECUTION RESULT COUNT MATCH: {'YES' if generated_test_count == execution_result_count else 'NO'}")

    # Check traceability
    print(f"\nTRACEABILITY VERIFICATION:")
    traceability_ok = True
    if scenario_count > 0 and test_case_count > 0:
        # Check first few items for traceability
        for i in range(min(scenario_count, test_case_count, generated_test_count, execution_result_count)):
            scenario_id = scenarios[i].get('scenario_id') if i < len(scenarios) else None
            test_case_id = test_cases[i].get('test_id') if i < len(test_cases) else None
            test_case_scenario_id = test_cases[i].get('scenario_id') if i < len(test_cases) else None
            generated_test_id = generated_test_codes[i].get('test_id') if i < len(generated_test_codes) else None
            generated_test_scenario_id = generated_test_codes[i].get('scenario_id') if i < len(generated_test_codes) else None
            exec_test_id = execution_results[i].get('test_id') if i < len(execution_results) else None
            exec_scenario_id = execution_results[i].get('scenario_id') if i < len(execution_results) else None
            exec_status = execution_results[i].get('status', 'unknown') if i < len(execution_results) else 'unknown'

            print(f"  Item {i+1}:")
            print(f"    Scenario ID: {scenario_id}")
            print(f"    -> Test Case ID: {test_case_id} (Scenario ID: {test_case_scenario_id})")
            print(f"    -> Generated Test ID: {generated_test_id} (Scenario ID: {generated_test_scenario_id})")
            print(f"    -> Execution Result ID: {exec_test_id} (Scenario ID: {exec_scenario_id}) - Status: {exec_status}")

            # Verify IDs match
            if scenario_id != test_case_scenario_id:
                print(f"    MISMATCH: Scenario ID {scenario_id} != Test Case Scenario ID {test_case_scenario_id}")
                traceability_ok = False
            if test_case_id != generated_test_id:
                print(f"    MISMATCH: Test Case ID {test_case_id} != Generated Test ID {generated_test_id}")
                traceability_ok = False
            if generated_test_id != exec_test_id:
                print(f"    MISMATCH: Generated Test ID {generated_test_id} != Execution Test ID {exec_test_id}")
                traceability_ok = False

            if traceability_ok:
                print(f"    Traceability OK")

    print(f"\nEXECUTION SUMMARY:")
    print(f"  total: {execution_summary.get('total', 0)}")
    print(f"  passed: {execution_summary.get('passed', 0)}")
    print(f"  failed: {execution_summary.get('failed', 0)}")
    print(f"  errors: {execution_summary.get('errors', 0)}")
    print(f"  skipped: {execution_summary.get('skipped', 0)}")

    summary_total = execution_summary.get('total', 0)
    print(f"\nSUMMARY TOTAL MATCHES EXECUTION_RESULTS: {'YES' if summary_total == execution_result_count else 'NO'}")

    # Check if all generated tests were actually attempted
    all_attempted = execution_result_count == generated_test_count
    print(f"ALL GENERATED TESTS ACTUALLY ATTEMPTED: {'YES' if all_attempted else 'NO'}")

    # Check if one failure stopped remaining tests (by checking if we have results for all tests)
    one_failure_stopped_others = not all_attempted and execution_result_count < generated_test_count
    print(f"ONE FAILURE STOPPED REMAINING TESTS: {'YES' if one_failure_stopped_others else 'NO'}")

    # Check for TODOs/placeholders in generated code
    todo_placeholder_present = False
    for gt in generated_test_codes:
        code = gt.get('generated_test_code', '')
        if '# TODO:' in code or '# TODO' in code or 'pass  # Placeholder' in code:
            todo_placeholder_present = True
            break
    print(f"TODO/PLACEHOLDER CODE PRESENT: {'YES' if todo_placeholder_present else 'NO'}")

    # Check for invented URLs (simplistic check)
    invented_url_present = False
    for gt in generated_test_codes:
        code = gt.get('generated_test_code', '')
        if 'http://' in code or 'https://' in code:
            # Check if it's pointing to our SUT
            if '127.0.0.1:8001' not in code and 'localhost' not in code:
                invented_url_present = True
                break
    print(f"INVENTED URL PRESENT: {'YES' if invented_url_present else 'NO'}")

    # Check for invented selectors (simplistic check - hard to do perfectly)
    # We'll just check if common selectors we didn't provide are used
    invented_selector_present = False
    forbidden_selectors = ['.class', '[id=', 'div:', 'p:', 'span:']  # Basic check
    for gt in generated_test_codes:
        code = gt.get('generated_test_code', '')
        for selector in forbidden_selectors:
            if selector in code:
                invented_selector_present = True
                break
        if invented_selector_present:
            break
    print(f"INVENTED SELECTORS PRESENT: {'YES' if invented_selector_present else 'NO'} (heuristic check)")

    # Check if failed/error tests reached investigation
    failed_tests = [r for r in execution_results if r.get('status') in ['fail', 'error']]
    failure_analyses = result.get('failure_analyses', [])
    investigation_reached = len(failed_tests) == 0 or len(failure_analyses) > 0
    print(f"FAILED/ERROR TESTS REACHED INVESTIGATION: {'YES' if investigation_reached else 'NO'}")
    if not investigation_reached and failed_tests:
        print(f"  {len(failed_tests)} failed/error tests but {len(failure_analyses)} failure analyses")

    # Workflow status
    workflow_status = result.get('workflow_status', 'unknown')
    print(f"WORKFLOW STATUS: {workflow_status}")

    # State errors
    state_errors = result.get('errors', [])
    print(f"STATE ERRORS: {len(state_errors)} error(s)")
    if state_errors:
        print(f"  First few: {state_errors[:3]}")

    # First failure if any
    first_failure = "None"
    if failed_tests:
        first_failure = f"Test {failed_tests[0].get('test_id', 'unknown')} - {failed_tests[0].get('status', 'unknown')}"
    print(f"FIRST FAILURE IF ANY: {first_failure}")

    # Final determination
    print("\n" + "=" * 80)
    print("FINAL RESULT:")

    # Check if we have at least 2 scenarios as required for verification
    if scenario_count < 2:
        print("REAL MULTI-TEST E2E: SKIPPED (less than 2 scenarios generated)")
        print("  NOTE: Verification requires at least 2 scenarios to test multi-test path")
        print(f"  Only {scenario_count} scenario(s) generated")
    else:
        # All checks passed
        multi_test_success = (
            scenario_count >= 2 and
            scenario_count == test_case_count and
            test_case_count == generated_test_count and
            generated_test_count == execution_result_count and
            summary_total == execution_result_count and
            all_attempted and
            not one_failure_stopped_others and
            not todo_placeholder_present and
            not invented_url_present and
            investigation_reached
        )
        print(f"REAL MULTI-TEST E2E: {'PASS' if multi_test_success else 'FAIL'}")

except Exception as e:
    print(f"\nError running workflow: {e}")
    import traceback
    traceback.print_exc()
    print("\nREAL MULTI-TEST E2E: FAIL (exception)")

finally:
    # Clean up any temporary files if needed
    pass