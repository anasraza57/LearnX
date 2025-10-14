"""
Adaptive Quiz System - Adjusts difficulty based on learner performance.

Implements adaptive testing algorithm that dynamically selects question difficulty.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

try:
    from ..agents.assessment_generator import AssessmentQuestion
except ImportError:
    from src.agents.assessment_generator import AssessmentQuestion


@dataclass
class QuestionResponse:
    """
    Learner's response to a question.

    Attributes:
        question_id: Question identifier
        question_text: Question text (for reference)
        question_type: Type of question
        difficulty: Question difficulty
        points: Points this question is worth (for weighted scoring)
        learner_answer: Learner's response
        is_correct: Whether answer is correct
        score: Score (0-100)
        time_taken_seconds: Time spent
        hints_used: Number of hints used
        response_status: Status (answered/skipped/graded)
        feedback: Feedback provided
        graded_by: Who graded this response
    """
    question_id: str
    question_text: str
    question_type: str
    difficulty: str
    points: float = 1.0
    learner_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    time_taken_seconds: Optional[int] = None
    hints_used: int = 0
    response_status: str = "unanswered"
    feedback: Optional[str] = None
    graded_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "learner_answer": self.learner_answer,
            "is_correct": self.is_correct,
            "score": self.score,
            "time_taken_seconds": self.time_taken_seconds,
            "hints_used": self.hints_used,
            "response_status": self.response_status,
            "feedback": self.feedback,
            "graded_by": self.graded_by,
        }


class AdaptiveQuiz:
    """
    Adaptive quiz that adjusts difficulty based on performance.

    Features:
    - Start at learner's current level
    - Increase difficulty on correct answers
    - Decrease difficulty on incorrect answers
    - Track performance throughout quiz
    - Generate recommendations
    """

    DIFFICULTY_ORDER = ["very_easy", "easy", "medium", "hard", "very_hard"]

    def __init__(
        self,
        session_id: Optional[str] = None,
        learner_id: str = None,
        module_id: str = None,
        topic_id: Optional[str] = None,
        syllabus_id: Optional[str] = None,
        teaching_session_id: Optional[str] = None,
        quiz_type: str = "practice",
        starting_difficulty: str = "medium",
        num_questions: int = 10,
        passing_score: float = 70.0,
        adaptive: bool = True,
    ):
        """
        Initialize adaptive quiz.

        Args:
            session_id: Quiz session ID (auto-generated if None)
            learner_id: Learner taking the quiz
            module_id: Module being assessed
            topic_id: Optional specific topic
            syllabus_id: Optional syllabus reference
            teaching_session_id: Optional teaching session reference (Phase 3→4 integration)
            quiz_type: Type of quiz (diagnostic/formative/summative/practice)
            starting_difficulty: Initial difficulty level
            num_questions: Total questions in quiz
            passing_score: Score required to pass (0-100)
            adaptive: Whether to adapt difficulty
        """
        self.session_id = session_id or f"qs-{uuid.uuid4()}"
        self.learner_id = learner_id
        self.module_id = module_id
        self.topic_id = topic_id
        self.syllabus_id = syllabus_id
        self.teaching_session_id = teaching_session_id
        self.quiz_type = quiz_type
        self.starting_difficulty = starting_difficulty
        self.current_difficulty = starting_difficulty
        self.num_questions = num_questions
        self.passing_score = passing_score
        self.adaptive = adaptive

        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = None
        self.status = "in_progress"

        self.questions: List[AssessmentQuestion] = []
        self.responses: List[QuestionResponse] = []
        self.difficulty_progression: List[str] = [starting_difficulty]

        # Performance tracking
        self.consecutive_correct = 0
        self.consecutive_incorrect = 0

        # Metadata with numeric difficulty tracking
        self._metadata = {
            "difficulty_numeric_progression": [self._difficulty_to_numeric(starting_difficulty)]
        }

    def add_question(self, question: AssessmentQuestion):
        """Add a question to the quiz."""
        self.questions.append(question)

    def submit_answer(
        self,
        question_id: str,
        learner_answer: str,
        time_taken_seconds: Optional[int] = None,
        hints_used: int = 0,
    ) -> QuestionResponse:
        """
        Submit answer for a question.

        Args:
            question_id: Question identifier
            learner_answer: Learner's response
            time_taken_seconds: Time spent on question
            hints_used: Number of hints used

        Returns:
            QuestionResponse with grading results

        Raises:
            ValueError: If validation checks fail
        """
        # Validation checks
        if not learner_answer or not learner_answer.strip():
            raise ValueError("Learner answer cannot be empty")

        if time_taken_seconds is not None and time_taken_seconds < 0:
            raise ValueError(f"Time taken cannot be negative: {time_taken_seconds}")

        if hints_used < 0:
            raise ValueError(f"Hints used cannot be negative: {hints_used}")

        # Find the question
        question = next((q for q in self.questions if q.question_id == question_id), None)
        if not question:
            raise ValueError(f"Question {question_id} not found in quiz")

        # Check if already answered
        existing = next((r for r in self.responses if r.question_id == question_id), None)
        if existing:
            raise ValueError(f"Question {question_id} already answered")

        # Auto-grade if possible
        is_correct, score, feedback = self._auto_grade(question, learner_answer)

        # Validate and clamp score
        if score is not None:
            if score < 0 or score > 100:
                raise ValueError(f"Score must be between 0 and 100, got {score}")
            score = max(0.0, min(100.0, score))

        # Create response
        response = QuestionResponse(
            question_id=question_id,
            question_text=question.question_text,
            question_type=question.question_type,
            difficulty=question.difficulty,
            points=question.points,  # Store points for reproducible weighted scoring
            learner_answer=learner_answer,
            is_correct=is_correct,
            score=score,
            time_taken_seconds=time_taken_seconds,
            hints_used=hints_used,
            response_status="graded" if is_correct is not None else "answered",
            feedback=feedback,
            graded_by="auto" if is_correct is not None else None,
        )

        self.responses.append(response)

        # Update difficulty if adaptive
        if self.adaptive and is_correct is not None:
            self._update_difficulty(is_correct)

        return response

    def skip_question(self, question_id: str) -> QuestionResponse:
        """Mark a question as skipped."""
        question = next((q for q in self.questions if q.question_id == question_id), None)
        if not question:
            raise ValueError(f"Question {question_id} not found")

        response = QuestionResponse(
            question_id=question_id,
            question_text=question.question_text,
            question_type=question.question_type,
            difficulty=question.difficulty,
            points=question.points,
            response_status="skipped",
        )

        self.responses.append(response)
        return response

    def complete_quiz(self) -> Dict[str, Any]:
        """
        Complete the quiz and generate final results.

        Returns:
            Dictionary with quiz results and recommendations

        Raises:
            ValueError: If integrity checks fail
        """
        # Integrity checks
        total_questions = len(self.questions)
        answered_count = len([r for r in self.responses if r.response_status in {"answered", "graded"}])

        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc).isoformat()

        # Calculate overall score (points-weighted)
        # Use points stored in responses for reproducibility (no need to look up questions)
        graded_responses = [r for r in self.responses if r.score is not None]
        if graded_responses:
            # Points-weighted: score = 100 * (sum(obtained_points) / sum(total_points))
            total_points = sum(r.points for r in graded_responses)
            obtained_points = sum((r.points * r.score / 100) for r in graded_responses)
            self.overall_score = 100 * (obtained_points / total_points) if total_points > 0 else 0
        else:
            self.overall_score = None

        # Determine pass/fail
        self.passed = self.overall_score >= self.passing_score if self.overall_score is not None else None

        # Final integrity check: if completed, passed must be non-null and score must be set
        if self.status == "completed":
            if self.passed is None:
                raise ValueError("Integrity error: Quiz marked completed but passed status is None")
            if self.overall_score is None:
                raise ValueError("Integrity error: Quiz marked completed but overall_score is None")

        # Generate recommendations
        recommendations = self._generate_recommendations()

        return {
            "session_id": self.session_id,
            "score": self.overall_score,
            "passed": self.passed,
            "total_questions": len(self.questions),
            "answered_questions": len([r for r in self.responses if r.response_status != "unanswered"]),
            "recommendations": recommendations,
        }

    def get_next_difficulty(self) -> str:
        """Get the current difficulty level for next question."""
        return self.current_difficulty

    def to_dict(self) -> Dict[str, Any]:
        """Convert quiz session to dictionary for persistence."""
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "completed_at": self.completed_at,
            "learner_id": self.learner_id,
            "syllabus_id": self.syllabus_id,
            "module_id": self.module_id,
            "topic_id": self.topic_id,
            "quiz_type": self.quiz_type,
            "status": self.status,
            "adaptive": self.adaptive,
            "questions": [r.to_dict() for r in self.responses],
            "total_questions": len(self.questions),
            "answered_questions": len([r for r in self.responses if r.response_status != "unanswered"]),
            "score": getattr(self, "overall_score", None),
            "passing_score": self.passing_score,
            "passed": getattr(self, "passed", None),
            "total_time_seconds": sum(r.time_taken_seconds or 0 for r in self.responses),
            "difficulty_progression": self.difficulty_progression,
            "recommendations": getattr(self, "_recommendations", None),
        }

    def _auto_grade(
        self,
        question: AssessmentQuestion,
        learner_answer: str,
    ) -> tuple[Optional[bool], Optional[float], Optional[str]]:
        """
        Auto-grade a question if possible.

        Returns:
            (is_correct, score, feedback) tuple
        """
        if question.question_type == "multiple_choice":
            # Find correct option
            correct_option = next(
                (opt for opt in question.options if opt["is_correct"]), None
            )
            if correct_option:
                is_correct = learner_answer.strip().upper() == correct_option["option_id"]
                score = 100.0 if is_correct else 0.0
                feedback = question.explanation if is_correct else "Incorrect. " + (question.explanation or "")
                return is_correct, score, feedback

        elif question.question_type == "true_false":
            correct_answer = question.correct_answer.lower().strip() if question.correct_answer else None
            learner_answer_clean = learner_answer.lower().strip()
            if correct_answer:
                is_correct = learner_answer_clean == correct_answer
                score = 100.0 if is_correct else 0.0
                feedback = question.explanation or ""
                return is_correct, score, feedback

        # Can't auto-grade short_answer, essay, code - needs LLM grading
        return None, None, "Requires manual grading"

    def _update_difficulty(self, is_correct: bool):
        """Update difficulty based on performance."""
        if is_correct:
            self.consecutive_correct += 1
            self.consecutive_incorrect = 0

            # Increase difficulty after 2 consecutive correct
            if self.consecutive_correct >= 2:
                self._increase_difficulty()
                self.consecutive_correct = 0
        else:
            self.consecutive_incorrect += 1
            self.consecutive_correct = 0

            # Decrease difficulty after 2 consecutive incorrect
            if self.consecutive_incorrect >= 2:
                self._decrease_difficulty()
                self.consecutive_incorrect = 0

    def _difficulty_to_numeric(self, difficulty: str) -> int:
        """Convert difficulty to numeric scale: very_easy=-2, easy=-1, medium=0, hard=1, very_hard=2."""
        mapping = {
            "very_easy": -2,
            "easy": -1,
            "medium": 0,
            "hard": 1,
            "very_hard": 2
        }
        return mapping.get(difficulty, 0)

    def _increase_difficulty(self):
        """Increase difficulty level."""
        current_idx = self.DIFFICULTY_ORDER.index(self.current_difficulty)
        if current_idx < len(self.DIFFICULTY_ORDER) - 1:
            self.current_difficulty = self.DIFFICULTY_ORDER[current_idx + 1]
            self.difficulty_progression.append(self.current_difficulty)
            # Track numeric progression
            self._metadata["difficulty_numeric_progression"].append(
                self._difficulty_to_numeric(self.current_difficulty)
            )

    def _decrease_difficulty(self):
        """Decrease difficulty level."""
        current_idx = self.DIFFICULTY_ORDER.index(self.current_difficulty)
        if current_idx > 0:
            self.current_difficulty = self.DIFFICULTY_ORDER[current_idx - 1]
            self.difficulty_progression.append(self.current_difficulty)
            # Track numeric progression
            self._metadata["difficulty_numeric_progression"].append(
                self._difficulty_to_numeric(self.current_difficulty)
            )

    def _generate_recommendations(self) -> Dict[str, Any]:
        """Generate recommendations based on performance."""
        # Topics that need review (incorrect answers)
        incorrect_responses = [r for r in self.responses if r.is_correct is False]
        should_review = list(set([self.topic_id] if self.topic_id and incorrect_responses else []))

        # Recommend next difficulty
        if self.overall_score is not None:
            if self.overall_score >= 90:
                next_difficulty = "hard" if self.current_difficulty != "very_hard" else "very_hard"
            elif self.overall_score >= 70:
                next_difficulty = "medium"
            else:
                next_difficulty = "easy"
        else:
            next_difficulty = self.current_difficulty

        # Ready for next module?
        ready_for_next = self.passed if self.passed is not None else False

        # Recommend next topic (if passed, suggest moving on; if failed, suggest current topic review)
        next_topic_id = None
        if ready_for_next and self.topic_id:
            # Could integrate with syllabus to get next topic, for now return None
            next_topic_id = None
        elif not ready_for_next and should_review:
            # Suggest staying on current topic
            next_topic_id = self.topic_id

        self._recommendations = {
            "should_review": should_review,
            "next_difficulty": next_difficulty,
            "next_topic_id": next_topic_id,
            "ready_for_next_module": ready_for_next,
        }

        return self._recommendations
