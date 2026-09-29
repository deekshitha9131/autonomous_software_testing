import time
import traceback
import os
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By


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
            result["browser_evidence"] = self._capture_browser_evidence(e)
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

    def _capture_browser_evidence(self, exception):
        if not self.driver:
            return None

        evidence = {}
        traceback_node = exception.__traceback__
        while traceback_node and traceback_node.tb_next:
            traceback_node = traceback_node.tb_next
        if traceback_node:
            frame_locals = traceback_node.tb_frame.f_locals
            assertion_values = {}
            for key in (
                "expected",
                "expected_value",
                "expected_result",
                "actual",
                "actual_value",
                "actual_text",
                "visible_text",
                "greeting_text",
                "inner_html",
                "alert_calls",
            ):
                value = frame_locals.get(key)
                if isinstance(value, str):
                    assertion_values[key] = value[:4000]
                elif isinstance(value, (int, float, bool)):
                    assertion_values[key] = value
                elif isinstance(value, list) and all(
                    isinstance(item, (str, int, float, bool)) for item in value
                ):
                    assertion_values[key] = value[:100]
            if assertion_values:
                evidence["assertion_values"] = assertion_values

        try:
            evidence["url"] = self.driver.current_url
            evidence["title"] = self.driver.title
            body = self.driver.find_element(By.TAG_NAME, "body")
            evidence["visible_text"] = body.text[:4000]
            evidence["body_text_content"] = self.driver.execute_script(
                "return document.body ? document.body.textContent : null"
            )
            if evidence["body_text_content"] is not None:
                evidence["body_text_content"] = evidence["body_text_content"][:4000]
            evidence["body_inner_html"] = self.driver.execute_script(
                "return document.body ? document.body.innerHTML : null"
            )
            if evidence["body_inner_html"] is not None:
                evidence["body_inner_html"] = evidence["body_inner_html"][:8000]
            evidence["script_alerts"] = self.driver.execute_script(
                "return window.__automation_test_alerts || []"
            )
        except WebDriverException as evidence_error:
            evidence["capture_error"] = str(evidence_error)
        return evidence
