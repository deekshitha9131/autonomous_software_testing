import ast
import json
import os
import re
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
                self._validate_code(test_code, test_case)
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

        # Post-process: enforce exactly one navigation before any element interaction
        target_url = self._build_target_url(test_case)
        if target_url:
            test_code = self._deduplicate_navigation(test_code, target_url)
            test_code = self._ensure_navigation(test_code, target_url)

        # Determine the file path
        file_path = os.path.join(
            self.generated_tests_dir,
            f"{test_case.test_id}.py",
        )

        # Write the test code to the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        return file_path

    def _generate_test_code(self, test_case: TestCase, test_func_name: str) -> str:
        """Generate the Python code for the test."""
        sut_context = self._context_for_test_case(test_case)
        security_code = self._generate_script_injection_test(
            test_case, test_func_name, sut_context
        )
        if security_code is not None:
            return security_code

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

        # Navigate to the target URL if base_url and route are provided
        target_url = self._build_target_url(test_case)
        if target_url:
            lines.append(f"    driver.get(\"{target_url}\")")
            lines.append("")  # blank line

        # Convert each step to Selenium commands
        for i, step in enumerate(test_case.steps, 1):
            # Use LLM to generate Selenium command for this step
            selenium_command = self._step_to_selenium_command(step, test_case)
            if test_case.expected_result and selenium_command.lstrip().startswith("assert "):
                continue
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

    def _generate_script_injection_test(
        self, test_case: TestCase, test_func_name: str, sut_context
    ) -> Optional[str]:
        payload = next(
            (
                item.value if hasattr(item, "value") else item.get("value")
                for item in (test_case.test_data or [])
                if isinstance(item.value if hasattr(item, "value") else item.get("value"), str)
                and "<script" in (item.value if hasattr(item, "value") else item.get("value")).lower()
            ),
            None,
        )
        if payload is None or not isinstance(sut_context, dict):
            return None

        name_selector = sut_context.get("name_selector")
        submit_selector = sut_context.get("submit_selector")
        greeting_selector = sut_context.get("greeting_selector")
        greeting_template = self._greeting_template(sut_context)
        target_url = self._build_target_url(test_case)
        if not all((name_selector, submit_selector, greeting_selector, target_url)):
            return None

        return "\n".join(
            [
                "import pytest",
                "from selenium.webdriver.common.by import By",
                "",
                f"def {test_func_name}(driver):",
                f'    """{test_case.title}\\n{test_case.description}"""',
                "    driver.execute_cdp_cmd(",
                '        "Page.addScriptToEvaluateOnNewDocument",',
                '        {"source": "window.__automation_test_alerts = []; window.alert = function(message) { window.__automation_test_alerts.push(String(message)); };"},',
                "    )",
                f"    driver.get({target_url!r})",
                f"    driver.find_element(By.CSS_SELECTOR, {name_selector!r}).send_keys({payload!r})",
                f"    driver.find_element(By.CSS_SELECTOR, {submit_selector!r}).click()",
                f"    greeting = driver.find_element(By.CSS_SELECTOR, {greeting_selector!r})",
                "    visible_text = greeting.text",
                '    text_content = greeting.get_attribute("textContent") or ""',
                '    inner_html = greeting.get_attribute("innerHTML") or ""',
                '    alert_calls = driver.execute_script("return window.__automation_test_alerts || []")',
                f"    expected_visible_text = {greeting_template.format(name=payload)!r}",
                '    assert visible_text == expected_visible_text, f"Expected visible text {expected_visible_text!r}; got {visible_text!r}"',
                f"    assert {payload!r} in text_content, f\"Expected submitted payload in textContent; got {{text_content!r}}\"",
                '    assert "&lt;" in inner_html and "&gt;" in inner_html, f"Expected escaped markup in innerHTML; got {inner_html!r}"',
                '    assert alert_calls == [], f"Unexpected JavaScript alert calls: {alert_calls!r}"',
            ]
        )

    def _greeting_template(self, sut_context: Dict[str, Any]) -> Optional[str]:
        template = sut_context.get("greeting_template")
        if template:
            return template
        reference_name = self.test_data.get("name") if isinstance(self.test_data, dict) else None
        expected_behavior = sut_context.get("expected_behavior", "")
        if isinstance(reference_name, str) and reference_name:
            match = re.search(
                rf"(Hello,\s*){re.escape(reference_name)}([.!?])",
                expected_behavior,
                flags=re.IGNORECASE,
            )
            if match:
                return f"{match.group(1)}{{name}}{match.group(2)}"
        return None

    def _step_to_selenium_command(self, step: str, test_case: TestCase) -> str:
        """Convert a natural language step to a Selenium command using the LLM."""
        # Build context information for the LLM
        context_parts = []
        if self.base_url:
            context_parts.append(f"Application Base URL: {self.base_url}")
        sut_context = self._context_for_test_case(test_case)
        if sut_context:
            if isinstance(sut_context, dict):
                for key, value in sut_context.items():
                    if value:  # Only include non-empty values
                        context_parts.append(f"{key}: {value}")
        # Add test data to context if available
        if hasattr(test_case, 'test_data') and test_case.test_data:
            test_data_str = self._format_test_data_for_llm(test_case.test_data)
            if test_data_str:
                context_parts.append(f"Test Data: {test_data_str}")
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
- Do NOT generate driver.get() navigation calls. Navigation is handled separately.
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
        sut_context = self._context_for_test_case(test_case)
        if isinstance(sut_context, dict):
            test_data = {
                item.key: item.value
                for item in (test_case.test_data or [])
            }
            input_value = test_data.get("name")
            greeting_selector = sut_context.get("greeting_selector")
            greeting_template = self._greeting_template(sut_context)
            empty_greeting = sut_context.get("empty_name_behavior")
            if isinstance(input_value, str) and greeting_selector and greeting_template:
                expected_greeting = (
                    empty_greeting
                    if not input_value.strip() and empty_greeting
                    else greeting_template.format(name=input_value.strip())
                )
                return (
                    f"assert driver.find_element(By.CSS_SELECTOR, {greeting_selector!r}).text "
                    f"== {expected_greeting!r}"
                )

        # Build context information for the LLM
        context_parts = []
        if self.base_url:
            context_parts.append(f"Application Base URL: {self.base_url}")
        if sut_context:
            if isinstance(sut_context, dict):
                for key, value in sut_context.items():
                    if value:  # Only include non-empty values
                        context_parts.append(f"{key}: {value}")
        # Add test data to context if available
        if hasattr(test_case, 'test_data') and test_case.test_data:
            test_data_str = self._format_test_data_for_llm(test_case.test_data)
            if test_data_str:
                context_parts.append(f"Test Data: {test_data_str}")
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
- Do NOT generate driver.get() navigation calls. Navigation is handled separately.
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

    def _format_test_data_for_llm(self, test_data_list) -> str:
        """Format test data as a readable string for LLM context.

        Args:
            test_data_list: List of TestDataItem objects or list of dicts with key/value

        Returns:
            Formatted string like "key1=value1, key2=value2"
        """
        if not test_data_list:
            return ""

        formatted_items = []
        for item in test_data_list:
            # Handle both TestDataItem objects and dict-like objects
            if hasattr(item, 'key') and hasattr(item, 'value'):
                key = item.key
                value = item.value
            elif isinstance(item, dict) and 'key' in item and 'value' in item:
                key = item['key']
                value = item['value']
            else:
                # Skip items that don't match expected format
                continue

            # Format the value appropriately for display
            if isinstance(value, str):
                # Escape quotes and limit length for readability
                formatted_value = f"'{value}'" if len(value) < 50 else f"'{value[:47]}...'"
            else:
                formatted_value = str(value)

            formatted_items.append(f"{key}={formatted_value}")

        return ", ".join(formatted_items)

    def _is_safe_code_line(self, line: str) -> bool:
        """Perform a basic safety check on the generated code line.

        We want to avoid:
        - Import statements (except those we allow, but we don't expect any)
        - Shell command execution (e.g., os.system, subprocess)
        - File system writes (outside of the test context, but we allow reading from driver)
        - This is a simple check and not foolproof.
        """
        # More precise dangerous patterns to avoid false positives
        dangerous_patterns = [
            r'\bimport\b',           # standalone import
            r'\bfrom\b',             # standalone from
            r'\bos\s*\.\s*system\b', # os.system
            r'\bsubprocess\b',       # subprocess
            r'\beval\b',             # eval
            r'\bexec\b(?!_[a-zA-Z])', # exec but not exec_* (like execute_script)
            r'open\s*\(',            # open(
            r'\bwrite\b',            # write
            r'\bremove\b',           # remove
            r'\bdelete\b',           # delete
        ]

        line_lower = line.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, line_lower):
                return False
        return True

    def _context_for_test_case(self, test_case: TestCase) -> Dict[str, Any]:
        context = dict(self.sut_context or {})
        route = test_case.route
        routes = context.get("routes")
        if isinstance(routes, dict) and not route:
            raise ValueError("Test case must select a route from the SUT route catalog")
        if route and isinstance(routes, dict):
            route_context = routes.get(route)
            if not isinstance(route_context, dict):
                raise ValueError(f"Test case route {route!r} is not in the SUT route catalog")
            context.update(route_context)
            context["route"] = route
        elif route:
            configured_route = context.get("route")
            if configured_route and configured_route != route:
                raise ValueError(
                    f"Test case route {route!r} conflicts with configured SUT route {configured_route!r}"
                )
            context["route"] = route
        return context

    def _build_target_url(
        self, test_case: Optional[TestCase] = None
    ) -> Optional[str]:
        """Build the target URL from base_url and sut_context route.

        Returns:
            The full target URL string, or None if base_url or route is missing.
        """
        if not self.base_url:
            return None
        context = (
            self._context_for_test_case(test_case)
            if test_case is not None
            else self.sut_context
        )
        route = context.get('route') if isinstance(context, dict) else None
        if not route:
            return None
        return self.base_url.rstrip('/') + '/' + route.lstrip('/')

    def _ensure_navigation(self, code: str, target_url: str) -> str:
        """Ensure driver.get(target_url) appears before the first element interaction.

        Scans the assembled code for element-interaction lines (find_element,
        find_elements, send_keys, click, page assertions) and inserts a
        driver.get() call before the first one if none already exists above it.

        Args:
            code: The assembled Python test code.
            target_url: The full URL to navigate to.

        Returns:
            The code with navigation enforced.
        """
        lines = code.split('\n')

        # Patterns that constitute element interaction requiring a loaded page
        interaction_pattern = re.compile(
            r'\b(find_element|find_elements|send_keys|click|'  # Selenium interactions
            r'assert.*driver|assert.*element|assert.*text|'    # Page assertions
            r'driver\.execute_script|driver\.switch_to|'      # Other page-dependent calls
            r'Select\(|ActionChains\()'
        )
        navigation_pattern = re.compile(r'driver\.get\s*\(')

        first_interaction_idx = None
        has_navigation_before = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip comments and blank lines
            if not stripped or stripped.startswith('#'):
                continue
            # Check for navigation
            if navigation_pattern.search(stripped):
                if first_interaction_idx is None:
                    # Navigation found before any interaction — already OK
                    has_navigation_before = True
                    break
            # Check for interaction
            if interaction_pattern.search(stripped) and first_interaction_idx is None:
                first_interaction_idx = i

        # If there's an interaction but no navigation before it, insert one
        if first_interaction_idx is not None and not has_navigation_before:
            # Detect indentation from the interaction line
            interaction_line = lines[first_interaction_idx]
            indent = len(interaction_line) - len(interaction_line.lstrip())
            indent_str = ' ' * indent
            nav_line = f'{indent_str}driver.get("{target_url}")'
            comment_line = f'{indent_str}# Navigate to the target URL'
            lines.insert(first_interaction_idx, '')
            lines.insert(first_interaction_idx, nav_line)
            lines.insert(first_interaction_idx, comment_line)

        return '\n'.join(lines)

    def _deduplicate_navigation(self, code: str, target_url: str) -> str:
        """Remove duplicate driver.get() calls, keeping only the first one.

        LLM-generated step code may include driver.get() calls even though
        navigation is handled separately by _generate_test_code and
        _ensure_navigation. This strips all but the first driver.get() to
        prevent page reloads between steps.

        Args:
            code: The assembled Python test code.
            target_url: The target URL (used to identify navigation lines).

        Returns:
            Code with only the first driver.get() retained.
        """
        lines = code.split('\n')
        navigation_pattern = re.compile(r'\s*driver\.get\s*\(')
        first_nav_found = False
        result_lines = []

        for line in lines:
            if navigation_pattern.match(line):
                if not first_nav_found:
                    first_nav_found = True
                    result_lines.append(line)
                else:
                    # Skip duplicate navigation — do not add this line
                    continue
            else:
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _validate_code(self, code: str, test_case: TestCase) -> None:
        """Validate the generated code by parsing it with ast.

        Args:
            code: The Python code string to validate.
            test_case: The TestCase object containing expected result and other metadata.

        Raises:
            SyntaxError: If the code is not valid Python or contains placeholder content.
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Generated code is invalid Python: {e}") from e

        # Check for placeholder content that indicates incomplete generation
        # More precise checks to avoid false positives
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check for TODO comments
            if stripped.startswith('# TODO'):
                raise SyntaxError(f"Generated code contains placeholder content: {stripped}")

            # Check for pass with placeholder comments
            if stripped == 'pass' or (stripped.startswith('pass ') and '#' in stripped):
                # More specific check for placeholder pass statements
                if '#' in stripped and any(placeholder in stripped.lower() for placeholder in ['placeholder', 'todo', 'fixme', 'xxx']):
                    raise SyntaxError(f"Generated code contains placeholder content: {stripped}")
                elif stripped == 'pass' and line_num < len(lines):
                    # Check if this pass is likely a placeholder by looking at surrounding context
                    # For now, we'll be conservative and only flag explicit placeholder passes
                    pass

            # Check for explicit placeholder assertions
            if stripped.startswith('assert True') and ('placeholder' in stripped.lower() or
                                                     'not implemented' in stripped.lower() or
                                                     stripped.strip() == 'assert True'):
                raise SyntaxError(f"Generated code contains placeholder content: {stripped}")

        # Validate Selenium locator usage - check for incorrect find_element/find_elements calls
        # Invalid patterns: find_element("..."), find_element('...'), find_elements("..."), find_elements('...')
        # These are missing the required locator strategy (By.ID, By.CSS_SELECTOR, etc.)
        import re
        invalid_patterns = [
            r'find_element\s*\(\s*["\']',  # find_element("...") or find_element('...')
            r'find_elements\s*\(\s*["\']',  # find_elements("...") or find_elements('...')
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, code):
                raise SyntaxError(f"Generated code contains invalid Selenium locator syntax. "
                                f"find_element/find_elements calls must include a locator strategy "
                                f"(e.g., By.ID, By.CSS_SELECTOR) as the first argument.")

        # Selector grounding validation - ensure selectors are from authoritative sut_context
        self._validate_selector_grounding(code, test_case)

        # Check for meaningful expected result and require executable verification
        self._verify_executable_verification(code, test_case)

    def _verify_executable_verification(self, code: str, test_case: TestCase) -> None:
        """Verify that the generated code contains executable verification when expected result is meaningful.

        Args:
            code: The Python code string to validate.
            test_case: The TestCase object containing expected result and other metadata.

        Raises:
            SyntaxError: If no executable verification is found when required.
        """
        # Check if test_case has a meaningful expected result
        if not self._has_meaningful_expected_result(test_case):
            # If no meaningful expected result, no verification is required
            return

        # Check if code contains executable verification
        if not self._contains_executable_verification(code):
            raise SyntaxError(
                "Generated test lacks executable verification for expected result. "
                "Expected result requires executable verification (e.g., assert statement), "
                "but only comments or non-verification code was found."
            )

    def _has_meaningful_expected_result(self, test_case: TestCase) -> bool:
        """Check if the test case has a meaningful expected result requiring verification.

        Args:
            test_case: The TestCase object to check.

        Returns:
            True if expected result is meaningful and requires verification, False otherwise.
        """
        expected_result = getattr(test_case, 'expected_result', None)

        # Check if expected_result exists and is meaningful
        if not expected_result:
            return False

        if not isinstance(expected_result, str):
            return False

        # Strip whitespace
        expected_result = expected_result.strip()

        # Check if empty after stripping
        if not expected_result:
            return False

        # Check for placeholder-like expected results that don't require verification
        placeholder_indicators = [
            'no specific expected result',
            'none',
            'not applicable',
            'n/a',
            'no verification needed',
            'verification not required',
            'see steps for verification',
            'verified in previous steps'
        ]

        expected_lower = expected_result.lower()
        for indicator in placeholder_indicators:
            if indicator in expected_lower:
                return False

        # If we got here, the expected result is meaningful
        return True

    def _contains_executable_verification(self, code: str) -> bool:
        """Check if the code contains executable verification.

        Args:
            code: The Python code string to check.

        Returns:
            True if executable verification is found, False otherwise.
        """
        lines = code.split('\n')

        for line in lines:
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                continue

            # Check for assert statements
            if stripped.startswith('assert '):
                # Make sure it's not a placeholder assertion
                if not ('placeholder' in stripped.lower() or
                       'not implemented' in stripped.lower()):
                    return True

            # Check for pytest.raises calls
            if 'pytest.raises(' in stripped:
                return True

            # Check for raise statements (explicit exception raising)
            if stripped.startswith('raise '):
                return True

            # Check for other verification patterns if needed
            # For example, calls to validation methods that return booleans used in conditionals
            # But we'll keep it simple for now to avoid false positives

        # No executable verification found
        return False

    def _fix_invalid_code(self, test_case: TestCase, test_func_name: str, invalid_code: str, syntax_error: str) -> str:
        """Ask the LLM to repair generated code using the validation feedback."""
        from pydantic import BaseModel

        class FixedCode(BaseModel):
            code: str

        prompt = f"""
