"""Simple knowledge base retriever for the autonomous testing project."""

import os
from typing import List, Dict


class KnowledgeRetriever:
    """A simple keyword-based retriever for text documents."""

    def __init__(self, knowledge_base_dir: str):
        """Initialize the retriever with a knowledge base directory.

        Args:
            knowledge_base_dir: Path to the directory containing .txt and .md files.
        """
        self.knowledge_base_dir = knowledge_base_dir
        self.documents: List[Dict[str, str]] = []
        self._load_knowledge_base()

    def _load_knowledge_base(self) -> None:
        """Load all .txt and .md files from the knowledge base directory."""
        self.documents = []
        for filename in os.listdir(self.knowledge_base_dir):
            if filename.endswith(".txt") or filename.endswith(".md"):
                file_path = os.path.join(self.knowledge_base_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.documents.append(
                        {
                            "id": filename,
                            "content": content,
                        }
                    )
                except Exception as e:
                    # In a real system, we might log this error.
                    print(f"Warning: Could not load {file_path}: {e}")

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        """Retrieve the most relevant documents based on keyword matching.

        Args:
            query: The search query.
            top_k: Number of top results to return.

        Returns:
            A list of documents, each containing 'id' and 'content',
            sorted by relevance (descending).
        """
        if not self.documents:
            return []

        # Simple tokenization: split by whitespace and lowercase.
        query_words = set(query.lower().split())
        # Score each document by the number of query words present.
        scored_docs = []
        for doc in self.documents:
            content_words = set(doc["content"].lower().split())
            # Compute intersection size.
            common = query_words.intersection(content_words)
            score = len(common)
            scored_docs.append((score, doc))

        # Sort by score descending.
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        # Return top_k documents (with score > 0? We'll return all if top_k is large, but we can filter zero scores later).
        # For simplicity, return top_k even if score is zero.
        top_docs = [doc for score, doc in scored_docs[:top_k] if score > 0]
        # If no documents have a positive score, return empty list? Or return the top_k anyway?
        # We'll return only those with positive score.
        return top_docs