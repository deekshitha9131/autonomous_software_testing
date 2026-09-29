#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from workflow.graph import build_workflow

def main():
    workflow = build_workflow()
    requirement = "Verify that a user can log in with valid credentials"
    initial_state = {
        "requirement": requirement,
    }
    final_state = workflow.invoke(initial_state)

    # Extract relevant information
    test_cases = final_state.get("test_cases", [])
    generated_test_codes = final_state.get("generated_test_codes", [])
    test_case = final_state.get("test_case")  # single test case for compatibility
    execution_result = final_state.get("execution_result")
    errors = final_state.get("errors", [])

    # Determine workflow status
    if errors:
        workflow_status = "completed_with_errors"
    elif execution_result:
        exec_status = execution_result.get("status", "unknown")
        if exec_status == "pass":
            workflow_status = "pass"
        elif exec_status == "fail":
            workflow_status = "fail"
        else:
            workflow_status = f"execution_{exec_status}"
    else:
        workflow_status = "not_executed"

    # Print the required information
    print("1. Files changed: app/workflow/state.py, app/workflow/graph.py")
    print(f"2. generated_test_codes field added: {'yes' if generated_test_codes is not None else 'no'}")
    print(f"3. Number of Selenium tests generated: {len(generated_test_codes)}")
    print("4. test_id for each generated test:")
    for gtc in generated_test_codes:
        print(f"   - {gtc.get('test_id')}")
    print("5. Brief expected assertion for each test:")
    for gtc in generated_test_codes:
        test_id = gtc.get("test_id")
        code = gtc.get("code")
        # Extract the assertion line (look for lines containing 'assert')
        assertion_lines = [line.strip() for line in code.split('\n') if 'assert' in line.lower()]
        if assertion_lines:
            # Take the first assertion line (or the last?) we'll take the last one as the main assertion
            assertion = assertion_lines[-1]
            print(f"   - {test_id}: {assertion}")
        else:
            print(f"   - {test_id}: No assertion found")
    print(f"6. Existing valid-login execution status: {execution_result.get('status') if execution_result else None}")
    print(f"7. Any generation error: {errors if errors else None}")

if __name__ == "__main__":
    main()