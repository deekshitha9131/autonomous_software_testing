import pytest
from unittest.mock import Mock, patch
from app.selenium_engine.execution_service import ExecutionService


@patch("app.selenium_engine.driver.webdriver")
@patch("app.selenium_engine.driver.ChromeDriverManager")
@patch("app.selenium_engine.driver.ChromeService")
def test_execution_service_init(mock_chrome_service, mock_driver_manager, mock_webdriver):
    """Test that the ExecutionService initializes correctly."""
    service = ExecutionService()
    assert service.driver_func is not None
    # We can't easily test the driver creation without more mocking, but we can
    # test that the service is instantiated.


def test_execution_service_context_manager():
    """Test that the ExecutionService can be used as a context manager."""
    with ExecutionService() as service:
        assert service.driver is not None
    # After context, driver should be quit (we can't easily test without mocking)


@patch("app.selenium_engine.execution_service.os")
@patch("app.selenium_engine.execution_service.time")
def test_execution_service_execute_test_pass(mock_time, mock_os):
    """Test executing a passing test."""
    mock_time.time.side_effect = [1000.0, 1001.0]  # start, end
    mock_os.makedirs.return_value = None

    # Mock driver
    mock_driver = Mock()

    # Define a simple test function that does nothing
    def test_func(driver):
        pass

    service = ExecutionService()
    service.driver = mock_driver

    result = service.execute_test(test_func)

    assert result["status"] == "pass"
    assert result["exception"] is None
    assert result["duration"] == 1.0
    assert result["screenshot"] is None


@patch("app.selenium_engine.execution_service.os")
@patch("app.selenium_engine.execution_service.time")
def test_execution_service_execute_test_fail(mock_time, mock_os):
    """Test executing a failing test."""
    mock_time.time.side_effect = [1000.0, 1001.0]
    mock_os.makedirs.return_value = None
    mock_os.path.join.return_value = "test_results/screenshot.png"

    # Mock driver
    mock_driver = Mock()
    mock_driver.save_screenshot = Mock()

    # Define a test function that raises an exception
    def test_func(driver):
        raise ValueError("Test error")

    service = ExecutionService()
    service.driver = mock_driver

    result = service.execute_test(test_func)

    assert result["status"] == "fail"
    assert result["exception"]["type"] == "ValueError"
    assert result["exception"]["message"] == "Test error"
    assert "Traceback" in result["exception"]["traceback"]
    assert result["duration"] == 1.0
    assert result["screenshot"] == "test_results/screenshot.png"
    mock_driver.save_screenshot.assert_called_once_with("test_results/screenshot.png")
