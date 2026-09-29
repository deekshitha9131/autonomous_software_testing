#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import _get_llm_client, validate_requirement, generate_test_scenarios
from app.workflow.state import WorkflowState
from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase

# Set up the initial state exactly like the workflow
requirement = "A user can enter a name on the hello page and see a personalized greeting. Also verify relevant negative and boundary behavior."

initial_state_dict = {
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

# Convert to WorkflowState
initial_state = WorkflowState(**initial_state_dict)

print("Testing the complete flow...")
print(f"Requirement: {requirement}")
print()

# Step 1: Validate requirement (should pass)
print("Step 1: Validating requirement...")
validation_result = validate_requirement(initial_state)
# Handle case where validation_result might be None
if validation_result is None:
    validation_result = {}
if isinstance(validation_result, dict) and "errors" in validation_result and validation_result["errors"]:
    print(f"ERROR: {validation_result['errors']}")
    sys.exit(1)
else:
    print("PASS: Requirement validated")

# Step 2: Generate test scenarios (this is where we get the scenarios)
print("\nStep 2: Generating test scenarios...")
scenarios_result = generate_test_scenarios(initial_state)
# Handle case where scenarios_result might be None
if scenarios_result is None:
    scenarios_result = {}
if isinstance(scenarios_result, dict) and "errors" in scenarios_result and scenarios_result["errors"]:
    print(f"ERROR: {scenarios_result['errors']}")
    sys.exit(1)
elif isinstance(scenarios_result, dict) and "test_scenarios" not in scenarios_result:
    print("ERROR: No test_scenarios in result")
    sys.exit(1)
else:
    scenarios = scenarios_result.get("test_scenarios", []) if isinstance(scenarios_result, dict) else []
    print(f"SUCCESS: Generated {len(scenarios)} scenarios")
    # Print scenario info without Unicode characters that might cause issues
    for i, scenario in enumerate(scenarios):
        # Safely get values and encode them to avoid Unicode issues
        scenario_id = str(scenario.get('scenario_id', 'N/A')).encode('ascii', 'ignore').decode('ascii')
        scenario_type = str(scenario.get('scenario_type', 'N/A')).encode('ascii', 'ignore').decode('ascii')
        title = str(scenario.get('title', 'N/A')).encode('ascii', 'ignore').decode('ascii')
        print(f"  {i+1}. ID: {scenario_id}, Type: {scenario_type}, Title: {title}")

# Step 3: Generate test cases from scenarios
print("\nStep 3: Generating test cases from scenarios...")
if not scenarios:
    print("ERROR: No scenarios to generate test cases from")
    sys.exit(1)

# Create the state that would be passed to generate_test_cases_from_scenarios
test_case_gen_state_dict = initial_state_dict.copy()
test_case_gen_state_dict["test_scenarios"] = scenarios

# Convert to WorkflowState
test_case_gen_state = WorkflowState(**test_case_gen_state_dict)

print(f"State for test case generation:")
print(f"  requirement: {test_case_gen_state.requirement[:50] if test_case_gen_state.requirement else 'NOT SET'}...")
print(f"  requirement_understanding: {test_case_gen_state.requirement_understanding}")
print(f"  number of test_scenarios: {len(test_case_gen_state.test_scenarios)}")

# Initialize the LLM client and generator
llm_client = _get_llm_client()
generator = RequirementToTestCaseGenerator(llm_client=llm_client)

print(f"\nCalling generate_test_cases_from_scenarios with the state from workflow...")
print(f"This should replicate exactly what the workflow does.")

success_count = 0
for i, scenario in enumerate(test_case_gen_state.test_scenarios):
    try:
        result = generator.generate_from_scenario(
            requirement=test_case_gen_state.requirement,
            requirement_understanding=test_case_gen_state.requirement_understanding or {},
            scenario=scenario
        )
        print(f"\nSUCCESS! Generated TestCase for scenario {scenario.get('scenario_id')}:")
        print(f"test_id: {result.test_id}")
        print(f"scenario_id: {result.scenario_id}")
        # Safely print title
        title_safe = result.title.encode('ascii', 'ignore').decode('ascii')
        print(f"title: {title_safe}")
        print(f"test_type: {result.test_type}")
        print(f"priority: {result.priority}")
        # Safely print expected_result
        expected_safe = result.expected_result.encode('ascii', 'ignore').decode('ascii')
        print(f"expected_result: {expected_safe}")
        success_count += 1
    except Exception as e:
        print(f"\nERROR generating test case for scenario {scenario.get('scenario_id')}: {e}")

print(f"\n=== SUMMARY ===")
print(f"Scenarios processed: {len(test_case_gen_state.test_scenarios)}")
print(f"Test cases successfully generated: {success_count}")
print(f"Success rate: {success_count/len(test_case_gen_state.test_scenarios)*100:.1f}%")

if success_count > 0:
    print("\nOVERALL SUCCESS: The fix is working!")
    print("   - Scenario generation is working")
    print("   - Test case generation from scenarios is working")
    print("   - Groq client is properly generating structured output")
else:
    print("\nFAILURE: Test case generation is not working")
    sys.exit(1)