"""
Unit tests for Quiz Session and Adaptive Quiz (Phase 4).

Tests adaptive difficulty, scoring, validation, and recommendations.
"""

import unittest
from unittest.mock import Mock
import uuid

from src.models.quiz_session import AdaptiveQuiz, QuestionResponse
from src.agents.assessment_generator import AssessmentQuestion


class TestQuestionResponse(unittest.TestCase):
    """Test QuestionResponse dataclass."""

    def test_question_response_creation(self):
        """Test creating a QuestionResponse."""
        response = QuestionResponse(
            question_id="q-test-123",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            points=5.0,
            learner_answer="A",
            is_correct=True,
            score=100.0,
            graded_by="auto",
        )
        self.assertEqual(response.question_id, "q-test-123")
        self.assertEqual(response.points, 5.0)
        self.assertTrue(response.is_correct)
        self.assertEqual(response.graded_by, "auto")

    def test_question_response_to_dict(self):
        """Test converting QuestionResponse to dictionary."""
        response = QuestionResponse(
            question_id="q-test-123",
            question_text="Test?",
            question_type="short_answer",
            difficulty="easy",
            points=3.0,
        )
        result = response.to_dict()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["question_id"], "q-test-123")
        self.assertEqual(result["points"], 3.0)


class TestAdaptiveQuiz(unittest.TestCase):
    """Test AdaptiveQuiz model."""

    def setUp(self):
        """Set up test fixtures."""
        self.quiz = AdaptiveQuiz(
            learner_id="learner-test-123",
            module_id="m01-python",
            topic_id="variables",
            starting_difficulty="medium",
            num_questions=5,
            passing_score=70.0,
            adaptive=True,
        )

        self.mcq_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is 2+2?",
            question_type="multiple_choice",
            difficulty="easy",
            module_id="m01-python",
            options=[
                {"option_id": "A", "text": "3", "is_correct": False},
                {"option_id": "B", "text": "4", "is_correct": True},
                {"option_id": "C", "text": "5", "is_correct": False},
            ],
            points=2.0,
        )

        self.tf_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Python is a programming language",
            question_type="true_false",
            difficulty="very_easy",
            module_id="m01-python",
            correct_answer="true",
            points=1.0,
        )

    def test_initialization(self):
        """Test quiz initialization."""
        self.assertIsNotNone(self.quiz.session_id)
        self.assertTrue(self.quiz.session_id.startswith("qs-"))
        self.assertEqual(self.quiz.learner_id, "learner-test-123")
        self.assertEqual(self.quiz.current_difficulty, "medium")
        self.assertEqual(self.quiz.status, "in_progress")
        self.assertTrue(self.quiz.adaptive)

    def test_session_id_format(self):
        """Test session ID has correct format."""
        # Check UUID v4 format with qs- prefix
        self.assertTrue(self.quiz.session_id.startswith("qs-"))
        uuid_part = self.quiz.session_id[3:]
        try:
            uuid.UUID(uuid_part, version=4)
        except ValueError:
            self.fail("Session ID does not contain valid UUID v4")

    def test_teaching_session_id_integration(self):
        """Test teaching_session_id field for Phase 3→4 integration."""
        teaching_session_id = f"ts-{uuid.uuid4()}"
        quiz = AdaptiveQuiz(
            learner_id="learner-test",
            module_id="m01-test",
            teaching_session_id=teaching_session_id,
        )
        self.assertEqual(quiz.teaching_session_id, teaching_session_id)

    def test_add_question(self):
        """Test adding questions to quiz."""
        self.quiz.add_question(self.mcq_question)
        self.assertEqual(len(self.quiz.questions), 1)
        self.assertEqual(self.quiz.questions[0].question_id, self.mcq_question.question_id)

    def test_submit_mcq_answer_correct(self):
        """Test submitting correct MCQ answer."""
        self.quiz.add_question(self.mcq_question)

        response = self.quiz.submit_answer(
            question_id=self.mcq_question.question_id,
            learner_answer="B",
            time_taken_seconds=30,
        )

        self.assertTrue(response.is_correct)
        self.assertEqual(response.score, 100.0)
        self.assertEqual(response.points, 2.0)
        self.assertEqual(response.graded_by, "auto")
        self.assertEqual(response.response_status, "graded")

    def test_submit_mcq_answer_incorrect(self):
        """Test submitting incorrect MCQ answer."""
        self.quiz.add_question(self.mcq_question)

        response = self.quiz.submit_answer(
            question_id=self.mcq_question.question_id,
            learner_answer="A",
            time_taken_seconds=20,
        )

        self.assertFalse(response.is_correct)
        self.assertEqual(response.score, 0.0)
        self.assertEqual(response.graded_by, "auto")

    def test_submit_true_false_answer_correct(self):
        """Test submitting correct True/False answer."""
        self.quiz.add_question(self.tf_question)

        response = self.quiz.submit_answer(
            question_id=self.tf_question.question_id,
            learner_answer="true",
        )

        self.assertTrue(response.is_correct)
        self.assertEqual(response.score, 100.0)
        self.assertEqual(response.points, 1.0)

    def test_submit_answer_validation_empty(self):
        """Test validation fails with empty answer."""
        self.quiz.add_question(self.mcq_question)

        with self.assertRaises(ValueError) as cm:
            self.quiz.submit_answer(
                question_id=self.mcq_question.question_id,
                learner_answer="",
            )
        self.assertIn("cannot be empty", str(cm.exception))

    def test_submit_answer_validation_negative_time(self):
        """Test validation fails with negative time."""
        self.quiz.add_question(self.mcq_question)

        with self.assertRaises(ValueError) as cm:
            self.quiz.submit_answer(
                question_id=self.mcq_question.question_id,
                learner_answer="B",
                time_taken_seconds=-10,
            )
        self.assertIn("cannot be negative", str(cm.exception))

    def test_submit_answer_validation_duplicate(self):
        """Test validation fails when answering same question twice."""
        self.quiz.add_question(self.mcq_question)

        self.quiz.submit_answer(
            question_id=self.mcq_question.question_id,
            learner_answer="B",
        )

        with self.assertRaises(ValueError) as cm:
            self.quiz.submit_answer(
                question_id=self.mcq_question.question_id,
                learner_answer="C",
            )
        self.assertIn("already answered", str(cm.exception))

    def test_skip_question(self):
        """Test skipping a question."""
        self.quiz.add_question(self.mcq_question)

        response = self.quiz.skip_question(self.mcq_question.question_id)

        self.assertEqual(response.response_status, "skipped")
        self.assertIsNone(response.score)
        self.assertIsNone(response.learner_answer)
        self.assertEqual(response.points, 2.0)

    def test_adaptive_difficulty_increase(self):
        """Test difficulty increases after 2 consecutive correct answers."""
        # Start at medium
        self.assertEqual(self.quiz.current_difficulty, "medium")

        # Add and answer 2 questions correctly
        for i in range(2):
            q = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Question {i}",
                question_type="true_false",
                difficulty="medium",
                module_id="m01-test",
                correct_answer="true",
                points=1.0,
            )
            self.quiz.add_question(q)
            self.quiz.submit_answer(q.question_id, "true")

        # Should increase to hard
        self.assertEqual(self.quiz.current_difficulty, "hard")
        self.assertEqual(self.quiz.consecutive_correct, 0)  # Reset after change

    def test_adaptive_difficulty_decrease(self):
        """Test difficulty decreases after 2 consecutive incorrect answers."""
        # Start at medium
        self.assertEqual(self.quiz.current_difficulty, "medium")

        # Add and answer 2 questions incorrectly
        for i in range(2):
            q = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Question {i}",
                question_type="true_false",
                difficulty="medium",
                module_id="m01-test",
                correct_answer="true",
                points=1.0,
            )
            self.quiz.add_question(q)
            self.quiz.submit_answer(q.question_id, "false")

        # Should decrease to easy
        self.assertEqual(self.quiz.current_difficulty, "easy")
        self.assertEqual(self.quiz.consecutive_incorrect, 0)  # Reset after change

    def test_difficulty_numeric_progression(self):
        """Test numeric difficulty progression tracking."""
        # Initial difficulty = medium (0)
        self.assertIn("difficulty_numeric_progression", self.quiz._metadata)
        self.assertEqual(self.quiz._metadata["difficulty_numeric_progression"][0], 0)

        # Answer 2 correctly to increase difficulty
        for i in range(2):
            q = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Q{i}",
                question_type="true_false",
                difficulty="medium",
                module_id="m01-test",
                correct_answer="true",
                points=1.0,
            )
            self.quiz.add_question(q)
            self.quiz.submit_answer(q.question_id, "true")

        # Should now be at hard (1)
        self.assertEqual(
            self.quiz._metadata["difficulty_numeric_progression"][-1], 1
        )

    def test_points_weighted_scoring(self):
        """Test points-weighted scoring (not averaged)."""
        # Add 3 questions with different points
        q1 = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Easy question",
            question_type="true_false",
            difficulty="easy",
            module_id="m01-test",
            correct_answer="true",
            points=1.0,
        )
        q2 = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Medium question",
            question_type="true_false",
            difficulty="medium",
            module_id="m01-test",
            correct_answer="true",
            points=5.0,
        )
        q3 = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Hard question",
            question_type="true_false",
            difficulty="hard",
            module_id="m01-test",
            correct_answer="true",
            points=10.0,
        )

        self.quiz.add_question(q1)
        self.quiz.add_question(q2)
        self.quiz.add_question(q3)

        # Answer: 100% on q1 (1pt), 80% on q2 (5pt), 50% on q3 (10pt)
        # Manually set scores for testing
        r1 = self.quiz.submit_answer(q1.question_id, "true")  # 100%
        r2 = QuestionResponse(
            question_id=q2.question_id,
            question_text=q2.question_text,
            question_type=q2.question_type,
            difficulty=q2.difficulty,
            points=q2.points,
            score=80.0,
        )
        r3 = QuestionResponse(
            question_id=q3.question_id,
            question_text=q3.question_text,
            question_type=q3.question_type,
            difficulty=q3.difficulty,
            points=q3.points,
            score=50.0,
        )
        self.quiz.responses.append(r2)
        self.quiz.responses.append(r3)

        result = self.quiz.complete_quiz()

        # Points-weighted: (1*100 + 5*80 + 10*50) / (1+5+10) = 900/16 = 56.25%
        self.assertAlmostEqual(result["score"], 56.25, places=2)

    def test_complete_quiz_integrity_checks(self):
        """Test quiz completion integrity checks."""
        self.quiz.add_question(self.mcq_question)
        self.quiz.submit_answer(self.mcq_question.question_id, "B")

        result = self.quiz.complete_quiz()

        self.assertEqual(self.quiz.status, "completed")
        self.assertIsNotNone(self.quiz.completed_at)
        self.assertIsNotNone(result["score"])
        self.assertIsNotNone(result["passed"])
        self.assertIsNotNone(result["recommendations"])

    def test_complete_quiz_passed(self):
        """Test quiz completion with passing score."""
        self.quiz.add_question(self.mcq_question)
        self.quiz.submit_answer(self.mcq_question.question_id, "B")  # Correct

        result = self.quiz.complete_quiz()

        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 100.0)

    def test_complete_quiz_failed(self):
        """Test quiz completion with failing score."""
        self.quiz.add_question(self.mcq_question)
        self.quiz.submit_answer(self.mcq_question.question_id, "A")  # Incorrect

        result = self.quiz.complete_quiz()

        self.assertFalse(result["passed"])
        self.assertEqual(result["score"], 0.0)

    def test_recommendations_generation(self):
        """Test recommendations are generated on quiz completion."""
        self.quiz.add_question(self.mcq_question)
        self.quiz.submit_answer(self.mcq_question.question_id, "B")

        result = self.quiz.complete_quiz()

        recommendations = result["recommendations"]
        self.assertIn("should_review", recommendations)
        self.assertIn("next_difficulty", recommendations)
        self.assertIn("next_topic_id", recommendations)
        self.assertIn("ready_for_next_module", recommendations)

    def test_recommendations_next_topic_id(self):
        """Test next_topic_id recommendation."""
        self.quiz.add_question(self.mcq_question)
        self.quiz.submit_answer(self.mcq_question.question_id, "A")  # Incorrect

        result = self.quiz.complete_quiz()

        # Should recommend staying on current topic
        self.assertEqual(
            result["recommendations"]["next_topic_id"], self.quiz.topic_id
        )

    def test_session_reproducibility(self):
        """Test session can reproduce score from stored data only."""
        # Add questions with known points
        q1 = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Q1",
            question_type="true_false",
            difficulty="easy",
            module_id="m01-test",
            correct_answer="true",
            points=3.0,
        )
        q2 = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Q2",
            question_type="true_false",
            difficulty="easy",
            module_id="m01-test",
            correct_answer="true",
            points=7.0,
        )

        self.quiz.add_question(q1)
        self.quiz.add_question(q2)
        self.quiz.submit_answer(q1.question_id, "true")  # 100%
        self.quiz.submit_answer(q2.question_id, "false")  # 0%

        result = self.quiz.complete_quiz()

        # Manually recompute score from responses only
        responses = [r for r in self.quiz.responses if r.score is not None]
        total_points = sum(r.points for r in responses)
        obtained = sum((r.points * r.score / 100) for r in responses)
        expected_score = 100 * (obtained / total_points)

        # Should match
        self.assertAlmostEqual(result["score"], expected_score, places=2)
        # 3*100 + 7*0 = 300; 300/(3+7) = 30%
        self.assertAlmostEqual(result["score"], 30.0, places=2)

    def test_non_adaptive_quiz(self):
        """Test quiz with adaptive=False doesn't change difficulty."""
        quiz = AdaptiveQuiz(
            learner_id="learner-test",
            module_id="m01-test",
            starting_difficulty="medium",
            adaptive=False,
        )

        # Answer 2 correctly
        for i in range(2):
            q = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Q{i}",
                question_type="true_false",
                difficulty="medium",
                module_id="m01-test",
                correct_answer="true",
                points=1.0,
            )
            quiz.add_question(q)
            quiz.submit_answer(q.question_id, "true")

        # Difficulty should not change
        self.assertEqual(quiz.current_difficulty, "medium")


if __name__ == "__main__":
    unittest.main()
