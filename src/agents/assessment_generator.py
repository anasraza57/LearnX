"""
Assessment Generator Agent - Creates questions from syllabus and teaching materials.

Uses RAG + LLM to generate contextually relevant questions aligned with learning objectives.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.prompts import PromptTemplate

try:
    from ..config import config
    from ..llm import make_chat_model, parse_json_response, tracked_invoke
    from ..utils.vector_store import VectorStore
except ImportError:
    from src.config import config
    from src.llm import make_chat_model, parse_json_response, tracked_invoke
    from src.utils.vector_store import VectorStore


# Type aliases
QuestionType = str  # "multiple_choice", "true_false", "short_answer", "essay", "code"
DifficultyLevel = str  # "very_easy", "easy", "medium", "hard", "very_hard"
BloomLevel = str  # "remember", "understand", "apply", "analyze", "evaluate", "create"


@dataclass
class AssessmentQuestion:
    """
    A single assessment question.

    Attributes:
        question_id: Unique identifier
        question_text: The question text
        question_type: Type of question
        difficulty: Difficulty level
        module_id: Reference to syllabus module
        options: Options for MCQ (if applicable)
        correct_answer: Correct answer
        explanation: Explanation of correct answer
        bloom_level: Bloom's taxonomy level
    """
    question_id: str
    question_text: str
    question_type: QuestionType
    difficulty: DifficultyLevel
    module_id: str
    topic_id: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    bloom_level: Optional[BloomLevel] = None
    learning_objectives: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    answer_rubric: Optional[str] = None
    points: float = 1.0
    time_limit_seconds: Optional[int] = None
    source_material: Optional[Dict[str, Any]] = None
    # How the item was produced (retrieval outcome, prompt, parse fallback).
    # Diagnostic only; not part of the persisted assessment schema.
    generation_meta: Dict[str, Any] = field(default_factory=dict, repr=False)

    @staticmethod
    def normalize_page_number(page: int, zero_indexed: bool = True) -> int:
        """
        Normalize page number to 1-indexed format for persistence.

        Args:
            page: Page number
            zero_indexed: Whether input is 0-indexed (default True for most loaders)

        Returns:
            1-indexed page number for schema compliance
        """
        if zero_indexed:
            return page + 1
        return page

    def validate(self) -> None:
        """
        Validate question integrity.

        Raises:
            ValueError: If validation fails
        """
        # MCQ must have options with at least one correct
        if self.question_type == "multiple_choice":
            if not self.options or len(self.options) < 2:
                raise ValueError(
                    f"MCQ question {self.question_id} must have at least 2 options, got {len(self.options or [])}"
                )

            # Check at least one correct option
            correct_options = [opt for opt in self.options if opt.get("is_correct", False)]
            if not correct_options:
                raise ValueError(
                    f"MCQ question {self.question_id} must have at least one correct option"
                )

            # Validate option_id format (A-F for up to 6 options)
            valid_ids = set("ABCDEF"[:len(self.options)])
            for opt in self.options:
                opt_id = opt.get("option_id", "")
                if opt_id not in valid_ids:
                    raise ValueError(
                        f"MCQ question {self.question_id} has invalid option_id '{opt_id}', "
                        f"expected one of {valid_ids}"
                    )

        # True/False must have correct_answer
        elif self.question_type == "true_false":
            if not self.correct_answer or self.correct_answer.lower() not in {"true", "false"}:
                raise ValueError(
                    f"True/False question {self.question_id} must have correct_answer as 'true' or 'false'"
                )

        # Validate points
        if self.points <= 0 or self.points > 100:
            raise ValueError(
                f"Question {self.question_id} points must be between 0 and 100, got {self.points}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "module_id": self.module_id,
            "topic_id": self.topic_id,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "bloom_level": self.bloom_level,
            "learning_objectives": self.learning_objectives,
            "hints": self.hints,
            "answer_rubric": self.answer_rubric,
            "points": self.points,
            "time_limit_seconds": self.time_limit_seconds,
            "source_material": self.source_material,
        }


class AssessmentGenerator:
    """
    Generates assessment questions using RAG + LLM.

    Features:
    - Generate questions from syllabus learning objectives
    - Create questions from teaching materials using RAG
    - Support multiple question types
    - Align with Bloom's taxonomy
    - Control difficulty level
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize assessment generator.

        Args:
            vector_store: Vector store with teaching materials (for RAG-based generation)
            model_name: LLM model name
            temperature: LLM temperature (higher = more creative)
        """
        self.vector_store = vector_store
        self.model_name = model_name or config.model.model_name

        # Initialize LLM
        self.llm = make_chat_model("assessment", temperature=temperature, model_name=self.model_name)

        # Question generation prompts
        self.mcq_prompt = PromptTemplate(
            input_variables=["context", "topic", "difficulty", "bloom_level", "learning_objective"],
            template="""You are an expert educational assessment designer. Create a multiple-choice question based on the following information.

**Topic:** {topic}
**Difficulty:** {difficulty} (very_easy/easy/medium/hard/very_hard)
**Bloom's Level:** {bloom_level} (remember/understand/apply/analyze/evaluate/create)
**Learning Objective:** {learning_objective}

