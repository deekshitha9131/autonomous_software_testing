import re
from typing import Optional, Dict, Any, List

from app.llm.client import LLMClient
from .schema import TestCase, TestDataItem
from app.requirement_understanding.schema import RequirementUnderstanding


class RequirementToTestCaseGenerator:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize the generator with an LLM client.

        If no LLM client is provided, defaults to OpenAIClient (which will read API key from environment).
        """
        if llm_client is None:
            from app.llm.client import OpenAIClient
            llm_client = OpenAIClient()
        self.llm_client = llm_client

    def generate(self, requirement: str) -> TestCase:
        """Generate a test case from a natural language requirement.

        This method maintains backward compatibility with existing usage.

        Args:
            requirement: The natural language requirement to convert to a test case.
        Returns:
            A TestCase instance populated with the generated data.
        """
        prompt = f"""
You are an expert software test engineer. Convert the following natural language requirement into a detailed test case.

Requirement:
{requirement}

Generate a JSON object that strictly adheres to the provided test case schema. The JSON must contain all required fields.
"""
        return self.llm_client.generate_structured(prompt, TestCase)

    def _align_scenario_test_data(
        self,
        test_case: TestCase,
        scenario: Dict[str, Any],
        supplied_test_data: Dict[str, Any],
        sut_context: Dict[str, Any],
    ) -> None:
        """Keep structured inputs aligned with the scenario the test will execute."""
        test_case.route = scenario.get("route")
        scenario_text = " ".join(
            str(scenario.get(field, ""))
            for field in ("title", "description", "scenario_type")
        )
        scenario_text_lower = scenario_text.lower()
        scenario_data = {
            item.key: item.value
            for item in (test_case.test_data or [])
        }

        route_context = (sut_context.get("routes") or {}).get(scenario.get("route"), {})
        selector_context = {**sut_context, **route_context}
        input_key = next(
            (
                key.removesuffix("_selector")
                for key in selector_context
                if key.endswith("_selector")
            ),
            next(iter(supplied_test_data), next(iter(scenario_data), "input")),
        )
        is_security_case = any(
            marker in scenario_text_lower for marker in ("xss", "script injection")
        )
        if re.search(r"\b(empty|blank)\b", scenario_text_lower):
            scenario_data[input_key] = ""
        elif is_security_case:
            match = re.search(
                r"<script\b[^>]*>.*?</script>",
                scenario_text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            payload = match.group(0) if match else scenario_data.get(input_key)
            if isinstance(payload, str) and payload:
                scenario_data[input_key] = payload
        elif any(marker in scenario_text_lower for marker in ("maximum length", "max length", "maximum allowed")):
            match = re.search(r"(\d{2,5})\s*(?:-\s*)?characters?", scenario_text_lower)
            character_count = min(int(match.group(1)), 4096) if match else 255
            scenario_data[input_key] = "A" * character_count
        elif any(marker in scenario_text_lower for marker in ("special character", "unicode", "apostrophe")):
            if not scenario_data.get(input_key):
                sample = re.search(
                    r"(?:e\.g\.,?|such as)\s*[\"“]([^\"”]+)[\"”]",
                    scenario_text,
                    flags=re.IGNORECASE,
                )
                if sample:
                    scenario_data[input_key] = sample.group(1)

        is_scenario_specific = (
            re.search(r"\b(empty|blank)\b", scenario_text_lower)
            or is_security_case
            or any(marker in scenario_text_lower for marker in ("maximum length", "max length", "maximum allowed"))
            or any(marker in scenario_text_lower for marker in ("special character", "unicode", "apostrophe"))
        )
        if not is_scenario_specific:
            scenario_data.update(supplied_test_data)

        greeting_template = selector_context.get("greeting_template")
        reference_name = supplied_test_data.get(input_key)
        expected_behavior = selector_context.get("expected_behavior", "")
        if not greeting_template and isinstance(reference_name, str) and reference_name:
            match = re.search(
                rf"(Hello,\s*){re.escape(reference_name)}([.!?])",
                expected_behavior,
                flags=re.IGNORECASE,
            )
            if match:
                greeting_template = f"{match.group(1)}{{name}}{match.group(2)}"

        input_value = scenario_data.get(input_key)
        empty_greeting = selector_context.get("empty_name_behavior")
        if isinstance(input_value, str):
            expected_greeting = None
            if not input_value.strip() and empty_greeting:
                expected_greeting = empty_greeting
            elif input_value.strip() and greeting_template:
                expected_greeting = greeting_template.format(name=input_value.strip())
            if expected_greeting is not None:
                test_case.expected_result = (
                    f"The greeting element text is exactly {expected_greeting!r}."
                )

        test_case.test_data = [
            TestDataItem(key=key, value=value)
            for key, value in scenario_data.items()
        ]

        if is_security_case:
            test_case.expected_result = (
                "The submitted script payload appears as literal visible text, its "
                "markup is escaped in the greeting element's innerHTML, and no "
                "JavaScript alert is invoked."
            )

    def generate_from_scenario(
        self,
        requirement: str,
        requirement_understanding: Dict[str, Any],
        scenario: Dict[str, Any],
        test_data: Optional[Dict[str, Any]] = None,
        sut_context: Optional[Dict[str, Any]] = None
    ) -> TestCase:
        """Generate a test case for a given scenario based on the requirement and its understanding.

        Args:
            requirement: The original natural language requirement
            requirement_understanding: The structured understanding from Phase 2
            scenario: The Phase 3 scenario to generate a test case for

        Returns:
            A TestCase instance populated with the generated data.
        """
        scenario_id = scenario.get("scenario_id", "")
        scenario_route = scenario.get("route")
        scenario_type = scenario.get("scenario_type", "")
        scenario_title = scenario.get("title", "")
        scenario_description = scenario.get("description", "")

        feature = requirement_understanding.get("feature", "")
        objective = requirement_understanding.get("objective", "")
        actors = requirement_understanding.get("actors", [])
        inputs = requirement_understanding.get("inputs", [])
        preconditions = requirement_understanding.get("preconditions", [])
        expected_behavior = requirement_understanding.get("expected_behavior", "")
        constraints = requirement_understanding.get("constraints", [])
        ambiguities = requirement_understanding.get("ambiguities", [])

        # Map scenario_type to test_type if needed (security -> non-functional)
        # Only functional, negative, boundary are direct matches
        if scenario_type in ["functional", "negative", "boundary"]:
            mapped_test_type = scenario_type
        else:
            # For security and other types, map to non-functional as default
            mapped_test_type = "non-functional"

        # Build test_data context string for the prompt
        test_data_context = ""
        if test_data:
            import json as _json
            test_data_context = f"\nSupplied Test Data (use these EXACT values where relevant — do NOT invent placeholders):\n{_json.dumps(test_data, indent=2, default=str)}\n"

        # Build SUT context string
        sut_context_str = ""
        effective_sut_context = sut_context or requirement_understanding.get("sut_context")
        if effective_sut_context:
            import json as _json
            sut_context_str = f"\nSUT Context:\n{_json.dumps(effective_sut_context, indent=2, default=str)}\n"

        prompt = f"""You are an expert software test engineer. Generate a SINGLE test case for the SPECIFIC scenario described below.

