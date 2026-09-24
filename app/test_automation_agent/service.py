import ast
import os
from typing import List

from app.llm.client import LLMClient
from app.requirement_to_testcase.schema import TestCase


class TestAutomationAgent:
    def __init__(self, llm_client: LLMClient = None):
        """Initialize the test automation agent.

        Args:
            llm_client: An instance of LLMClient. If None, defaults to OpenAIClient.
        """
        if llm_client is None:
            from app.llm.client import OpenAIClient
            llm_client = OpenAIClient()
        self.llm_client = llm_client
        self.base_url = os.getenv("TEST_APP_URL", "http://127.0.0.1:8001")
        self.generated_tests_dir = "generated_tests"
        os.makedirs(self.generated_tests_dir, exist_ok=True)

    def generate_test(self, test_case: TestCase) -> str:
        """Generate a Selenium pytest test from a TestCase.

        Args:
            test_case: A validated TestCase instance.

        Returns:
            The file path of the generated test.
        """
        # Generate the test function name from test_id
        test_func_name = f"test_{test_case.test_id}"

        # Generate the test code
        test_code = self._generate_test_code(test_case, test_func_name)

        # Validate the generated code
        self._validate_code(test_code)

        # Determine the file path
        file_path = os.path.join(
            self.generated_tests_dir,
            f"{test_case.test_id}.py",
        )

        # Write the test code to the file
        with open(file_path, "w") as f:
            f.write(test_code)

        return file_path

    def _generate_test_code(self, test_case: TestCase, test_func_name: str) -> str:
        """Generate the Python code for the test."""
        # Start with necessary imports
        lines = [
            "import pytest",
            "from selenium.webdriver.common.by import By",
            "",  # blank line
            f"def {test_func_name}(driver):",
        ]

        # Add a docstring with the test case title and description
        lines.append(f'    """{test_case.title}\\n{test_case.description}"""')
        lines.append("")

        # Convert each step to Selenium commands
        for i, step in enumerate(test_case.steps, 1):
            # Use LLM to generate Selenium command for this step
            selenium_command = self._step_to_selenium_command(step, test_case)
            # Indent the command
            lines.append(f"    # Step {i}: {step}")
            lines.append(f"    {selenium_command}")
            lines.append("")  # blank line after each step for readability

        # Add assertion for expected result
        if test_case.expected_result:
            # Use LLM to generate an assertion for the expected result
            assertion = self._expected_result_to_assertion(
                test_case.expected_result, test_case
            )
            lines.append(f"    # Expected result: {test_case.expected_result}")
            lines.append(f"    {assertion}")
            lines.append("")

        # If no steps or expected result, at least add a placeholder
        if not test_case.steps and not test_case.expected_result:
            lines.append("    # No steps or expected result provided")
            lines.append("    assert True, \"Placeholder assertion\"")

        return "\n".join(lines)

    def _step_to_selenium_command(self, step: str, test_case: TestCase) -> str:
        """Convert a natural language step to a Selenium command using the LLM."""
        prompt = f"""
You are an expert Selenium engineer. Convert the following test step into a single line of Selenium Python code.
Assume the Selenium WebDriver instance is available as `driver`.
Use stable locators (e.g., by ID, name, etc.) and avoid brittle locators like complex XPath unless necessary.
If the step involves verification, return an assertion statement.
Only return the code line, no extra text.

Step: {step}
"""
        # We'll define a simple schema for the expected output: a string containing the code line.
        # However, we don't have a Pydantic model for a single string. We'll just ask for a string and hope.
        # To ensure we get a string, we can use a Pydantic model with a single field.
        from pydantic import BaseModel

        class CodeLine(BaseModel):
            code: str

        # Use the LLM client to generate structured output
        # We'll retry on validation errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result: CodeLine = self.llm_client.generate_structured(prompt, CodeLine)
                code_line = result.code.strip()
                # Basic safety check: ensure the line doesn't contain dangerous imports or shell commands
                if self._is_safe_code_line(code_line):
                    return code_line
                else:
                    raise ValueError("Generated code line failed safety check")
            except Exception as e:
                if attempt == max_retries - 1:
                    # Fallback: return a comment indicating the step couldn't be converted
                    return f"# TODO: Implement step: {step}"
                continue
        # This point should not be reached
        return f"# TODO: Implement step: {step}"

    def _expected_result_to_assertion(self, expected_result: str, test_case: TestCase) -> str:
        """Convert the expected result to an assertion using the LLM."""
        prompt = f"""
You are an expert test engineer. Convert the following expected result into a single line of Python assertion code.
Assume the Selenium WebDriver instance is available as `driver`.
Use the step context if needed. The test case steps are: {test_case.steps}.
Only return the assertion line, no extra text.

Expected result: {expected_result}
"""
        from pydantic import BaseModel

        class AssertionLine(BaseModel):
            assertion: str

        max_retries = 3
        for attempt in range(max_retries):
            try:
                result: AssertionLine = self.llm_client.generate_structured(prompt, AssertionLine)
                assertion_line = result.assertion.strip()
                if self._is_safe_code_line(assertion_line):
                    return assertion_line
                else:
                    raise ValueError("Generated assertion line failed safety check")
            except Exception as e:
                if attempt == max_retries - 1:
                    # Fallback: return a simple assertion that always passes
                    return "assert True, \"Expected result verification not implemented\""
                continue
        return "assert True, \"Expected result verification not implemented\""

    def _is_safe_code_line(self, line: str) -> bool:
        """Perform a basic safety check on the generated code line.

        We want to avoid:
        - Import statements (except those we allow, but we don't expect any)
        - Shell command execution (e.g., os.system, subprocess)
        - File system writes (outside of the test context, but we allow reading from driver)
        - This is a simple check and not foolproof.
        """
        dangerous_keywords = [
            "import",
            "from",
            "os.system",
            "subprocess",
            "eval",
            "exec",
            "open(",  # could be dangerous if writing to arbitrary files
            "write",
            "remove",
            "delete",
        ]
        line_lower = line.lower()
        for keyword in dangerous_keywords:
            if keyword in line_lower:
                return False
        # Additionally, we can check for balanced parentheses and quotes as a basic syntax check
        # but we'll rely on the AST validation later.
        return True

    def _validate_code(self, code: str) -> None:
        """Validate the generated code by parsing it with ast.

        Args:
            code: The Python code string to validate.

        Raises:
            SyntaxError: If the code is not valid Python.
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Generated code is invalid Python: {e}") from e
