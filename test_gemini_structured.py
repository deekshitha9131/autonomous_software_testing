#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

def test_gemini_structured_output():
    """Test Gemini structured output capability."""
    try:
        from app.llm.client import GeminiClient
        from pydantic import BaseModel, Field
        from typing import Literal
        
        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "":
            print("GEMINI STRUCTURED OUTPUT: SKIPPED (no API key provided)")
            return False
            
        # Initialize client
        client = GeminiClient(api_key=api_key, model="gemini-1.5-flash")
        
        # Define a simple test schema
        class SimpleTestSchema(BaseModel):
            name: str = Field(..., description="A name")
            age: int = Field(..., description="An age")
            status: Literal["active", "inactive"] = Field(..., description="Status")
        
        # Test prompt
        prompt = """
        Generate a test object with the following information:
        name: "John Doe"
        age: 30
        status: "active"
        """
        
        # Generate structured output
        result = client.generate_structured(prompt, SimpleTestSchema)
        
        # Validate the result
        assert result.name == "John Doe"
        assert result.age == 30
        assert result.status == "active"
        
        print("GEMINI STRUCTURED OUTPUT: PASS")
        return True
        
    except Exception as e:
        print(f"GEMINI STRUCTURED OUTPUT: FAIL - {str(e)}")
        return False

if __name__ == "__main__":
    test_gemini_structured_output()
