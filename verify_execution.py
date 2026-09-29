import sys
sys.path.insert(0, 'D:/major project')

from app.selenium_engine.execution_service import ExecutionService

def passing_test(driver):
    pass

def failing_test(driver):
    raise AssertionError("Intentional failure")

def exception_test(driver):
    raise ValueError("Something broke")

print("Testing ExecutionService...")
with ExecutionService() as service:
    result = service.execute_test(passing_test)
    print("Passing test result:")
    print(f"  status: {result['status']}")
    print(f"  duration: {result['duration']}")
    print(f"  exception: {result['exception']}")
    print(f"  screenshot: {result['screenshot']}")

with ExecutionService() as service:
    result = service.execute_test(failing_test)
    print("\nFailing test result (AssertionError):")
    print(f"  status: {result['status']}")
    print(f"  duration: {result['duration']}")
    print(f"  exception: {result['exception']}")
    if result['exception']:
        print(f"    type: {result['exception']['type']}")
        print(f"    message: {result['exception']['message']}")
    print(f"  screenshot: {result['screenshot']}")

with ExecutionService() as service:
    result = service.execute_test(exception_test)
    print("\nFailing test result (ValueError):")
    print(f"  status: {result['status']}")
    print(f"  duration: {result['duration']}")
    print(f"  exception: {result['exception']}")
    if result['exception']:
        print(f"    type: {result['exception']['type']}")
        print(f"    message: {result['exception']['message']}")
    print(f"  screenshot: {result['screenshot']}")