**Context from teaching materials:**
{context}

**Requirements:**
1. Create a clear, unambiguous question
2. Provide 4 options (A, B, C, D)
3. Only ONE option should be correct
4. Make distractors plausible but clearly wrong
5. Match the specified difficulty and Bloom's level
6. Align with the learning objective

**Format your response as JSON:**
{{
  "question_text": "...",
  "options": [
    {{"option_id": "A", "text": "...", "is_correct": false}},
    {{"option_id": "B", "text": "...", "is_correct": true}},
    {{"option_id": "C", "text": "...", "is_correct": false}},
    {{"option_id": "D", "text": "...", "is_correct": false}}
  ],
  "explanation": "Brief explanation of why B is correct",
  "bloom_level": "{bloom_level}"
}}

**Question:**"""
        )

        self.short_answer_prompt = PromptTemplate(
            input_variables=["context", "topic", "difficulty", "bloom_level", "learning_objective"],
            template="""You are an expert educational assessment designer. Create a short-answer question based on the following information.

**Topic:** {topic}
**Difficulty:** {difficulty}
**Bloom's Level:** {bloom_level}
**Learning Objective:** {learning_objective}

**Context from teaching materials:**
{context}

**Requirements:**
1. Create a question that requires a brief (1-3 sentence) answer
2. Question should test understanding, not just recall
3. Match the specified difficulty and Bloom's level
4. Provide a model answer and grading rubric

**Format your response as JSON:**
{{
  "question_text": "...",
  "correct_answer": "Model answer (1-3 sentences)",
  "answer_rubric": "Key points that should be included: 1) ..., 2) ..., 3) ...",
  "explanation": "Why this answer is correct",
  "bloom_level": "{bloom_level}"
}}

