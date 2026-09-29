import os
os.environ["OPENAI_API_KEY"] = ""

from app.test_automation_agent.service import TestAutomationAgent
from app.llm.client import LLMClient

# Dummy LLM client (not used in status method)
class DummyLLMClient(LLMClient):
    def generate_structured(self, prompt, schema):
        return schema()

def test_case_a():
    print("=== Case A: base_url + usable sut_context supplied ===")
    agent = TestAutomationAgent(
        llm_client=DummyLLMClient(),
        base_url="http://example.com",
        sut_id="sut123",
        sut_context={"page": "login"},
        test_data={"user": "test"}
    )
    status = agent.get_sut_context_status()
    print("Status:", status)
    assert status["has_base_url"] == True
    assert status["has_sut_id"] == True
    assert status["has_sut_context"] == True
    assert status["has_test_data"] == True
    assert status["ready"] == True
    assert status["missing"] == []
    print("PASS\n")

def test_case_b():
    print("=== Case B: base_url + sut_context + test_data supplied ===")
    agent = TestAutomationAgent(
        llm_client=DummyLLMClient(),
        base_url="http://example.com",
        sut_id="sut123",
        sut_context={"page": "login"},
        test_data={"user": "test"}
    )
    status = agent.get_sut_context_status()
    print("Status:", status)
    assert status["has_base_url"] == True
    assert status["has_sut_id"] == True
    assert status["has_sut_context"] == True
    assert status["has_test_data"] == True
    assert status["ready"] == True
    assert status["missing"] == []
    print("PASS\n")

def test_case_c_missing_sut_context():
    print("=== Case C: missing sut_context (essential) ===")
    agent = TestAutomationAgent(
        llm_client=DummyLLMClient(),
        base_url="http://example.com",
        sut_id="sut123",
        sut_context={},  # empty dict -> not usable
        test_data={"user": "test"}
    )
    status = agent.get_sut_context_status()
    print("Status:", status)
    assert status["has_base_url"] == True
    assert status["has_sut_id"] == True
    assert status["has_sut_context"] == False  # empty dict
    assert status["has_test_data"] == True
    assert status["ready"] == False  # because sut_context empty
    assert "sut_context" in status["missing"]
    print("PASS\n")

def test_case_c_missing_base_url():
    print("=== Case C: missing base_url ===")
    agent = TestAutomationAgent(
        llm_client=DummyLLMClient(),
        base_url="",  # empty string
        sut_id="sut123",
        sut_context={"page": "login"},
        test_data={"user": "test"}
    )
    status = agent.get_sut_context_status()
    print("Status:", status)
    assert status["has_base_url"] == False
    assert status["has_sut_id"] == True
    assert status["has_sut_context"] == True
    assert status["has_test_data"] == True
    assert status["ready"] == False
    assert "base_url" in status["missing"]
    print("PASS\n")

def test_case_c_missing_all():
    print("=== Case C: missing all except llm_client ===")
    agent = TestAutomationAgent(
        llm_client=DummyLLMClient()
    )
    status = agent.get_sut_context_status()
    print("Status:", status)
    assert status["has_base_url"] == False
    assert status["has_sut_id"] == False
    assert status["has_sut_context"] == False
    assert status["has_test_data"] == False
    assert status["ready"] == False
    assert set(status["missing"]) == {"base_url", "sut_id", "sut_context", "test_data"}
    print("PASS\n")

if __name__ == "__main__":
    test_case_a()
    test_case_b()
    test_case_c_missing_sut_context()
    test_case_c_missing_base_url()
    test_case_c_missing_all()
    print("All tests passed!")