import abc
from typing import Type, TypeVar
import time
import json

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
                # Other errors (e.g., network, rate limit) we raise immediately to avoid infinite loops
                raise e
        # This point should not be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in generate_structured")


class GroqClient(LLMClient):
    def __init__(self, api_key: str = None, model: str = None):
        """Initialize the Groq client.

        Args:
            api_key: The Groq API key. If not provided, reads from GROQ_API_KEY environment variable.
            model: The model to use for generation. If not provided, reads from GROQ_MODEL environment variable.
                   GROQ_MODEL must be set; no default is provided.
        """
        import os
        from langchain_groq import ChatGroq

        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key must be provided or set in GROQ_API_KEY environment variable.")
        if model is None:
            model = os.getenv("GROQ_MODEL")
        if model is None:
            raise ValueError("GROQ_MODEL must be set in environment variable or provided as argument.")
        self.model = ChatGroq(model=model, groq_api_key=self.api_key)

    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """Generate a structured response from Groq with retries on validation and transient errors."""
        from pydantic import ValidationError
        import re

        max_attempts = 4
        base_delay = 2.0  # Backoff: 2s, 4s, 8s

        for attempt in range(max_attempts):
            try:
                # Use LangChain's structured output with JSON schema mode for Groq
                runnable = self.model.with_structured_output(schema, method="json_schema")
                return runnable.invoke(prompt)
            except ValidationError as e:
                # Validation errors are not transient — fail immediately
                raise ValueError(f"Failed to generate valid response: {e}")
            except Exception as e:
                if _is_transient_error(e) and attempt < max_attempts - 1:
                    # Try to extract retry-after timing from Groq 429 messages
                    delay = base_delay * (2 ** attempt)
                    exc_str = str(e)
                    retry_match = re.search(r'try again in\s+(\d+(?:\.\d+)?)\s*ms', exc_str, re.IGNORECASE)
                    if retry_match:
                        retry_ms = float(retry_match.group(1))
                        delay = max(delay, retry_ms / 1000.0)
                    time.sleep(delay)
                    continue
                else:
                    # Permanent error or final attempt exhausted
                    raise e

        raise RuntimeError("Unexpected error in generate_structured")


def _is_transient_error(exc: Exception) -> bool:
    """Check if an exception represents a transient error that should be retried.

    Returns True for errors like 429, 500, 502, 503, 504 that may succeed on retry.
    Returns False for permanent errors like validation errors, auth errors, etc.
    """
    # Convert exception to string for checking
    exc_str = str(exc).lower()

    # Check for common transient error indicators
    transient_indicators = [
        '429',  # Rate limit
        '500',  # Internal server error
        '502',  # Bad gateway
        '503',  # Service unavailable
        '504',  # Gateway timeout
        'timeout',
        'deadline exceeded',
        'resource exhausted',
        'unavailable',
        'throttl',
        'quota',
        'try again',
        'temporarily',
        'spike',  # Often appears in Gemini 503 messages
        'high demand',  # From the observed error
    ]

    return any(indicator in exc_str for indicator in transient_indicators)


class GeminiClient(LLMClient):
    def __init__(self, api_key: str = None, model: str = None):
        """Initialize the Gemini client.

        Args:
            api_key: The Gemini API key. If not provided, reads from GEMINI_API_KEY environment variable.
            model: The model to use for generation. If not provided, reads from GEMINI_MODEL environment variable.
                   GEMINI_MODEL must be set; no default is provided.
        """
        import os
        from google import genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key must be provided or set in GEMINI_API_KEY environment variable.")
        if model is None:
            model = os.getenv("GEMINI_MODEL")
        if model is None:
            raise ValueError("GEMINI_MODEL must be set in environment variable or provided as argument.")

        # Initialize the Gemini client
        self.client = genai.Client(api_key=self.api_key)
        self.model = model

    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """Generate a structured response from Gemini with retries on validation failure and transient errors.

        If Gemini exhausts all retry attempts due to transient errors (429/500/502/503/504),
        falls back to GroqClient if GROQ_API_KEY and GROQ_MODEL are configured.
        Permanent errors (auth, schema, malformed request) are never failed over.
        """
        from pydantic import ValidationError
        import json
        import os

        max_attempts = 4
        base_delay = 2.0  # Start with 2 second delay for transient errors (2s, 4s, 8s backoff)
        last_transient_error = None

        for attempt in range(max_attempts):
            try:
                # Use Gemini's structured output capabilities
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )

                # Parse the JSON response and validate with Pydantic schema
                json_data = json.loads(response.text)
                return schema(**json_data)

            except ValidationError as e:
                # Validation errors are not transient - they indicate schema issues
                # Don't retry validation errors, fail immediately
                if attempt == max_attempts - 1:
                    raise ValueError(f"Failed to generate valid response after {max_attempts} attempts: {e}")
                # For validation errors, we could adjust prompt, but for simplicity fail fast
                raise ValueError(f"Failed to generate valid response: {e}")
            except Exception as e:
                # Check if this is a transient error that should be retried
                if _is_transient_error(e) and attempt < max_attempts - 1:
                    # Wait with exponential backoff: 2s, 4s, 8s
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    last_transient_error = e
                    continue
                elif _is_transient_error(e):
                    # Final attempt exhausted on transient error — try Groq failover
                    last_transient_error = e
                    break
                else:
                    # Permanent error — do not failover, raise immediately
                    raise e

        # Gemini transient retries exhausted — attempt Groq failover
        if last_transient_error is not None:
            groq_key = os.getenv("GROQ_API_KEY")
            groq_model = os.getenv("GROQ_MODEL")
            print(f"[LLM Failover] Gemini exhausted {max_attempts} attempts. "
                  f"Transient={_is_transient_error(last_transient_error)}, "
                  f"GROQ_API_KEY present={bool(groq_key)}, GROQ_MODEL={groq_model}")
            if groq_key and groq_model:
                try:
                    fallback_client = GroqClient(api_key=groq_key, model=groq_model)
                    print(f"[LLM Failover] GroqClient created. Calling generate_structured...")
                    result = fallback_client.generate_structured(prompt, schema)
                    print(f"[LLM Failover] Groq generate_structured succeeded.")
                    return result
                except Exception as groq_exc:
                    # Preserve BOTH errors so the real Groq failure is visible
                    print(f"[LLM Failover] Groq generate_structured FAILED: {type(groq_exc).__name__}: {groq_exc}")
                    raise RuntimeError(
                        f"Primary Gemini failed: {last_transient_error}; "
                        f"Groq fallback failed: {groq_exc}"
                    )
            else:
                print(f"[LLM Failover] No Groq credentials — raising original Gemini error")
                # No Groq credentials — raise original Gemini error
                raise last_transient_error

        # This point should not be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in generate_structured")