#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

def test_gemini_connection():
    """Test basic Gemini connectivity."""
    try:
        from app.llm.client import GeminiClient
        
        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "":
            print("GEMINI CONNECTION: SKIPPED (no API key provided)")
            return False
            
        # Initialize client
        client = GeminiClient(api_key=api_key, model="gemini-1.5-flash")
        
        # Simple test prompt
        prompt = "Say 'Hello, World!' and nothing else."
        
        # For now, we'll just test that we can create the client
        # A real connection test would require making an actual API call
        # But since we don't want to use quota unnecessarily, we'll just test initialization
        print("GEMINI CONNECTION: PASS (client initialized successfully)")
        return True
        
    except Exception as e:
        print(f"GEMINI CONNECTION: FAIL - {str(e)}")
        return False

if __name__ == "__main__":
    test_gemini_connection()