=== ORIGINAL REQUIREMENT ===
{requirement}

=== REQUIREMENT UNDERSTANDING ===
- Feature: {feature}
- Objective: {objective}
- Actors: {actors}
- Inputs: {inputs}
- Preconditions: {preconditions}
- Expected Behavior: {expected_behavior}
- Constraints: {constraints}
- Ambiguities: {ambiguities}
{sut_context_str}{test_data_context}
=== TARGET SCENARIO (you MUST generate a test case for THIS scenario ONLY) ===
- Scenario ID: {scenario_id}
- Route: {scenario_route}
- Scenario Type: {scenario_type}
- Scenario Title: {scenario_title}
- Scenario Description: {scenario_description}

CRITICAL ALIGNMENT RULES:
- The generated test case MUST be semantically aligned with the TARGET SCENARIO above.
- Do NOT replace the scenario with a generic or unrelated example.
- Do NOT invent unrelated domains (e.g., quantity/order forms, numeric inputs, load/performance tests) unless the scenario explicitly describes them.
- A "{scenario_type}" scenario about "{scenario_title}" MUST produce a "{scenario_type}"-relevant test case about "{scenario_title}".
- If test_data is supplied above, use those EXACT values (e.g., if name='Alice', use 'Alice' — do NOT substitute with generic placeholders like 'ValidSampleData').

Required JSON format:
{{
  "test_id": "string (unique test identifier)",
  "scenario_id": "string (must exactly equal: \\"{scenario_id}\\")",
    "route": "string or null (must exactly match the target scenario route)",
  "title": "string (test title directly describing this scenario)",
  "description": "string (detailed description aligned with this scenario)",
  "preconditions": ["string", ...] (JSON array of strings, use [] if empty),
  "steps": ["string", ...] (JSON array of strings, ordered test steps for THIS scenario),
  "test_data": [{{"key": "string", "value": any}}, ...] (JSON array of objects with "key" and "value" fields, use [] if no test data),
  "expected_result": "string (expected outcome for THIS scenario)",
  "test_type": "string (must be exactly \\"{mapped_test_type}\\")",
  "priority": "string (must be exactly one of: \\"low\\", \\"medium\\", \\"high\\", \\"critical\\")"
}}

Field rules:
- test_id: Generate as "tc_" + scenario_id + "_001"
- scenario_id: MUST be exactly "{scenario_id}" (preserve case, no changes)
- route: MUST be exactly {scenario_route!r}; use null only when the scenario has no route
- title: Must directly describe what THIS scenario tests (e.g., for a security XSS scenario, title must mention XSS/injection)
- description: Must describe THIS scenario's test coverage, not a generic test
- steps: Ordered steps specific to THIS scenario — describe WHAT not HOW
- test_data: Use supplied test data values where relevant; use [] if no test data needed
- expected_result: Expected outcome specific to THIS scenario
- test_type: Must be exactly "{mapped_test_type}"
- priority: Set based on risk and importance

Constraints:
- Do NOT invent SUT selectors, URLs, usernames, passwords, or credentials
- Do NOT hardcode login-specific behavior unless scenario requires login
- Steps describe WHAT the test should do (not HOW to implement in code)
- Return ONLY the JSON object — no explanations, no markdown, no extra text
- All fields are required — do not omit any
- Do NOT add fields not listed above

DO NOT include any text before or after the JSON object.
DO NOT use ```json``` markdown fences.
Return the raw JSON object only."""

        # In a real implementation, we might want to adjust the prompt based on retries, but for now we keep it simple.
        test_case = self.llm_client.generate_structured(prompt, TestCase)
        self._align_scenario_test_data(
            test_case,
            scenario,
            test_data or {},
            effective_sut_context or {},
        )
        return test_case