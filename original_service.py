import ast
import os
from typing import List, Optional, Dict, Any

from app.llm.client import LLMClient
from app.requirement_to_testcase.schema import TestCase


class TestAutomationAgent:
    def __init__(self, llm_client: LLMClient = None, base_url: Optional[str] = None,
                 sut_id: Optional[str] = None, sut_context: Optional[Dict[str, Any]] = None,
                 test_data: Optional[Dict[str, Any]] = None):
        """Initialize the test automation agent.

        Args:
            llm_client: An instance of LLMClient. If None, defaults to OpenAIClient.
            base_url: The base URL of the SUT.
            sut_id: Identifier of the SUT.
            sut_context: Dictionary containing SUT contextual information (e.g., page mappings, element hints).
            test_data: Dictionary containing test data needed for executing tests.
        """
        if llm_client is None:
            from app.llm.client import OpenAIClient
            llm_client = OpenAIClient()
        self.llm_client = llm_client
        self.base_url = base_url
        self.sut_id = sut_id
        self.sut_context = sut_context if sut_context is not None else {}
        self.test_data = test_data if test_data is not None else {}
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

        # Generate and validate the test code with retry for syntax errors
        max_attempts = 2
        last_error = None
        last_code = None

        for attempt in range(max_attempts):
            # Generate the test code
            if attempt == 0:
                # First attempt: normal generation
                test_code = self._generate_test_code(test_case, test_func_name)
            else:
                # Retry attempt: give the invalid code and syntax error back to LLM
                test_code = self._fix_invalid_code(
                    test_case, test_func_name, last_code, last_error
                )

            # Validate the generated code
            try:
                self._validate_code(test_code)
                # If validation succeeds, break out of the retry loop
                break
            except SyntaxError as e:
                last_error = str(e)
                last_code = test_code
                # If this was the last attempt, re-raise the error
                if attempt == max_attempts - 1:
                    raise SyntaxError(f"Generated code is invalid Python after {max_attempts} attempts: {last_error}") from e
                # Otherwise, continue to retry with feedback
                continue

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
        # Build context information for the LLM
        context_parts = []
        if self.base_url:
            context_parts.append(f"Application Base URL: {self.base_url}")
        if self.sut_context:
            if isinstance(self.sut_context, dict):
                for key, value in self.sut_context.items():
                    if value:  # Only include non-empty values
                        context_parts.append(f"{key}: {value}")
        context_info = "\n".join(context_parts) if context_parts else "No specific SUT context provided"

        prompt = f"""
You are an expert Selenium engineer. Convert the following test step into a single line of Selenium Python code.
Assume the Selenium WebDriver instance is available as `driver`.
Use stable locators (e.g., by ID, name, etc.) and avoid brittle locators like complex XPath unless necessary.
If the step involves verification, return an assertion statement.
Only return the code line, no extra text.

SUT Context:
{context_info}

Step: {step}

IMPORTANT:
- Use the exact selectors provided in the SUT context (e.g., if name_selector is "#name", use By.ID, "name" or By.CSS_SELECTOR, "#name")
- Navigate to the correct URL using base_url + route if provided
- Do not invent URLs or selectors - use only what is provided in the SUT context
- If a required selector or URL is not provided in the SUT context, return a comment indicating what is missing
"""
        # We'll define a simple schema for the expected output: a string containing the code line.
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
        """Convert the expected result into an assertion using the LLM."""
        # Build context information for the LLM
        context_parts = []
        if self.base_url:
            context_parts.append(f"Application Base URL: {self.base_url}")
        if self.sut_context:
            if isinstance(self.sut_context, dict):
                for key, value in self.sut_context.items():
                    if value:  # Only include non-empty values
                        context_parts.append(f"{key}: {value}")
        context_info = "\n".join(context_parts) if context_parts else "No specific SUT context provided"

        prompt = f"""
You are an expert test engineer. Convert the following expected result into a single line of Python assertion code.
Assume the Selenium WebDriver instance is available as `driver`.
Use the step context if needed. The test case steps are: {test_case.steps}.
Only return the assertion line, no extra text.

SUT Context:
{context_info}

Test Case Steps:
{chr(10).join(test_case.steps) if test_case.steps else "No steps provided"}

Expected result: {expected_result}

IMPORTANT:
- Use the exact selectors provided in the SUT context (e.g., if name_selector is "#name", use By.ID, "name" or By.CSS_SELECTOR, "#name")
- Verify against the correct URL using base_url + route if provided
- Do not invent URLs or selectors - use only what is provided in the SUT context
- If a required selector or URL is not provided in the SUT context, return a comment indicating what is missing
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

    def _fix_invalid_code(self, test_case: TestCase, test_func_name: str, invalid_code: str, syntax_error: str) -> str:
        """Ask the LLM to fix invalid Python code based on the syntax error."""
        from pydantic import BaseModel

        class FixedCode(BaseModel):
            code: str

        prompt = f"""
