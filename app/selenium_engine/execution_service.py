import time
import traceback
import os
from selenium.common.exceptions import WebDriverException


class ExecutionService:
    def __init__(self, driver_func=None):
        """
        Initialize the execution service.
        :param driver_func: A function that returns a WebDriver instance.
                            If None, defaults to get_chrome_driver.
        """
        from .driver import get_chrome_driver
        self.driver_func = driver_func or get_chrome_driver
        self.driver = None

    def __enter__(self):
        self.driver = self.driver_func()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()

    def execute_test(self, test_func, *args, **kwargs):
        """
        Execute a test function and capture results.
        :param test_func: A function that takes a driver and performs the test.
        :param args: Positional arguments to pass to test_func.
        :param kwargs: Keyword arguments to pass to test_func.
        :return: A dictionary containing the test results.
        """
        start_time = time.time()
        result = {
            "status": "pass",
            "exception": None,
            "duration": 0,
            "screenshot": None,
            "stdout": None,
            "stderr": None,
        }
        try:
            # Execute the test function
            test_func(self.driver, *args, **kwargs)
        except Exception as e:
            result["status"] = "fail"
            result["exception"] = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            # Take a screenshot on failure
            if self.driver:
                try:
                    # Ensure test_results directory exists
                    os.makedirs("test_results", exist_ok=True)
                    screenshot_path = os.path.join(
                        "test_results",
                        f"screenshot_{int(start_time)}_{result['status']}.png",
                    )
                    self.driver.save_screenshot(screenshot_path)
                    result["screenshot"] = screenshot_path
                except Exception:
                    pass
        finally:
            end_time = time.time()
            result["duration"] = end_time - start_time
            # Note: Capturing stdout/stderr is platform-specific and complex.
            # For simplicity, we leave them as None. In a real scenario, we might
            # redirect sys.stdout and sys.stderr to capture them.
        return result
