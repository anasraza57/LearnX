"""
RAG-based Instructor Agent with Citations.

This agent teaches using retrieval-augmented generation:
- Retrieves relevant context from document store
- Generates responses with citations
- Adapts explanation complexity to learner level
- Tracks sources used
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from langchain_core.prompts import PromptTemplate

try:
    from ..config import config
    from ..llm import make_chat_model, tracked_invoke
    from ..utils.vector_store import VectorStore
    from ..utils.document_loader import Document
    from ..utils.persistence import save_teaching_session
except ImportError:
    from src.config import config
    from src.llm import make_chat_model, tracked_invoke
    from src.utils.vector_store import VectorStore
    from src.utils.document_loader import Document
    from src.utils.persistence import save_teaching_session


@dataclass
class Citation:
    """
    Citation for a piece of information.

    Attributes:
        source: Source document name/title
        content: Brief excerpt from the source
        url: Original URL to the source (if available)
        source_type: Type of source (wikipedia, book, website, article, video, course)
        page: Page number (if applicable)
        filepath: Internal file path (not shown to user)
    """
    source: str
    content: str
    url: Optional[str] = None
    source_type: Optional[str] = None
    page: Optional[int] = None
    filepath: Optional[str] = None

    def __repr__(self) -> str:
        page_info = f", p.{self.page}" if self.page else ""
        return f"[{self.source}{page_info}]"

    def to_markdown(self) -> str:
        """Format citation as user-friendly markdown with clickable URL."""
        # Add source type emoji
        type_emoji = {
            "wikipedia": "📖",
            "book": "📚",
            "website": "🌐",
            "article": "📄",
            "video": "🎥",
            "course": "🎓",
            "tutorial": "💡",
            "paper": "📜"
        }.get(self.source_type, "📑")

        citation_text = self.source

        # Add page number if available
        if self.page:
            citation_text += f", page {self.page}"

        # Make clickable if URL available
        if self.url:
            result = f"{type_emoji} [{citation_text}]({self.url})\n"
        else:
            result = f"{type_emoji} **{citation_text}**\n"

        # Add brief excerpt
        result += f"> {self.content[:150]}...\n"

        return result


NO_CONTEXT_ANSWER = (
    "I don't have enough information in my knowledge base to answer this question "
    "accurately. Please provide relevant teaching materials."
)

# Inline citation markers the instructor is asked to emit: [1], [2, 3], [1-3], [1; 2],
# [Source 2], [Source 2: title]
INLINE_CITATION_PATTERN = re.compile(
    r"\[(?:Sources?\s+)?(\d+(?:\s*[-–,;]\s*(?:Sources?\s+)?\d+)*)(?:\s*:[^\]\n]*)?\]"
)
# Code is masked before matching so list literals such as [1, 2, 3] are not read as citations
CODE_SPAN_PATTERN = re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)|`[^`\n]*`", re.DOTALL)


def _mask_code(text: str) -> str:
    """Blank out fenced and inline code, preserving character offsets."""
    return CODE_SPAN_PATTERN.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)

CITATION_INSTRUCTION = """**Citation requirements:**
- Every factual statement that relies on the context must end with the number of the source that supports it, in square brackets, e.g. [1] or [2, 3]. The numbers refer to the [Source N] labels above.
- Only cite a source if that source actually supports the statement.
- Do not attach citations to your own examples, analogies or exercises unless a source supports them.
- Do not invent source numbers that do not appear in the context."""


def learning_style_guidance(learning_style: List[str]) -> str:
    """Formatting guidance for the learner's learning style preferences."""
    guidance_parts = []

    if "visual" in learning_style:
        guidance_parts.append("   - VISUAL learners: Use analogies, describe visual patterns, suggest diagrams/charts, use formatting (lists, tables, bullet points)")

    if "auditory" in learning_style:
        guidance_parts.append("   - AUDITORY learners: Use conversational tone, explain step-by-step verbally, include discussion points")

    if "kinesthetic" in learning_style:
        guidance_parts.append("   - KINESTHETIC learners: Include hands-on examples, practical exercises, real-world applications, actionable steps")

    if "reading_writing" in learning_style:
        guidance_parts.append("   - READING/WRITING learners: Provide detailed text explanations, written summaries, definitions, note-taking suggestions")

    return "\n".join(guidance_parts) if guidance_parts else "   - Use clear, balanced explanations"


def format_context(retrieved_docs: List[Tuple[Document, float]]) -> str:
    """Format retrieved passages as the numbered [Source N] context block."""
    context_parts = []
    for i, (doc, score) in enumerate(retrieved_docs, 1):
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "")
        page_info = f" (Page {page})" if page else ""

        context_parts.append(
            f"[Source {i}: {source}{page_info}]\n{doc.content}\n"
        )

    context = "\n---\n".join(context_parts)
    return context


