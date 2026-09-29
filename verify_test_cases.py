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
    test_scenarios = final_state.get("test_scenarios", [])
    test_cases = final_state.get("test_cases", [])
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
    print(f"2. test_scenarios count: {len(test_scenarios)}")
    print(f"3. test_cases count: {len(test_cases)}")
    print("4. test_id + title + test_type for all test cases:")
    for tc in test_cases:
        print(f"   - test_id: {tc.get('test_id')}, title: {tc.get('title')}, test_type: {tc.get('test_type')}")
    # Check if every scenario converted to a test case
    every_converted = len(test_scenarios) == len(test_cases) and all(
        tc.get('test_id') == sc.get('scenario_id') for tc, sc in zip(test_cases, test_scenarios)
    )
    print(f"5. Every scenario converted: {'yes' if every_converted else 'no'}")
    print(f"6. Existing valid-login execution status: {execution_result.get('status') if execution_result else None}")
    print(f"7. Any error: {errors if errors else None}")

if __name__ == "__main__":
    main()