You are an expert Selenium test engineer. Repair the generated test code to address the reported validation failure.

ORIGINAL TEST CASE:
- test_id: {test_case.test_id}
- title: {test_case.title}
- description: {test_case.description}
- steps: {test_case.steps}
- expected_result: {test_case.expected_result}
- test_data: {self._format_test_data_for_llm(test_case.test_data)}

AUTHORITATIVE SUT CONTEXT:
{json.dumps(self._context_for_test_case(test_case), indent=2, ensure_ascii=True)}

ORIGINAL INVALID CODE:
{invalid_code}

VALIDATION ERROR:
{syntax_error}

IMPORTANT CONSTRAINTS:
- Only return the corrected Python code, no extra text or explanations
- Preserve the original functionality and structure
- Fix the reported validation failure, not just Python syntax
- Ensure the code is valid Python 3
- Use only selectors explicitly present in the authoritative SUT context; never invent selectors
- Use the route-specific selectors appropriate for this test case
- Preserve the test case's expected result and test data
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

    def _validate_selector_grounding(self, code: str, test_case: TestCase) -> None:
        """Validate that Selenium selectors used in the code are grounded in the authoritative sut_context.

        Args:
            code: The Python code string to validate.

        Raises:
            SyntaxError: If selectors are used that are not grounded in the sut_context.
        """
        # If no sut_context is provided, skip selector grounding validation
        sut_context = self._context_for_test_case(test_case)
        if not sut_context:
            return

        # Extract authoritative selectors from sut_context
        authoritative_selectors = self._extract_authoritative_selectors(sut_context)

        # If no authoritative selectors found, skip validation (preserve existing behavior)
        if not authoritative_selectors:
            return

        # Extract all selectors used in find_element and find_elements calls
        used_selectors = self._extract_used_selectors(code)

        # Check each used selector against authoritative selectors
        for strategy, selector in used_selectors:
            if not self._is_selector_grounded(strategy, selector, authoritative_selectors):
                # Build helpful error message
                selector_repr = self._format_selector_for_error(strategy, selector)
                auth_selectors_repr = ", ".join(
                    sorted([self._format_selector_for_error(s, sel) for s, sel in authoritative_selectors])
                )
                raise SyntaxError(
                    f"Generated Selenium uses selector {selector_repr} which is not grounded in authoritative SUT context. "
                    f"Authorized selectors: {auth_selectors_repr}"
                )

    def _extract_authoritative_selectors(self, sut_context=None) -> list[tuple[str, str]]:
        """Extract selector values from sut_context.

        Returns:
            List of (strategy, selector) tuples representing authoritative selectors.
        """
        selectors = []

        sut_context = self.sut_context if sut_context is None else sut_context
        if not isinstance(sut_context, dict):
            return selectors

        # Look for keys that likely contain selectors (ending with _selector or containing selector-related terms)
        for key, value in sut_context.items():
            if not isinstance(value, str):
                continue

            # Prefer keys ending with _selector
            if key.endswith('_selector') and value.strip():
                # Treat the value as a CSS selector string
                selectors.append(('css selector', value.strip()))
            # Also check for common selector-related keys
            elif any(term in key.lower() for term in ['selector', 'locator']) and value.strip():
                # Try to determine if it's a CSS selector, XPath, etc.
                # For simplicity, treat as CSS selector if it looks like one
                if value.startswith('#') or value.startswith('.') or '[' in value:
                    selectors.append(('css selector', value.strip()))
                else:
                    # Default to treating as CSS selector
                    selectors.append(('css selector', value.strip()))

        return selectors

    def _extract_used_selectors(self, code: str) -> list[tuple[str, str]]:
        """Extract all selectors used in find_element and find_elements calls.

        Args:
            code: The Python code string to analyze.

        Returns:
            List of (strategy, selector) tuples representing used selectors.
        """
        import re
        selectors = []

        # Pattern to match find_element and find_elements calls
        # Matches: find_element(By.ID, "name"), find_elements(By.CSS_SELECTOR, "#submit"), etc.
        pattern = r'find_element\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)|find_elements\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)'

        for match in re.finditer(pattern, code):
            # Groups 1,2 are for find_element; Groups 3,4 are for find_elements
            if match.group(1) is not None:  # find_element
                strategy_str = match.group(1).strip()
                selector_str = match.group(2).strip()
            else:  # find_elements
                strategy_str = match.group(3).strip()
                selector_str = match.group(4).strip()

            # Parse the strategy (e.g., By.ID -> "id")
            strategy = self._parse_by_strategy(strategy_str)
            if strategy is None:
                # If we can't parse the strategy, skip validation for this call
                # The existing locator strategy validation will catch invalid strategies
                continue

            # Parse the selector (remove quotes)
            selector = self._parse_selector_string(selector_str)
            if selector is None:
                # If we can't parse the selector, skip validation for this call
                continue

            selectors.append((strategy, selector))

        return selectors

    def _parse_by_strategy(self, strategy_str: str) -> str | None:
        """Parse By.XXX strategy string to lowercase strategy name.

        Args:
            strategy_str: String like "By.ID", "By.CSS_SELECTOR", etc.

        Returns:
            Lowercase strategy name (e.g., "id", "css selector") or None if invalid.
        """
        strategy_str = strategy_str.strip()
        # Remove By. prefix if present
        if strategy_str.startswith('By.'):
            strategy_str = strategy_str[3:]

        # Map to lowercase strategy names used by Selenium
        strategy_mapping = {
            'ID': 'id',
            'CSS_SELECTOR': 'css selector',
            'XPATH': 'xpath',
            'NAME': 'name',
            'TAG_NAME': 'tag name',
            'CLASS_NAME': 'class name',
            'LINK_TEXT': 'link text',
            'PARTIAL_LINK_TEXT': 'partial link text'
        }

        return strategy_mapping.get(strategy_str.upper())

    def _parse_selector_string(self, selector_str: str) -> str | None:
        """Parse selector string, removing quotes.

        Args:
            selector_str: String like '"name"', "'#submit'", etc.

        Returns:
            Selector string without quotes or None if invalid.
        """
        selector_str = selector_str.strip()
        # Remove surrounding quotes (both single and double)
        if (selector_str.startswith('"') and selector_str.endswith('"')) or \
           (selector_str.startswith("'") and selector_str.endswith("'")):
            return selector_str[1:-1]
        return None

    def _is_selector_grounded(self, strategy: str, selector: str, authoritative_selectors: list[tuple[str, str]]) -> bool:
        """Check if a selector is grounded in the authoritative selectors.

        Args:
            strategy: Strategy name (e.g., "id", "css selector")
            selector: Selector value (e.g., "name", "#say-hello")
            authoritative_selectors: List of authorized (strategy, selector) tuples

        Returns:
            True if selector is grounded, False otherwise.
        """
        # Normalize the strategy for comparison
        strategy = strategy.lower().strip()
        selector = selector.strip()

        # Check for exact match first
        if (strategy, selector) in authoritative_selectors:
            return True

        # Check for safe equivalences
        # #name ↔ By.ID, "name" ↔ By.CSS_SELECTOR, "#name"
        if strategy == 'id' and not selector.startswith('#'):
            # Generated uses By.ID, "name" - check if authoritative has it as CSS selector "#name"
            css_selector = ('css selector', '#' + selector)
            if css_selector in authoritative_selectors:
                return True
        elif strategy == 'css selector' and selector.startswith('#'):
            # Generated uses By.CSS_SELECTOR, "#name" - check if authoritative has it as ID "name"
            # Remove # and check if it's a valid ID
            id_value = selector[1:]
            if id_value and self._is_valid_id(id_value):
                id_selector = ('id', id_value)
                if id_selector in authoritative_selectors:
                    return True

        return False

    def _is_valid_id(self, value: str) -> bool:
        """Check if a string is a valid CSS ID identifier.

        Args:
            value: String to check (without the # prefix)

        Returns:
            True if valid ID, False otherwise.
        """
        if not value:
            return False
        # CSS ID must start with letter ([a-zA-Z]) followed by letters, digits, hyphens, underscores
        import re
        return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', value))

    def _format_selector_for_error(self, strategy: str, selector: str) -> str:
        """Format a selector for inclusion in error messages.

        Args:
            strategy: Strategy name (e.g., "id", "css selector")
            selector: Selector value (e.g., "name", "#say-hello")

        Returns:
            Formatted string like "By.ID, \"name\"".
        """
        strategy_map = {
            'id': 'By.ID',
            'css selector': 'By.CSS_SELECTOR',
            'xpath': 'By.XPATH',
            'name': 'By.NAME',
            'tag name': 'By.TAG_NAME',
            'class name': 'By.CLASS_NAME',
            'link text': 'By.LINK_TEXT',
            'partial link text': 'By.PARTIAL_LINK_TEXT'
        }

        strategy_str = strategy_map.get(strategy.lower(), f'By.{strategy.upper()}')
        return f'{strategy_str}, "{selector}"'

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