def build_citations(retrieved_docs: List[Tuple[Document, float]], limit: int = 5) -> List[Citation]:
    """Deduplicate retrieved passages into a source list (one entry per source, at most `limit`)."""
    citations = []
    seen_sources = set()  # Track unique sources to avoid duplicates

    for doc, score in retrieved_docs:
        # Create unique key based on source and URL (not chunk)
        source_name = doc.metadata.get("source", "Unknown")
        original_url = doc.metadata.get("original_url")
        source_key = (source_name, original_url)  # Both must match for duplicate

        # Skip if we already cited this source
        if source_key in seen_sources:
            continue

        seen_sources.add(source_key)

        # Get source type from metadata
        source_type = doc.metadata.get("source_type", "document")

        # Create citation with URL and type
        citation = Citation(
            source=source_name,
            content=doc.content[:200],  # Brief excerpt for display
            url=original_url,
            source_type=source_type,
            page=doc.metadata.get("page"),
            filepath=doc.metadata.get("filepath"),
        )
        citations.append(citation)

        # Limit unique sources
        if len(citations) >= limit:
            break
    return citations


def extract_inline_citations(answer: str, num_passages: int) -> List[Dict[str, Any]]:
    """
    Find inline citation markers in an answer and check them against the
    passages that were supplied.

    Returns one entry per cited number, with its character offset and whether
    it refers to a passage that exists (1..num_passages).
    """
    found = []
    for match in INLINE_CITATION_PATTERN.finditer(_mask_code(answer)):
        numbers: List[int] = []
        for part in re.split(r"\s*[,;]\s*", match.group(1)):
            bounds = [int(n) for n in re.findall(r"\d+", part)]
            if len(bounds) == 2 and bounds[0] < bounds[1] <= bounds[0] + 20:
                numbers.extend(range(bounds[0], bounds[1] + 1))  # a range such as 1-3
            else:
                numbers.extend(bounds)
        for index in numbers:
            found.append({
                "marker": match.group(0),
                "offset": match.start(),
                "passage_index": index,
                "valid": 1 <= index <= num_passages,
            })
    return found


@dataclass
class TeachingResponse:
    """
    Response from the RAG instructor.

    Attributes:
        answer: The teaching explanation
        citations: List of citations used
        retrieved_docs: Original documents retrieved
        confidence: Retrieval confidence (0-1), derived from the mean similarity
            of the retrieved passages. It is not reported by the model
        mode: "grounded" or "ungrounded"
        refused: True when the canned no-context answer was returned
        inline_citations: Inline citation markers found in the answer
        prompt: The exact prompt sent to the model (None if no call was made)
        call_id: Joins this response to its usage record (None if no call was made)
        retrieval_s: Time spent in retrieval
    """
    answer: str
    citations: List[Citation] = field(default_factory=list)
    retrieved_docs: List[Tuple[Document, float]] = field(default_factory=list)
    confidence: float = 1.0
    mode: str = "grounded"
    refused: bool = False
    inline_citations: List[Dict[str, Any]] = field(default_factory=list)
    prompt: Optional[str] = None
    call_id: Optional[str] = None
    retrieval_s: Optional[float] = None

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
        vector_store: Optional[VectorStore],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        top_k_retrieval: int = None,
        min_similarity: Optional[float] = None,
        learning_style: Optional[List[str]] = None,
        interests: Optional[List[str]] = None,
        grounded: bool = True,
        citation_instruction: bool = True,
    ):
        """
        Initialize RAG instructor.

        Args:
            vector_store: Initialized vector store with documents
            model_name: LLM model name (default from config)
            temperature: LLM temperature (0=deterministic, 1=creative)
            top_k_retrieval: Number of documents to retrieve (default from config)
            min_similarity: Minimum similarity threshold (default from config)
            learning_style: Learner's preferred learning styles (visual, auditory, kinesthetic, reading_writing)
            interests: Learner's interests for generating relevant examples
            grounded: If False, never retrieve and answer from the model's own
                knowledge (the no-retrieval ablation)
            citation_instruction: If True, instruct the model to cite sources
                inline by passage number
        """
        if grounded and vector_store is None:
            raise ValueError("A grounded instructor needs a vector store")

        self.vector_store = vector_store
        self.top_k = top_k_retrieval or config.rag.top_k
        self.min_similarity = (
            config.rag.similarity_threshold if min_similarity is None else min_similarity
        )
        self.model_name = model_name or config.model.model_name
        self.learning_style = learning_style or ["visual"]
        self.interests = interests or []
        self.grounded = grounded
        self.citation_instruction = citation_instruction and grounded

        # Conversation history for follow-up questions
        self.conversation_history = []

        # Initialize LLM
        self.llm = make_chat_model("instructor", temperature=temperature, model_name=self.model_name)

        # Build learning style guidance
        style_guidance = self._get_learning_style_guidance()

        # Build interests context
        interests_text = f"Learner is interested in: {', '.join(self.interests)}" if self.interests else "No specific interests provided"

        citation_block = CITATION_INSTRUCTION.strip() + "\n\n" if self.citation_instruction else ""

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

