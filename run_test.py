#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from workflow.graph import build_workflow

def main():
    workflow = build_workflow()
    # Set the requirement for valid login
    requirement = "Verify that a user can log in with valid credentials"
    initial_state = {
        "requirement": requirement,
        # Other fields will be filled by the workflow
    }
    # Run the workflow
    final_state = workflow.invoke(initial_state)
    # Print the execution result
    print("Execution result:")
    print(final_state.get("execution_result"))
    # Check if the test passed
    execution_result = final_state.get("execution_result")
    if execution_result and execution_result.get("status") == "pass":
        print("TEST PASSED")
        return 0
    else:
        print("TEST FAILED or unknown status")
        return 1

if __name__ == "__main__":
    sys.exit(main())