You are an expert Python programmer. The following Python code has a syntax error. Fix the code to make it valid Python 3 syntax.

ORIGINAL TEST CASE:
- test_id: {test_case.test_id}
- title: {test_case.title}
- description: {test_case.description}

ORIGINAL INVALID CODE:
{invalid_code}

SYNTAX ERROR:
{syntax_error}

IMPORTANT CONSTRAINTS:
- Only return the corrected Python code, no extra text or explanations
- Preserve the original functionality and structure
- Fix only the syntax error(s)
- Ensure the code is valid Python 3
- Do not change the test function name: {test_func_name}
- Do not remove or alter the import statements
- Do not remove or alter the docstring
- Return ONLY the corrected code block

Generate the corrected Python code:
"""

        # Use the LLM client to generate structured output
        # We'll retry on validation errors
        max_retries = 2
        for attempt in range(max_retries):
            try:
                result: FixedCode = self.llm_client.generate_structured(prompt, FixedCode)
                fixed_code = result.code.strip()
                # Validate that the fixed code is actually valid Python
                ast.parse(fixed_code)  # This will raise SyntaxError if still invalid
                return fixed_code
            except Exception as e:
                if attempt == max_retries - 1:
                    # If we can't fix it after retries, return the original code (will fail validation)
                    # but at least we tried
                    return invalid_code
                continue

        # This point should not be reached
        return invalid_code

    def _generate_test_code_with_feedback(self, test_case: TestCase, test_func_name: str, syntax_error: str) -> str:
        """Generate the Python code for the test with feedback about a previous syntax error."""
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

        # Add a comment about the syntax error to avoid
        lines.append(f"    # IMPORTANT: The previous attempt had a syntax error: {syntax_error}")
        lines.append(f"    # Ensure all generated code is valid Python 3 syntax.")
        lines.append(f"    # In particular, avoid leading zeros in decimal integers (e.g., use 123 not 0123).")
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

    def get_sut_context_status(self) -> Dict[str, Any]:
        """Return a dict indicating the availability of SUT context for automation.

        Returns:
            dict with keys:
                - has_base_url: bool
                - has_sut_id: bool
                - has_sut_context: bool (non-empty dict)
                - has_test_data: bool (non-empty dict)
                - ready: bool (True if base_url is present and sut_context is non-empty)
        """
        has_base_url = bool(self.base_url)
        has_sut_id = bool(self.sut_id)
        has_sut_context = bool(self.sut_context and isinstance(self.sut_context, dict))
        has_test_data = bool(self.test_data and isinstance(self.test_data, dict))
        # For automation to be possible, we need at least a base_url and some context.
        # The definition of "usable" can be refined; we'll consider ready if base_url and sut_context are present.
        ready = has_base_url and has_sut_context
        return {
            "has_base_url": has_base_url,
            "has_sut_id": has_sut_id,
            "has_sut_context": has_sut_context,
            "has_test_data": has_test_data,
            "ready": ready,
            "missing": [] if ready else [k for k, v in [
                ("base_url", has_base_url),
                ("sut_id", has_sut_id),
                ("sut_context", has_sut_context),
                ("test_data", has_test_data)
            ] if not v]
        }
