import sys
sys.path.insert(0, 'D:/major project/app')

from workflow.graph import build_workflow

requirement = "Requirement:\nVerify that a user can log in with invalid credentials and is redirected to the dashboard"

initial_state = {
    "requirement": requirement,
}

graph = build_workflow()
final_state = graph.invoke(initial_state)

# Print relevant fields
print("=== State after workflow ===")
print(f"requirement: {final_state.get('requirement')}")
print(f"test_case: {final_state.get('test_case')}")
print(f"execution_result: {final_state.get('execution_result')}")
print(f"failure_analysis: {final_state.get('failure_analysis')}")
print(f"verification_result: {final_state.get('verification_result')}")
print(f"bug_report: {final_state.get('bug_report')}")
print(f"regression_test: {final_state.get('regression_test')}")
print(f"regression_test_approved: {final_state.get('regression_test_approved')}")
print(f"regression_execution_result: {final_state.get('regression_execution_result')}")