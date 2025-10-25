"""
RAG-based Instructor Agent with Citations.

This agent teaches using retrieval-augmented generation:
- Retrieves relevant context from document store
- Generates responses with citations
- Adapts explanation complexity to learner level
- Tracks sources used
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

try:
    from ..config import config
    from ..utils.vector_store import VectorStore
    from ..utils.document_loader import Document
    from ..utils.persistence import save_teaching_session
except ImportError:
    from src.config import config
    from src.utils.vector_store import VectorStore
    from src.utils.document_loader import Document
    from src.utils.persistence import save_teaching_session


@dataclass
class Citation:
    """
    Citation for a piece of information.

    Attributes:
        source: Source document name
        page: Page number (if applicable)
        content: Exact content cited
        relevance_score: How relevant this source is (0-1)
    """
    source: str
    content: str
    relevance_score: float
    page: Optional[int] = None
    filepath: Optional[str] = None

    def __repr__(self) -> str:
        page_info = f", p.{self.page}" if self.page else ""
        return f"[{self.source}{page_info}]"

    def to_markdown(self) -> str:
        """Format citation as markdown."""
        page_info = f", page {self.page}" if self.page else ""
        return f"**Source:** {self.source}{page_info}\n> {self.content[:200]}..."


@dataclass
class TeachingResponse:
    """
    Response from the RAG instructor.

    Attributes:
        answer: The teaching explanation
        citations: List of citations used
        retrieved_docs: Original documents retrieved
        confidence: Confidence in the answer (0-1)
    """
    answer: str
    citations: List[Citation] = field(default_factory=list)
    retrieved_docs: List[Tuple[Document, float]] = field(default_factory=list)
    confidence: float = 1.0

    def format_with_citations(self) -> str:
        """Format answer with inline citations."""
        result = self.answer + "\n\n"

        if self.citations:
            result += "## Sources\n\n"
            for i, citation in enumerate(self.citations, 1):
                result += f"{i}. {citation.to_markdown()}\n\n"

        return result


class RAGInstructor:
    """
    RAG-based teaching agent that provides accurate answers with citations.

    Features:
    - Semantic search over document corpus
    - Citation generation
    - Adaptive explanation complexity
    - Confidence scoring
    """

    def __init__(
        self,
        vector_store: VectorStore,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        top_k_retrieval: int = None,
        min_similarity: float = 0.35,
        learning_style: Optional[List[str]] = None,
        interests: Optional[List[str]] = None,
    ):
        """
        Initialize RAG instructor.

        Args:
            vector_store: Initialized vector store with documents
            model_name: LLM model name (default from config)
            temperature: LLM temperature (0=deterministic, 1=creative)
            top_k_retrieval: Number of documents to retrieve (default from config)
            min_similarity: Minimum similarity threshold for citations (0-1)
            learning_style: Learner's preferred learning styles (visual, auditory, kinesthetic, reading_writing)
            interests: Learner's interests for generating relevant examples
        """
        self.vector_store = vector_store
        self.top_k = top_k_retrieval or config.rag.top_k
        self.min_similarity = min_similarity
        self.model_name = model_name or config.model.model_name
        self.learning_style = learning_style or ["visual"]
        self.interests = interests or []

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
            api_key=config.model.api_key,
        )

        # Build learning style guidance
        style_guidance = self._get_learning_style_guidance()

        # Build interests context
        interests_text = f"Learner is interested in: {', '.join(self.interests)}" if self.interests else "No specific interests provided"

        # Teaching prompt template with learning style, prior knowledge, and interests
        self.prompt_template = PromptTemplate(
            input_variables=["question", "context", "learner_level", "prior_knowledge"],
            template=f"""You are an expert educational instructor. Your task is to explain concepts clearly and accurately using the provided context.

**Learner Level:** {{learner_level}}
**Learning Style Preferences:** {', '.join(self.learning_style)}
**Learner's Prior Knowledge:** {{prior_knowledge}}
**Learner's Interests:** {interests_text}

**Question:** {{question}}

**Context from educational materials:**
{{context}}

**Instructions:**
1. Answer the question using ONLY information from the provided context
2. Adapt your explanation complexity to the learner's level (novice/beginner/intermediate/advanced/expert)
3. Build on the learner's prior knowledge when relevant - connect new concepts to what they already know
4. When appropriate, use examples or analogies from the learner's interests to make concepts more relatable
5. Format your response according to the learner's learning style preferences:
{style_guidance}
6. Be clear, accurate, and pedagogical
7. If the context doesn't contain enough information, say so honestly
8. Break down complex concepts into understandable parts

