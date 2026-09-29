#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv
load_dotenv()

from app.llm.client import GroqClient

def test_plain():
    print("Testing plain generation...")
    client = GroqClient()  # will read env
    # Simple prompt
    prompt = "Say hello in one word."
    # We need to call generate? The LLMClient abstract method is generate_structured only? Actually LLMClient has generate_structured abstract, but GroqClient does not implement generate (non-structured). However, we can use the underlying model directly for plain generation.
    # For plain generation test, we can use client.model.invoke(prompt)
    try:
        resp = client.model.invoke(prompt)
        print(f"Plain response: {resp.content}")
        return True
    except Exception as e:
        print(f"Plain generation failed: {e}")
        return False

def test_structured():
    print("\nTesting structured generation...")
    from pydantic import BaseModel, Field
    class Joke(BaseModel):
        setup: str = Field(description="The setup of the joke")
        punchline: str = Field(description="The punchline to the joke")
        rating: int | None = Field(description="How funny the joke is, from 1 to 10")
    client = GroqClient()
    prompt = "Tell me a joke about cats."
    try:
        # Use generate_structured method
        result: Joke = client.generate_structured(prompt, Joke)
        print(f"Structured result: {result}")
        # Validate fields
        assert isinstance(result.setup, str) and len(result.setup) > 0
        assert isinstance(result.punchline, str) and len(result.punchline) > 0
        assert result.rating is None or (isinstance(result.rating, int) and 1 <= result.rating <= 10)
        print("Validation passed.")
        return True
    except Exception as e:
        print(f"Structured generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    ok1 = test_plain()
    ok2 = test_structured()
    if ok1 and ok2:
        print("\nAll tests PASSED")
        sys.exit(0)
    else:
        print("\nSome tests FAILED")
        sys.exit(1)