**Question:**"""
        )

    def generate_question(
        self,
        module_id: str,
        topic: str,
        question_type: QuestionType = "multiple_choice",
        difficulty: DifficultyLevel = "medium",
        bloom_level: Optional[BloomLevel] = None,
        learning_objective: Optional[str] = None,
        use_rag: bool = True,
    ) -> AssessmentQuestion:
        """
        Generate a single assessment question.

        Args:
            module_id: Module this question belongs to
            topic: Topic/concept to test
            question_type: Type of question to generate
            difficulty: Difficulty level
            bloom_level: Bloom's taxonomy level (auto-selected if None)
            learning_objective: Specific learning objective to test
            use_rag: Whether to use RAG to retrieve context from materials

        Returns:
            AssessmentQuestion object
        """
        # Auto-select Bloom's level based on difficulty if not specified
        if bloom_level is None:
            bloom_level = self._suggest_bloom_level(difficulty)

        # Get context from RAG if available and requested
        context = ""
        source_material = None
        retrieved_docs = []
        retrieval_s = None
        rag_attempted = bool(use_rag and self.vector_store)
        if rag_attempted:
            # Same pinned retrieval parameters as the instructor
            started = time.perf_counter()
            retrieved_docs = self.vector_store.search(
                query=topic,
                top_k=config.rag.top_k,
                min_similarity=config.rag.similarity_threshold,
            )
            retrieval_s = time.perf_counter() - started
            if retrieved_docs:
                context = "\n\n".join([doc.content for doc, _ in retrieved_docs])
                # Store source reference
                doc, score = retrieved_docs[0]
                source_material = {
                    "source": doc.metadata.get("source", "unknown"),
                    "page": doc.metadata.get("page"),
                    "section": doc.metadata.get("title"),
                }

        # If no context from RAG, use a generic context
        if not context:
            context = f"Generate a question about {topic} for educational assessment."

        # Default learning objective if not provided
        if not learning_objective:
            learning_objective = f"Assess understanding of {topic}"

        # Generate question based on type
        if question_type == "multiple_choice":
            question_data = self._generate_mcq(
                context, topic, difficulty, bloom_level, learning_objective
            )
        elif question_type == "short_answer":
            question_data = self._generate_short_answer(
                context, topic, difficulty, bloom_level, learning_objective
            )
        else:
            raise ValueError(f"Unsupported question type: {question_type}")
        parse_fallback = question_data.pop("_parse_fallback", False)
        raw_response = question_data.pop("_raw_response", None)
        prompt = question_data.pop("_prompt", None)
        call_id = question_data.pop("_call_id", None)

        # Create AssessmentQuestion object
        question_id = f"q-{uuid.uuid4()}"

        return AssessmentQuestion(
            question_id=question_id,
            question_text=question_data["question_text"],
            question_type=question_type,
            difficulty=difficulty,
            module_id=module_id,
            topic_id=topic,
            options=question_data.get("options"),
            correct_answer=question_data.get("correct_answer"),
            explanation=question_data.get("explanation"),
            bloom_level=question_data.get("bloom_level", bloom_level),
            learning_objectives=[learning_objective] if learning_objective else [],
            answer_rubric=question_data.get("answer_rubric"),
            source_material=source_material,
            generation_meta={
                "rag_attempted": rag_attempted,
                "retrieval_hits": len(retrieved_docs),
                "retrieval_failed": rag_attempted and not retrieved_docs,
                "retrieved": [
                    {
                        "chunk_id": doc.metadata.get("chunk_id"),
                        "source": doc.metadata.get("source"),
                        "doc_id": doc.metadata.get("doc_id"),
                        "strand": doc.metadata.get("strand"),
                        "similarity": score,
                        "content": doc.content,
                    }
                    for doc, score in retrieved_docs
                ],
                "retrieval_s": retrieval_s,
                "parse_fallback": parse_fallback,
                "raw_response": raw_response,
                "prompt": prompt,
                "call_id": call_id,
            },
        )

    def generate_quiz(
        self,
        module_id: str,
        topics: List[str],
        num_questions: int = 5,
        question_types: Optional[List[QuestionType]] = None,
        difficulty: DifficultyLevel = "medium",
        use_rag: bool = True,
    ) -> List[AssessmentQuestion]:
        """
        Generate a complete quiz with multiple questions.

        Args:
            module_id: Module ID
            topics: List of topics to cover
            num_questions: Number of questions to generate
            question_types: Types of questions (if None, defaults to MCQ)
            difficulty: Difficulty level
            use_rag: Whether to use RAG

        Returns:
            List of AssessmentQuestion objects
        """
        if question_types is None:
            question_types = ["multiple_choice"]

        questions = []

        # Distribute questions across topics
        questions_per_topic = max(1, num_questions // len(topics))

        for topic in topics:
            for i in range(questions_per_topic):
                if len(questions) >= num_questions:
                    break

                # Vary question types
                q_type = question_types[i % len(question_types)]

                question = self.generate_question(
                    module_id=module_id,
                    topic=topic,
                    question_type=q_type,
                    difficulty=difficulty,
                    use_rag=use_rag,
                )
                questions.append(question)

        return questions[:num_questions]

    def _generate_mcq(
        self,
        context: str,
        topic: str,
        difficulty: str,
        bloom_level: str,
        learning_objective: str,
    ) -> Dict[str, Any]:
        """Generate a multiple-choice question."""

        prompt = self.mcq_prompt.format(
            context=context,
            topic=topic,
            difficulty=difficulty,
            bloom_level=bloom_level,
            learning_objective=learning_objective,
        )

        reply, call_id = tracked_invoke(self.llm, prompt)
        raw = reply.content
        meta = {"_raw_response": raw, "_prompt": prompt, "_call_id": call_id}

        # Parse JSON response (fences inside the question text are fine)
        try:
            question_data = parse_json_response(raw)
            if not isinstance(question_data, dict) or "question_text" not in question_data:
                raise json.JSONDecodeError("reply is not a question object", raw, 0)
            question_data.update(meta)
            return question_data
        except json.JSONDecodeError:
            # Fallback: a placeholder question, flagged as such
            return {
                "_parse_fallback": True,
                **meta,
                "question_text": f"What is {topic}?",
                "options": [
                    {"option_id": "A", "text": "Option A", "is_correct": True},
                    {"option_id": "B", "text": "Option B", "is_correct": False},
                    {"option_id": "C", "text": "Option C", "is_correct": False},
                    {"option_id": "D", "text": "Option D", "is_correct": False},
                ],
                "explanation": "This is the correct answer.",
                "bloom_level": bloom_level,
            }

    def _generate_short_answer(
        self,
        context: str,
        topic: str,
        difficulty: str,
        bloom_level: str,
        learning_objective: str,
    ) -> Dict[str, Any]:
        """Generate a short-answer question."""

        prompt = self.short_answer_prompt.format(
            context=context,
            topic=topic,
            difficulty=difficulty,
            bloom_level=bloom_level,
            learning_objective=learning_objective,
        )

        reply, call_id = tracked_invoke(self.llm, prompt)
        raw = reply.content
        meta = {"_raw_response": raw, "_prompt": prompt, "_call_id": call_id}

        # Parse JSON response (fences inside the question text are fine)
        try:
            question_data = parse_json_response(raw)
            if not isinstance(question_data, dict) or "question_text" not in question_data:
                raise json.JSONDecodeError("reply is not a question object", raw, 0)
            question_data.update(meta)
            return question_data
        except json.JSONDecodeError:
            # Fallback: a placeholder question, flagged as such
            return {
                "_parse_fallback": True,
                **meta,
                "question_text": f"Explain {topic}.",
                "correct_answer": f"A brief explanation of {topic}.",
                "answer_rubric": "Should include key concepts and clear explanation.",
                "explanation": "Model answer provided above.",
                "bloom_level": bloom_level,
            }

    def _suggest_bloom_level(self, difficulty: str) -> str:
        """Suggest Bloom's taxonomy level based on difficulty."""
        difficulty_to_bloom = {
            "very_easy": "remember",
            "easy": "understand",
            "medium": "apply",
            "hard": "analyze",
            "very_hard": "evaluate",
        }
        return difficulty_to_bloom.get(difficulty, "apply")
