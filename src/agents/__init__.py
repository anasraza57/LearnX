"""
AI agents for personalized learning.

This module contains LangChain-based agents (AI/LLM-powered decision makers):
- Syllabus planning (curriculum design, learner advocacy)
- RAG Instruction (RAG-based teaching with citations)
- Assessment generation (AI-powered question creation)
- Grading (LLM-based evaluation of open-ended responses)

Note: AdaptiveQuiz is in src/models (pure logic, not an agent)
"""

from .rag_instructor import (
    RAGInstructor,
    Citation,
    TeachingResponse,
    create_instructor_from_documents,
)
from .assessment_generator import (
    AssessmentGenerator,
    AssessmentQuestion,
)
from .grading_agent import (
    GradingAgent,
    GradingResult,
)

__all__ = [
    # RAG Instruction
    "RAGInstructor",
    "Citation",
    "TeachingResponse",
    "create_instructor_from_documents",
    # Assessment Agents
    "AssessmentGenerator",
    "AssessmentQuestion",
    "GradingAgent",
    "GradingResult",
]
