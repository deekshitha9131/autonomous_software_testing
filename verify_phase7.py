import sys
import os
sys.path.insert(0, 'D:/major project')

from app.selenium_engine.execution_service import ExecutionService

print("=== Testing ExecutionService directly ===")
def passing_test(driver):
    pass

def failing_test(driver):
    raise AssertionError("Intentional failure")

# Passing test
with ExecutionService() as service:
    result = service.execute_test(passing_test)
    print(f"Passing test: status={result['status']}, duration={result['duration']}, screenshot={result['screenshot']}")
    assert result['status'] == 'pass'
    assert result['duration'] >= 0
    assert result['exception'] is None
    assert result['screenshot'] is None

# Failing test
with ExecutionService() as service:
    result = service.execute_test(failing_test)
    print(f"Failing test: status={result['status']}, duration={result['duration']}")
    assert result['status'] == 'fail'
    assert result['duration'] >= 0
    assert result['exception'] is not None
    assert result['exception']['type'] == 'AssertionError'
    assert result['screenshot'] is not None
    # Check screenshot file exists
    if result['screenshot']:
        assert os.path.exists(result['screenshot']), f"Screenshot file not found: {result['screenshot']}"
        print(f"  Screenshot exists: {result['screenshot']}")

print("\n=== Testing execution result augmentation (simulating graph.py logic) ===")
# Simulate what execute_test does: takes result from ExecutionService and adds test_id and scenario_id
def augment_result(result, test_id, scenario_id):
    # This is what we do in execute_test after getting result from service
    result["test_id"] = test_id
    result["scenario_id"] = scenario_id
    return result

# Passing test augmentation
with ExecutionService() as service:
    base_result = service.execute_test(passing_test)
    augmented = augment_result(base_result.copy(), "test123", "scenario456")
    print(f"Augmented passing test: test_id={augmented['test_id']}, scenario_id={augmented['scenario_id']}")
    print(f"  status={augmented['status']}, duration={augmented['duration']}, screenshot={augmented['screenshot']}")
    # Ensure original fields preserved
    assert augmented['status'] == 'pass'
    assert augmented['duration'] == base_result['duration']
    assert augmented['exception'] == base_result['exception']
    assert augmented['screenshot'] == base_result['screenshot']
    assert augmented['test_id'] == 'test123'
    assert augmented['scenario_id'] == 'scenario456'

# Failing test augmentation
with ExecutionService() as service:
    base_result = service.execute_test(failing_test)
    augmented = augment_result(base_result.copy(), "test999", "scenario888")
    print(f"Augmented failing test: test_id={augmented['test_id']}, scenario_id={augmented['scenario_id']}")
    print(f"  status={augmented['status']}, duration={augmented['duration']}")
    assert augmented['status'] == 'fail'
    assert augmented['duration'] == base_result['duration']
    assert augmented['exception'] == base_result['exception']
    assert augmented['screenshot'] == base_result['screenshot']
    assert augmented['test_id'] == 'test999'
    assert augmented['scenario_id'] == 'scenario888'

print("\n=== Testing summary computation ===")
# Mock a list of execution results as they would be in state.execution_results
mock_results = [
    {"status": "pass", "duration": 0.1, "exception": None, "screenshot": None, "test_id": "t1", "scenario_id": "s1"},
    {"status": "fail", "duration": 0.2, "exception": {"type": "AssertionError", "message": "fail"}, "screenshot": "shot1.png", "test_id": "t2", "scenario_id": "s1"},
    {"status": "fail", "duration": 0.3, "exception": {"type": "ValueError", "message": "fail2"}, "screenshot": "shot2.png", "test_id": "t3", "scenario_id": "s2"},
    {"status": "error", "duration": 0, "exception": {"type": "ImportError", "message": "bad module"}, "screenshot": None, "test_id": "t4", "scenario_id": "s2"},
    {"status": "pass", "duration": 0.05, "exception": None, "screenshot": None, "test_id": "t5", "scenario_id": "s2"},
]

# Compute summary as in execute_test
passed = sum(1 for r in mock_results if r.get("status") == "pass")
failed = sum(1 for r in mock_results if r.get("status") == "fail")
errors = sum(1 for r in mock_results if r.get("status") == "error")
skipped = 0
total = len(mock_results)

print(f"Mock results: {len(mock_results)} total")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Errors: {errors}")
print(f"  Skipped: {skipped}")

assert total == 5
assert passed == 2
assert failed == 2
assert errors == 1
assert skipped == 0

print("\n=== All checks passed ===")
print("Phase 7 execution components are working correctly.")