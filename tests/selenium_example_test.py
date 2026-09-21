import pytest
from app.selenium_engine.execution_service import ExecutionService


def test_google_search():
    """A simple Selenium test that searches Google."""
    def test_func(driver):
        driver.get("https://www.google.com")
        assert "Google" in driver.title
        # Find the search box
        search_box = driver.find_element("name", "q")
        search_box.send_keys("Agentic GenAI Framework")
        search_box.submit()
        # Wait for results to load
        driver.implicitly_wait(5)
        assert "Agentic GenAI Framework" in driver.title

    # Use the execution service to run the test
    with ExecutionService() as service:
        result = service.execute_test(test_func)

    # Assert that the test passed
    assert result["status"] == "pass", f"Test failed: {result['exception']}"
    # Optionally, you can assert on duration, etc.
    assert result["duration"] > 0
    # If the test failed, a screenshot would have been saved.
    # We don't assert on the screenshot here because we expect it to pass.
    # But we can check that no screenshot was taken on pass.
    assert result["screenshot"] is None
