"""Unit tests for the KnowledgeRetriever."""

import os
import tempfile
import shutil
from pathlib import Path

from app.rag.retriever import KnowledgeRetriever


def test_retriever_loads_documents():
    """Test that the retriever loads .txt and .md files from the knowledge base."""
    # Use the actual knowledge_base directory
    kb_path = Path(__file__).parent.parent / "knowledge_base"
    retriever = KnowledgeRetriever(str(kb_path))
    # We expect at least the three files we created
    assert len(retriever.documents) == 3
    # Check that each document has an id and content
    for doc in retriever.documents:
        assert "id" in doc
        assert "content" in doc
        assert isinstance(doc["content"], str)
        assert len(doc["content"]) > 0


def test_retriever_returns_relevant_documents():
    """Test that the retriever returns documents matching the query keywords."""
    kb_path = Path(__file__).parent.parent / "knowledge_base"
    retriever = KnowledgeRetriever(str(kb_path))

    # Query about testing guidelines
    results = retriever.retrieve("testing guidelines tdd", top_k=2)
    # Should return at least one document
    assert len(results) > 0
    # The most relevant should be testing_guidelines.md
    assert results[0]["id"] == "testing_guidelines.md"
    # Check that the content contains some of the query words
    assert "tdd" in results[0]["content"].lower() or "test" in results[0]["content"].lower()

    # Query about API testing
    results = retriever.retrieve("api testing status codes", top_k=2)
    assert len(results) > 0
    assert results[0]["id"] == "api_testing.md"
    assert "status" in results[0]["content"].lower() or "codes" in results[0]["content"].lower()

    # Query about bug patterns
    results = retriever.retrieve("bug patterns null pointer", top_k=2)
    assert len(results) > 0
    assert results[0]["id"] == "bug_patterns.md"
    assert "null" in results[0]["content"].lower() or "pointer" in results[0]["content"].lower()


def test_retriever_returns_empty_for_no_match():
    """Test that the retriever returns an empty list when no keywords match."""
    kb_path = Path(__file__).parent.parent / "knowledge_base"
    retriever = KnowledgeRetriever(str(kb_path))

    # Query with words that are unlikely to be in the documents
    results = retriever.retrieve("xyzqwerty asdfghjkl", top_k=3)
    assert len(results) == 0


def test_retriever_respects_top_k():
    """Test that the retriever returns at most top_k results."""
    kb_path = Path(__file__).parent.parent / "knowledge_base"
    retriever = KnowledgeRetriever(str(kb_path))

    # Query that matches all documents (e.g., "test")
    results = retriever.retrieve("test", top_k=2)
    # Should return at most 2 documents
    assert len(results) <= 2
    # But we expect at least one because all documents contain the word "test"?
    # Actually, all three documents have the word "test" in them? Let's see:
    # testing_guidelines.md: has "test" in "Testing Guidelines" and throughout.
    # api_testing.md: has "test" in "API Testing".
    # bug_patterns.md: does not have the word "test" (it has "bug", "patterns").
    # So we expect at least two.
    # We'll just assert that the length is <= top_k.
    assert len(results) <= 2


def test_investigate_failure_knowledge_retrieval():
    """Test that investigate_failure node retrieves knowledge and passes it to the investigation agent."""
    from app.workflow.graph import investigate_failure
    from app.workflow.state import WorkflowState
    from unittest.mock import patch, MagicMock

    # Mock the KnowledgeRetriever to return a fixed result
    with patch('app.workflow.graph.KnowledgeRetriever') as mock_retriever_class, \
         patch('app.workflow.graph._get_llm_client') as mock_llm_client, \
         patch('app.workflow.graph.FailureInvestigationAgent') as mock_agent_class:

        # Setup mock retriever instance
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = [{"id": "test.txt", "content": "TDD is a software development process."}]
        mock_retriever_class.return_value = mock_retriever_instance

        # Setup mock LLM client
        mock_llm = MagicMock()
        mock_llm_client.return_value = mock_llm

        # Setup mock FailureInvestigationAgent
        mock_agent_instance = MagicMock()
        mock_agent_instance.investigate.return_value = MagicMock(model_dump=lambda: {"analysis": "dummy failure analysis"})
        mock_agent_class.return_value = mock_agent_instance

        # Create a state with a failed execution result
        state = WorkflowState(
            requirement="Test requirement for TDD",
            test_case={"title": "Test TDD", "description": "Test driven development"},
            generated_test_code="def test_tdd(): assert True",
            execution_result={
                "status": "fail",
                "exception": {"type": "AssertionError", "message": "assert False"},
                "stdout": "",
                "stderr": "",
                "screenshot": None,
                "duration": 0
            }
        )

        # Call the investigate_failure function
        result = investigate_failure(state)

        # Verify that the retriever was called (we don't need to check the query string for this minimal test)
        mock_retriever_instance.retrieve.assert_called_once()
        # Check that retrieved_knowledge is in the result and is a list
        assert "retrieved_knowledge" in result
        assert isinstance(result["retrieved_knowledge"], list)
        assert len(result["retrieved_knowledge"]) > 0
        # Verify that the investigation agent was called with the retrieved knowledge
        mock_agent_instance.investigate.assert_called_once()
        call_args, call_kwargs = mock_agent_instance.investigate.call_args
        assert "retrieved_knowledge" in call_kwargs
        assert call_kwargs["retrieved_knowledge"] is not None
        assert isinstance(call_kwargs["retrieved_knowledge"], list)
        assert len(call_kwargs["retrieved_knowledge"]) > 0
        # Also check that failure_analysis is present (the original functionality)
        assert "failure_analysis" in result