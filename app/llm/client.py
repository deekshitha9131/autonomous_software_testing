import abc
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(abc.ABC):
    @abc.abstractmethod
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """Generate a structured response from the LLM conforming to the given schema.

        Args:
            prompt: The prompt to send to the LLM.
            schema: A Pydantic model class defining the expected structure.
        Returns:
            An instance of the schema populated with the LLM's response.
        Raises:
            Exception: If the LLM fails to generate a valid response after retries.
        """
        pass


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        """Initialize the OpenAI client.

        Args:
            api_key: The OpenAI API key. If not provided, reads from OPENAI_API_KEY environment variable.
            model: The model to use for generation.
        """
        import os
        from langchain_openai import ChatOpenAI

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY environment variable.")
        self.model = ChatOpenAI(model=model, openai_api_key=self.api_key)

    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """Generate a structured response from OpenAI with retries on validation failure."""
        from pydantic import ValidationError

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use LangChain's structured output
                runnable = self.model.with_structured_output(schema)
                return runnable.invoke(prompt)
            except ValidationError as e:
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to generate valid response after {max_retries} attempts: {e}")
                # Optionally, we could adjust the prompt and retry
                # For simplicity, we just retry the same prompt
                continue
            except Exception as e:
                # Other errors (e.g., network, rate limit) we might want to retry or raise immediately
                # For now, we raise immediately to avoid infinite loops on non-retryable errors
                raise e
        # This point should not be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in generate_structured")