**Answer:**"""
        )

    def _get_learning_style_guidance(self) -> str:
        """Generate formatting guidance based on learning style preferences."""
        guidance_parts = []

        if "visual" in self.learning_style:
            guidance_parts.append("   - VISUAL learners: Use analogies, describe visual patterns, suggest diagrams/charts, use formatting (lists, tables, bullet points)")

        if "auditory" in self.learning_style:
            guidance_parts.append("   - AUDITORY learners: Use conversational tone, explain step-by-step verbally, include discussion points")

        if "kinesthetic" in self.learning_style:
            guidance_parts.append("   - KINESTHETIC learners: Include hands-on examples, practical exercises, real-world applications, actionable steps")

        if "reading_writing" in self.learning_style:
            guidance_parts.append("   - READING/WRITING learners: Provide detailed text explanations, written summaries, definitions, note-taking suggestions")

        return "\n".join(guidance_parts) if guidance_parts else "   - Use clear, balanced explanations"

    def teach(
        self,
        question: str,
        learner_level: str = "intermediate",
        metadata_filter: Optional[Dict[str, Any]] = None,
        prior_knowledge: Optional[Dict[str, str]] = None,
    ) -> TeachingResponse:
        """
        Answer a question using RAG with citations.

        Args:
            question: Student's question
            learner_level: Learner's mastery level (novice/beginner/intermediate/advanced/expert)
            metadata_filter: Filter documents by metadata (e.g., {"topic": "machine learning"})
            prior_knowledge: Learner's prior knowledge topics and levels

        Returns:
            TeachingResponse with answer and citations
        """
        # Step 1: Retrieve relevant documents with min_similarity filter
        retrieved_docs = self.vector_store.search(
            query=question,
            top_k=self.top_k,
            metadata_filter=metadata_filter,
            min_similarity=self.min_similarity,
        )

        if not retrieved_docs:
            return TeachingResponse(
                answer="I don't have enough information in my knowledge base to answer this question accurately. Please provide relevant teaching materials.",
                confidence=0.0
            )

        # Step 2: Prepare context from retrieved documents
        context_parts = []
        for i, (doc, score) in enumerate(retrieved_docs, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            page_info = f" (Page {page})" if page else ""

            context_parts.append(
                f"[Source {i}: {source}{page_info}]\n{doc.content}\n"
            )

        context = "\n---\n".join(context_parts)

        # Format prior knowledge for prompt
        if prior_knowledge:
            pk_text = ", ".join([f"{topic} ({level})" for topic, level in prior_knowledge.items()])
        else:
            pk_text = "None specified"

        # Step 3: Generate answer using LLM
        prompt = self.prompt_template.format(
            question=question,
            context=context,
            learner_level=learner_level,
            prior_knowledge=pk_text
        )

        answer = self.llm.invoke(prompt).content

        # Step 4: Create citations (only from high-quality docs)
        # Limit to top N citations with best scores
        max_citations = min(5, len(retrieved_docs))
        citations = []
        for doc, score in retrieved_docs[:max_citations]:
            citation = Citation(
                source=doc.metadata.get("source", "Unknown"),
                page=doc.metadata.get("page"),
                filepath=doc.metadata.get("filepath"),
                content=doc.content,
                relevance_score=score,
            )
            citations.append(citation)

        # Step 5: Estimate confidence based on retrieval scores
        if retrieved_docs:
            avg_score = sum(score for _, score in retrieved_docs) / len(retrieved_docs)
            confidence = min(1.0, avg_score * 1.2)  # Boost slightly, cap at 1.0
        else:
            confidence = 0.0

        return TeachingResponse(
            answer=answer,
            citations=citations,
            retrieved_docs=retrieved_docs,
            confidence=confidence,
        )

    def teach_and_save(
        self,
        question: str,
        learner_level: str = "intermediate",
        metadata_filter: Optional[Dict[str, Any]] = None,
        learner_id: Optional[str] = None,
        syllabus_id: Optional[str] = None,
        module_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        lesson_id: Optional[str] = None,
    ) -> tuple[TeachingResponse, Optional[str]]:
        """
        Teach and persist the session to disk.

        Args:
            question: Student's question
            learner_level: Learner's mastery level
            metadata_filter: Filter documents by metadata
            learner_id: Optional learner ID for tracking
            syllabus_id: Optional syllabus reference (Phase 1 mapping)
            module_id: Optional module reference (Phase 1 mapping)
            topic_id: Optional topic reference
            lesson_id: Optional lesson reference

        Returns:
            Tuple of (TeachingResponse, session_id or None if save failed)
        """
        # Step 1: Generate teaching response
        response = self.teach(
            question=question,
            learner_level=learner_level,
            metadata_filter=metadata_filter,
        )

        # Step 2: Build session dict for persistence
        session_id = f"ts-{uuid.uuid4()}"
        session_data = {
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "learner_id": learner_id,
            "syllabus_id": syllabus_id,
            "module_id": module_id,
            "topic_id": topic_id,
            "lesson_id": lesson_id,
            "question": question,
            "answer": response.answer,
            "learner_level": learner_level,
            "citations": [
                {
                    "source": c.source,
                    "page": c.page,
                    "filepath": c.filepath,
                    "content": c.content,
                    "relevance_score": c.relevance_score,
                }
                for c in response.citations
            ],
            "confidence": response.confidence,
            "model": self.model_name,
            "rag_config": {
                "top_k": self.top_k,
                "min_similarity": self.min_similarity,
            },
        }

        # Step 3: Save session
        success, saved_session_id, errors = save_teaching_session(
            session_data, validate=True, auto_repair=False
        )

        if not success:
            print(f"Warning: Failed to save teaching session: {errors}")
            return response, None

        return response, saved_session_id

    def teach_topic(
        self,
        topic: str,
        learner_level: str = "intermediate",
        max_length: int = 500,
    ) -> TeachingResponse:
        """
        Teach a specific topic (proactive teaching, not Q&A).

        Args:
            topic: Topic to teach
            learner_level: Learner's mastery level
            max_length: Maximum length of explanation

        Returns:
            TeachingResponse with teaching content
        """
        question = f"Explain {topic} in detail with examples."
        return self.teach(question, learner_level=learner_level)

    def verify_answer(
        self,
        question: str,
        student_answer: str,
        learner_level: str = "intermediate",
    ) -> Dict[str, Any]:
        """
        Verify a student's answer using RAG.

        Args:
            question: Original question
            student_answer: Student's answer to verify
            learner_level: Learner's level

        Returns:
            Dict with verification results (correct, feedback, citations)
        """
        # Get correct answer from RAG
        correct_response = self.teach(question, learner_level=learner_level)

        # Create verification prompt
        verification_prompt = f"""Compare the student's answer with the correct answer from the materials.