{citation_block}**Answer:**"""
        )

        # Ungrounded prompt: same persona and personalisation, no context block
        self.ungrounded_prompt_template = PromptTemplate(
            input_variables=["question", "learner_level", "prior_knowledge"],
            template=f"""You are an expert educational instructor. Your task is to explain concepts clearly and accurately.

**Learner Level:** {{learner_level}}
**Learning Style Preferences:** {', '.join(self.learning_style)}
**Learner's Prior Knowledge:** {{prior_knowledge}}
**Learner's Interests:** {interests_text}

**Question:** {{question}}

**Instructions:**
1. Answer the question from your own knowledge
2. Adapt your explanation complexity to the learner's level (novice/beginner/intermediate/advanced/expert)
3. Build on the learner's prior knowledge when relevant - connect new concepts to what they already know
4. When appropriate, use examples or analogies from the learner's interests to make concepts more relatable
5. Format your response according to the learner's learning style preferences:
{style_guidance}
6. Be clear, accurate, and pedagogical
7. Break down complex concepts into understandable parts

**Answer:**"""
        )

    def _get_learning_style_guidance(self) -> str:
        """Generate formatting guidance based on learning style preferences."""
        return learning_style_guidance(self.learning_style)

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
        if not self.grounded:
            return self._teach_ungrounded(question, learner_level, prior_knowledge)

        # Step 1: Retrieve relevant documents with min_similarity filter
        started = time.perf_counter()
        retrieved_docs = self.vector_store.search(
            query=question,
            top_k=self.top_k,
            metadata_filter=metadata_filter,
            min_similarity=self.min_similarity,
        )
        retrieval_s = time.perf_counter() - started

        if not retrieved_docs:
            return TeachingResponse(
                answer=NO_CONTEXT_ANSWER,
                confidence=0.0,
                refused=True,
                retrieval_s=retrieval_s,
            )

        # Step 2: Prepare context from retrieved documents
        context = format_context(retrieved_docs)

        # Step 3-4: Generate answer using LLM
        prompt = self._with_history(self.prompt_template.format(
            question=question,
            context=context,
            learner_level=learner_level,
            prior_knowledge=self._prior_knowledge_text(prior_knowledge),
        ))
        answer, call_id = self._generate(question, prompt)

        # Step 4: Create deduplicated citations with URLs
        citations = build_citations(retrieved_docs)

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
            mode="grounded",
            inline_citations=extract_inline_citations(answer, len(retrieved_docs)),
            prompt=prompt,
            call_id=call_id,
            retrieval_s=retrieval_s,
        )

    def _teach_ungrounded(
        self,
        question: str,
        learner_level: str,
        prior_knowledge: Optional[Dict[str, str]],
    ) -> TeachingResponse:
        """Answer from the model's own knowledge, with no retrieval."""
        prompt = self._with_history(self.ungrounded_prompt_template.format(
            question=question,
            learner_level=learner_level,
            prior_knowledge=self._prior_knowledge_text(prior_knowledge),
        ))
        answer, call_id = self._generate(question, prompt)
        return TeachingResponse(
            answer=answer,
            confidence=0.0,
            mode="ungrounded",
            prompt=prompt,
            call_id=call_id,
        )

    @staticmethod
    def _prior_knowledge_text(prior_knowledge: Optional[Dict[str, str]]) -> str:
        if prior_knowledge:
            return ", ".join([f"{topic} ({level})" for topic, level in prior_knowledge.items()])
        return "None specified"

    def _with_history(self, prompt: str) -> str:
        """Prepend the last three exchanges so follow-up questions have context."""
        if not self.conversation_history:
            return prompt
        history_context = "\n\n**Recent Conversation:**\n"
        for i, (q, a) in enumerate(self.conversation_history[-3:], 1):
            history_context += f"Q{i}: {q}\nA{i}: {a[:200]}...\n"
        return history_context + "\n" + prompt

    def _generate(self, question: str, prompt: str) -> Tuple[str, str]:
        reply, call_id = tracked_invoke(self.llm, prompt)
        answer = reply.content
        self.conversation_history.append((question, answer))
        # Keep only last 10 exchanges
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        return answer, call_id

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
                    "url": c.url,
                    "source_type": c.source_type,
                    "page": c.page,
                    "filepath": c.filepath,
                    "content": c.content,
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

        evaluation = tracked_invoke(self.llm, verification_prompt)[0].content

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
    **instructor_kwargs: Any,
) -> RAGInstructor:
    """
    Create RAG instructor from a directory of teaching materials.

    Args:
        documents_dir: Directory containing teaching documents
        collection_name: Name for the vector store collection
        force_reload: Whether to reload documents even if collection exists
        learning_style: Learner's preferred learning styles
        interests: Learner's interests for personalised examples
        **instructor_kwargs: Passed through to RAGInstructor

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
        interests=interests,
        **instructor_kwargs,
    )
