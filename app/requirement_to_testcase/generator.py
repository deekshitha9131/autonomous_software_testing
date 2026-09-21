from typing import Optional

from app.llm.client import LLMClient
from .schema import TestCase


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

        Args:
            requirement: The natural language requirement to convert to a test case.
        Returns:
            A TestCase instance populated with the generated data.
        """
        prompt = f"""
You are an expert software test engineer. Convert the following natural language requirement into a detailed test case.

Requirement:
{requirement}

Generate a JSON object that strictly adheres to the provided schema. The JSON must contain all required fields.
Make sure the test case is clear, concise, and directly tests the requirement.
"""
        # In a real implementation, we might want to adjust the prompt based on retries, but for now we keep it simple.
        return self.llm_client.generate_structured(prompt, TestCase)
