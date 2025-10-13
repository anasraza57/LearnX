"""
AI agents for personalized learning.

This module contains LangChain-based agents for:
- Syllabus planning (curriculum design, learner advocacy)
- RAG Instruction (RAG-based teaching with citations)
- Assessment (adaptive testing and evaluation)
"""

from .rag_instructor import (
    RAGInstructor,
    Citation,
    TeachingResponse,
    create_instructor_from_documents,
)

__all__ = [
    "RAGInstructor",
    "Citation",
    "TeachingResponse",
    "create_instructor_from_documents",
]
