"""
Grading Agent - LLM-based evaluation of open-ended responses.

Grades short answer, essay, and code questions using rubric-based evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

try:
    from ..config import config
    from .assessment_generator import AssessmentQuestion
except ImportError:
    from src.config import config
    from src.agents.assessment_generator import AssessmentQuestion


@dataclass
class GradingResult:
    """
    Result of grading an open-ended response.

    Attributes:
        score: Score from 0-100
        is_correct: Whether answer meets passing criteria
        feedback: Detailed feedback for learner
        strengths: What was done well
        improvements: Areas for improvement
        rubric_scores: Breakdown by rubric criteria
        graded_by: Source of grading ("llm", "human", "auto")
    """
    score: float
    is_correct: bool
    feedback: str
    strengths: list[str]
    improvements: list[str]
    rubric_scores: Optional[Dict[str, float]] = None
    graded_by: str = "llm"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "is_correct": self.is_correct,
            "feedback": self.feedback,
            "strengths": self.strengths,
            "improvements": self.improvements,
            "rubric_scores": self.rubric_scores,
        }


class GradingAgent:
    """
    AI-powered grading agent for open-ended questions.

    Uses LLM with rubric-based evaluation to provide consistent,
    detailed feedback on short answer, essay, and code responses.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.3,  # Lower temperature for consistent grading
    ):
        """
        Initialize grading agent.

        Args:
            model_name: LLM model name
            temperature: LLM temperature (lower = more consistent)
        """
        self.model_name = model_name or config.model.model_name

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
            api_key=config.model.api_key,
        )

        # Grading prompt template
        self.grading_prompt = PromptTemplate(
            input_variables=["question", "model_answer", "rubric", "learner_answer", "max_score"],
            template="""You are an expert educational grader. Grade the learner's answer using the provided rubric.

**Question:**
{question}

**Model Answer:**
{model_answer}

**Grading Rubric:**
{rubric}

**Learner's Answer:**
{learner_answer}

**Maximum Score:** {max_score}

**Instructions:**
1. Evaluate the learner's answer against the rubric criteria
2. Provide a score from 0 to {max_score}
3. Identify strengths (what was done well)
4. Identify improvements (what could be better)
5. Provide constructive, encouraging feedback

**Format your response as JSON:**
{{
  "score": <number 0-{max_score}>,
  "is_correct": <true if score >= 70% of max, false otherwise>,
  "strengths": ["strength 1", "strength 2", ...],
  "improvements": ["improvement 1", "improvement 2", ...],
  "feedback": "Detailed feedback for the learner (2-3 sentences)"
}}

**Evaluation:**"""
        )

        self.code_grading_prompt = PromptTemplate(
            input_variables=["question", "model_solution", "test_cases", "learner_code", "max_score"],
            template="""You are an expert code reviewer and grader. Grade the learner's code solution.

**Question:**
{question}

**Model Solution:**
{model_solution}

**Test Cases:**
{test_cases}

**Learner's Code:**
{learner_code}

**Maximum Score:** {max_score}

**Grading Criteria:**
1. Correctness (50%): Does it produce correct output?
2. Code Quality (25%): Is it readable, well-structured?
3. Efficiency (15%): Is it reasonably efficient?
4. Best Practices (10%): Follows conventions?

**Instructions:**
- Provide a score from 0 to {max_score}
- Identify what works well
- Identify issues and how to fix them
- Be constructive and educational

**Format your response as JSON:**
{{
  "score": <number 0-{max_score}>,
  "is_correct": <true if code is mostly correct, false otherwise>,
  "strengths": ["strength 1", "strength 2", ...],
  "improvements": ["improvement 1", "improvement 2", ...],
  "feedback": "Detailed feedback (2-3 sentences)",
  "rubric_scores": {{
    "correctness": <0-50>,
    "code_quality": <0-25>,
    "efficiency": <0-15>,
    "best_practices": <0-10>
  }}
}}

**Evaluation:**"""
        )

    def grade_response(
        self,
        question: AssessmentQuestion,
        learner_answer: str,
        passing_threshold: float = 70.0,
    ) -> GradingResult:
        """
        Grade a learner's response to an open-ended question.

        Args:
            question: The assessment question
            learner_answer: Learner's response
            passing_threshold: Minimum score to pass (as percentage)

        Returns:
            GradingResult with score and feedback

        Raises:
            ValueError: If validation checks fail
        """
        import json

        # Validation checks
        if not learner_answer or not learner_answer.strip():
            raise ValueError("Learner answer cannot be empty")

        if not question.question_text:
            raise ValueError("Question text cannot be empty")

        if question.points <= 0 or question.points > 100:
            raise ValueError(f"Question points must be between 0 and 100, got {question.points}")

        if question.question_type == "code":
            prompt = self.code_grading_prompt.format(
                question=question.question_text,
                model_solution=question.correct_answer or "See rubric",
                test_cases=question.answer_rubric or "N/A",
                learner_code=learner_answer,
                max_score=int(question.points),
            )
        else:
            prompt = self.grading_prompt.format(
                question=question.question_text,
                model_answer=question.correct_answer or "See rubric",
                rubric=question.answer_rubric or "Evaluate based on accuracy and completeness",
                learner_answer=learner_answer,
                max_score=int(question.points),
            )

        response = self.llm.invoke(prompt).content

        # Parse JSON response
        try:
            # Extract JSON from markdown if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            grading_data = json.loads(response)

            # Validate grading response
            if "score" not in grading_data:
                raise ValueError("Grading response missing 'score' field")

            # Convert score to 0-100 scale
            max_score = question.points or 100
            raw_score = grading_data["score"]

            if raw_score < 0 or raw_score > max_score:
                raise ValueError(f"Score {raw_score} out of valid range [0, {max_score}]")

            score_normalized = (raw_score / max_score) * 100

            # Ensure score is in [0, 100]
            score_normalized = max(0.0, min(100.0, score_normalized))

            return GradingResult(
                score=score_normalized,
                is_correct=grading_data.get("is_correct", score_normalized >= passing_threshold),
                feedback=grading_data.get("feedback", ""),
                strengths=grading_data.get("strengths", []),
                improvements=grading_data.get("improvements", []),
                rubric_scores=grading_data.get("rubric_scores"),
                graded_by="llm",  # Track grading source
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback grading with validation
            return GradingResult(
                score=50.0,
                is_correct=False,
                feedback=f"Unable to parse grading response. Error: {str(e)}",
                strengths=["Answer provided"],
                improvements=["Please review the question requirements"],
                graded_by="llm",
            )

    def batch_grade(
        self,
        questions: list[AssessmentQuestion],
        learner_answers: list[str],
        passing_threshold: float = 70.0,
    ) -> list[GradingResult]:
        """
        Grade multiple responses at once.

        Args:
            questions: List of questions
            learner_answers: List of learner responses
            passing_threshold: Minimum score to pass

        Returns:
            List of GradingResult objects
        """
        if len(questions) != len(learner_answers):
            raise ValueError("Number of questions must match number of answers")

        results = []
        for question, answer in zip(questions, learner_answers):
            result = self.grade_response(question, answer, passing_threshold)
            results.append(result)

        return results

    def provide_hints(
        self,
        question: AssessmentQuestion,
        learner_answer: str,
        hint_level: int = 1,
    ) -> str:
        """
        Provide progressive hints based on learner's current answer.

        Args:
            question: The question
            learner_answer: Current attempt
            hint_level: Hint level (1=gentle nudge, 2=more direct, 3=explicit)

        Returns:
            Hint text
        """
        # If question has pre-defined hints, use those
        if question.hints and len(question.hints) >= hint_level:
            return question.hints[hint_level - 1]

        # Generate dynamic hint
        hint_prompt = f"""Based on this question and the learner's attempt, provide a hint (level {hint_level}/3).

Question: {question.question_text}
Model Answer: {question.correct_answer}
Learner's Attempt: {learner_answer}

Hint Level {hint_level}: {"Gentle nudge - point them in the right direction" if hint_level == 1 else "More direct - identify specific gaps" if hint_level == 2 else "Explicit - show them how to approach it"}

Provide a short, helpful hint (1-2 sentences):"""

        hint = self.llm.invoke(hint_prompt).content
        return hint.strip()
