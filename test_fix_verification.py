#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import _get_llm_client, validate_requirement, generate_test_scenarios
from app.workflow.state import WorkflowState
from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator

# Use the same requirement as in the verification
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

print("Verifying TestCase generation fix...")
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
    # Print scenario info
    for i, scenario in enumerate(scenarios):
        scenario_id = str(scenario.get('scenario_id', 'N/A'))
        scenario_type = str(scenario.get('scenario_type', 'N/A'))
        title = str(scenario.get('title', 'N/A'))
        print(f"  {i+1}. ID: {scenario_id}, Type: {scenario_type}, Title: {title}")

# Step 3: Generate test cases from scenarios with focused testing
print("\nStep 3: Testing TestCase generation from scenarios...")
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

print(f"\nTesting {len(test_case_gen_state.test_scenarios)} scenarios with 3 attempts each for stability check...")

# Group scenarios by type for testing
scenarios_by_type = {}
for scenario in test_case_gen_state.test_scenarios:
    scenario_type = scenario.get('scenario_type')
    if scenario_type not in scenarios_by_type:
        scenarios_by_type[scenario_type] = []
    scenarios_by_type[scenario_type].append(scenario)

# Test results tracking
stability_results = {
    'functional': {'attempts': 0, 'successes': 0},
    'negative': {'attempts': 0, 'successes': 0},
    'boundary': {'attempts': 0, 'successes': 0},
    'security': {'attempts': 0, 'successes': 0},
    'other': {'attempts': 0, 'successes': 0}
}

# Test up to 1 scenario of each type with 3 attempts each (reduced to save tokens)
tested_scenarios = {}
for scenario_type, scenario_list in scenarios_by_type.items():
    # Take up to 1 scenario of each type for testing
    test_scenarios = scenario_list[:1]
    tested_scenarios[scenario_type] = test_scenarios

    print(f"\n--- Testing {scenario_type} scenarios ({len(test_scenarios)} scenarios, 3 attempts each) ---")

    for scenario_idx, scenario in enumerate(test_scenarios):
        scenario_id = scenario.get('scenario_id', 'unknown')
        print(f"  Scenario {scenario_idx+1}: {scenario_id}")

        # Run 3 attempts for this scenario
        for attempt in range(3):
            stability_results[scenario_type]['attempts'] += 1
            try:
                result = generator.generate_from_scenario(
                    requirement=test_case_gen_state.requirement,
                    requirement_understanding=test_case_gen_state.requirement_understanding or {},
                    scenario=scenario
                )
                stability_results[scenario_type]['successes'] += 1
                # Print dot for success
                print(".", end="", flush=True)
            except Exception as e:
                error_msg = str(e)
                # Check if it's a JSON validation error
                if "json_validate_failed" in error_msg or "Failed to validate JSON" in error_msg:
                    print("J", end="", flush=True)  # J for JSON validation error
                elif "Rate limit reached" in error_msg or "429" in error_msg:
                    print("R", end="", flush=True)  # R for rate limit error
                else:
                    print("O", end="", flush=True)  # O for other error
        print(f"  Completed scenario {scenario_id}")

print(f"\n\n=== STABILITY TEST RESULTS ===")
for scenario_type, results in stability_results.items():
    if results['attempts'] > 0:
        success_rate = (results['successes'] / results['attempts']) * 100
        print(f"{scenario_type.upper()}: {results['successes']}/{results['attempts']} successes ({success_rate:.1f}%)")

print("\nNow running 3 complete workflow runs...")

# Now run 3 complete workflow runs
workflow_results = []

for run_num in range(1, 4):
    print(f"\n--- WORKFLOW RUN {run_num} ---")

    # Regenerate scenarios for each run to simulate real workflow
    scenarios_result = generate_test_scenarios(initial_state)
    if isinstance(scenarios_result, dict) and "errors" in scenarios_result and scenarios_result["errors"]:
        print(f"ERROR generating scenarios: {scenarios_result['errors']}")
        scenarios = []
    else:
        scenarios = scenarios_result.get("test_scenarios", []) if isinstance(scenarios_result, dict) else []

    print(f"Scenarios generated: {len(scenarios)}")

    if not scenarios:
        print("WARNING: No scenarios generated, skipping test case generation")
        workflow_results.append({
            'run': run_num,
            'scenarios': 0,
            'test_cases': 0,
            'failed_scenarios': []
        })
        continue

    # Create state for test case generation
    workflow_state_dict = initial_state_dict.copy()
    workflow_state_dict["test_scenarios"] = scenarios
    workflow_state = WorkflowState(**workflow_state_dict)

    # Generate test cases for all scenarios
    successful_test_cases = 0
    failed_scenario_ids = []

    for scenario in scenarios:
        try:
            result = generator.generate_from_scenario(
                requirement=workflow_state.requirement,
                requirement_understanding=workflow_state.requirement_understanding or {},
                scenario=scenario
            )
            successful_test_cases += 1
        except Exception as e:
            error_msg = str(e)
            failed_scenario_ids.append(scenario.get('scenario_id', 'unknown'))
            # Count as failed but continue with other scenarios

    workflow_results.append({
        'run': run_num,
        'scenarios': len(scenarios),
        'test_cases': successful_test_cases,
        'failed_scenarios': failed_scenario_ids
    })

    print(f"Run {run_num}: {len(scenarios)} scenarios -> {successful_test_cases} test cases")
    if failed_scenario_ids:
        print(f"  Failed scenarios: {failed_scenario_ids}")

# Print workflow run summary
print(f"\n\n=== WORKFLOW RUN SUMMARY ===")
for result in workflow_results:
    print(f"Run {result['run']}: {result['scenarios']} scenarios -> {result['test_cases']} test cases")
    if result['failed_scenarios']:
        print(f"  Failed scenario IDs: {result['failed_scenarios']}")

# Check if security scenarios were handled correctly
print(f"\n=== SECURITY SCENARIO HANDLING ===")
# We need to get the current scenarios to check for security types
scenarios_result = generate_test_scenarios(initial_state)
if isinstance(scenarios_result, dict) and "errors" not in scenarios_result:
    scenarios = scenarios_result.get("test_scenarios", []) if isinstance(scenarios_result, dict) else []
    security_scenarios = [s for s in scenarios if s.get('scenario_type') == 'security']
    if security_scenarios:
        print(f"Found {len(security_scenarios)} security scenarios:")
        for scenario in security_scenarios[:3]:  # Show first 3
            print(f"  - {scenario.get('scenario_id')}: {scenario.get('title')}")
        print("According to fix: security scenarios should be mapped to test_type='non-functional'")
    else:
        print("No security scenarios found in current scenario set")
else:
    print("Could not retrieve scenarios for security check")

# Final assessment
print(f"\n=== FINAL ASSESSMENT ===")
all_success = all(r['test_cases'] == r['scenarios'] for r in workflow_results)
if all_success:
    print("SUCCESS: All workflow runs achieved test_case_count == scenario_count")
    print("   No scenarios were silently dropped")
else:
    print("FAILURE: Some workflow runs did not achieve test_case_count == scenario_count")
    for result in workflow_results:
        if result['test_cases'] != result['scenarios']:
            print(f"   Run {result['run']}: {result['scenarios']} scenarios -> {result['test_cases']} test cases")
            if result['failed_scenarios']:
                print(f"     Failed scenarios: {result['failed_scenarios']}")