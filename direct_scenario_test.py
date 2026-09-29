#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath('.'))

from app.workflow.graph import _get_llm_client
from app.workflow.state import WorkflowState
from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase

# Use a known scenario from previous runs to avoid token usage for generation
known_boundary_scenario = {
    "scenario_id": "boundary_1",
    "scenario_type": "boundary",
    "title": "Maximum length name input is handled correctly",
    "description": "User enters a name that reaches the maximum allowed length (e.g., 255 characters) and the greeting should display correctly without truncation or errors."
}

requirement = "A user can enter a name on the hello page and see a personalized greeting. Also verify relevant negative and boundary behavior."

# Create a minimal state
state_dict = {
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
state = WorkflowState(**state_dict)

print("Testing with known boundary scenario:")
print(f"Scenario ID: {known_boundary_scenario['scenario_id']}")
print(f"Scenario Type: {known_boundary_scenario['scenario_type']}")
print(f"Title: {known_boundary_scenario['title']}")
print(f"Description: {known_boundary_scenario['description']}")

# Initialize the LLM client and generator
llm_client = _get_llm_client()
generator = RequirementToTestCaseGenerator(llm_client=llm_client)

# Run multiple attempts to catch JSON validation errors
json_validation_errors = []
success_count = 0
other_errors = []

print("\nRunning 20 attempts to capture JSON validation errors:")
for attempt in range(20):
    try:
        result = generator.generate_from_scenario(
            requirement=requirement,
            requirement_understanding={},  # Simplified - in real workflow this comes from Phase 2
            scenario=known_boundary_scenario
        )
        success_count += 1
        # Print just a dot for success to keep output clean
        print(".", end="", flush=True)
    except Exception as e:
        error_msg = str(e)
        if "json_validate_failed" in error_msg or "Failed to validate JSON" in error_msg:
            json_validation_errors.append({
                'attempt': attempt+1,
                'error': error_msg
            })
            print("J", end="", flush=True)  # J for JSON error
        elif "Rate limit reached" in error_msg or "429" in error_msg:
            print("R", end="", flush=True)  # R for Rate limit error
        else:
            other_errors.append({
                'attempt': attempt+1,
                'error': error_msg
            })
            print("O", end="", flush=True)  # O for Other error

print(f"\n\n=== RESULTS ===")
print(f"Total attempts: 20")
print(f"Successes: {success_count}")
print(f"JSON validation errors: {len(json_validation_errors)}")
print(f"Rate limit errors: {sum(1 for e in other_errors if 'Rate limit reached' in e['error'] or '429' in e['error'])}")
print(f"Other errors: {len([e for e in other_errors if not ('Rate limit reached' in e['error'] or '429' in e['error'])])}")

if json_validation_errors:
    print(f"\nJSON validation error details (first 3):")
    for i, error in enumerate(json_validation_errors[:3]):
        print(f"  Attempt {error['attempt']}: {error['error']}")
else:
    print("\nNo JSON validation errors captured in this run.")

print(f"\n=== TESTCASE SCHEMA CONSTRAINTS ===")
print("Field: test_type")
print("  Type: Literal[")
print('    "functional", "non-functional", "unit", "integration", "ui", "api", "negative", "boundary"')
print("  ]")
print("")
print("Field: priority")
print("  Type: Literal[")
print('    "low", "medium", "high", "critical"')
print("  ]")
print("")
print("All other fields are required strings or collections of strings/dicts.")
print("")
print("KEY OBSERVATION:")
print("- The schema requires EXACT string matches for Literal fields")
print("- The prompt gives guidance but doesn't enforce exact format")
print("- JSON validation errors suggest Groq sometimes produces:")
print("  * Invalid JSON format")
print("  * Valid JSON but with values not in the Literal allowed set")
print("  * Valid JSON but missing required fields")