**Question:** {question}

**Student's Answer:**
{student_answer}

**Correct Answer (from materials):**
{correct_response.answer}

**Your Task:**
1. Is the student's answer correct? (Yes/Partially/No)
2. What did they get right?
3. What did they miss or get wrong?
4. Provide constructive feedback

**Evaluation:**"""

        evaluation = self.llm.predict(verification_prompt)

        return {
            "evaluation": evaluation,
            "correct_answer": correct_response.answer,
            "citations": correct_response.citations,
            "confidence": correct_response.confidence,
        }

    def get_related_topics(
        self,
        topic: str,
        top_k: int = 5,
    ) -> List[str]:
        """
        Find related topics based on document similarity.

        Args:
            topic: Base topic
            top_k: Number of related topics to return

        Returns:
            List of related topic names
        """
        # Search for documents related to the topic
        docs = self.vector_store.search(query=topic, top_k=top_k * 2)

        # Extract unique sources as related topics
        related = []
        seen_sources = set()

        for doc, score in docs:
            source = doc.metadata.get("source", "")
            title = doc.metadata.get("title", source)

            if title and title not in seen_sources:
                seen_sources.add(title)
                related.append(title)

                if len(related) >= top_k:
                    break

        return related


# Convenience function

def create_instructor_from_documents(
    documents_dir: str | Path,
    collection_name: str = "teaching_materials",
    force_reload: bool = False,
    learning_style: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
) -> RAGInstructor:
    """
    Create RAG instructor from a directory of teaching materials.

    Args:
        documents_dir: Directory containing teaching documents
        collection_name: Name for the vector store collection
        force_reload: Whether to reload documents even if collection exists
        learning_style: Learner's preferred learning styles
        interests: Learner's interests for personalized examples

    Returns:
        Initialized RAGInstructor

    Example:
        >>> instructor = create_instructor_from_documents(
        ...     "data/documents",
        ...     learning_style=["visual", "kinesthetic"],
        ...     interests=["sports", "music"]
        ... )
        >>> response = instructor.teach("What is machine learning?")
        >>> print(response.format_with_citations())
    """
    from ..utils.vector_store import initialize_vector_store_from_directory

    vector_store = initialize_vector_store_from_directory(
        directory=documents_dir,
        collection_name=collection_name,
        force_reload=force_reload,
    )

    return RAGInstructor(
        vector_store=vector_store,
        learning_style=learning_style,
        interests=interests
    )
