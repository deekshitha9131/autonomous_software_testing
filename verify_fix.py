#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from workflow.graph import build_workflow

def main():
    workflow = build_workflow()
    requirement = "Verify that after successful login the user is redirected to a profile page with title 'User Profile'"
    initial_state = {
        "requirement": requirement,
    }
    final_state = workflow.invoke(initial_state)

    # Extract relevant information
    test_case = final_state.get("test_case")
    generated_test_code = final_state.get("generated_test_code")
    execution_result = final_state.get("execution_result")
    failure_analysis = final_state.get("failure_analysis")
    human_approval_required = final_state.get("human_approval_required")

    # Determine workflow status based on execution result and errors
    errors = final_state.get("errors", [])
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

    failure_detected = failure_analysis is not None

    # Print the required information
    print("=== Verification Results ===")
    print(f"Requirement: {requirement}")
    print()
    print("Generated Test Case:")
    if test_case:
        for key, value in test_case.items():
            print(f"  {key}: {value}")
    else:
        print("  None")
    print()
    print("Generated Test Code (first 500 chars):")
    if generated_test_code:
        print(generated_test_code[:500] + ("..." if len(generated_test_code) > 500 else ""))
    else:
        print("  None")
    print()
    print("Execution Result:")
    if execution_result:
        for key, value in execution_result.items():
            print(f"  {key}: {value}")
    else:
        print("  None")
    print()
    print(f"Execution Status: {execution_result.get('status') if execution_result else None}")
    print(f"Failure Detected: {failure_detected}")
    print(f"Human Approval Required: {human_approval_required}")
    print(f"Workflow Status: {workflow_status}")
    print()
    # Also print the assertion line if we can find it in the generated test code
    if generated_test_code:
        lines = generated_test_code.split('\n')
        assertion_lines = [line.strip() for line in lines if 'assert' in line.lower() and ('title' in line.lower() or 'dashboard' in line.lower() or 'user profile' in line.lower())]
        if assertion_lines:
            print("Assertion lines found in generated test:")
            for line in assertion_lines:
                print(f"  {line}")
        else:
            print("No specific assertion lines found (maybe check the full code).")
    else:
        print("No generated test code.")

if __name__ == "__main__":
    main()