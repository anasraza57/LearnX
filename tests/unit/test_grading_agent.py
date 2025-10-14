"""
Unit tests for Grading Agent (Phase 4).

Tests open-ended response grading, validation, and feedback generation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json

from src.agents.grading_agent import GradingAgent, GradingResult
from src.agents.assessment_generator import AssessmentQuestion


class TestGradingResult(unittest.TestCase):
    """Test GradingResult dataclass."""

    def test_grading_result_creation(self):
        """Test creating a GradingResult."""
        result = GradingResult(
            score=85.0,
            is_correct=True,
            feedback="Well done!",
            strengths=["Clear explanation", "Good examples"],
            improvements=["Could add more detail"],
            graded_by="llm",
        )
        self.assertEqual(result.score, 85.0)
        self.assertTrue(result.is_correct)
        self.assertEqual(result.graded_by, "llm")

    def test_grading_result_to_dict(self):
        """Test converting GradingResult to dictionary."""
        result = GradingResult(
            score=75.0,
            is_correct=True,
            feedback="Good work",
            strengths=["Accurate"],
            improvements=["Be more specific"],
            graded_by="llm",
        )
        result_dict = result.to_dict()
        self.assertIsInstance(result_dict, dict)
        self.assertEqual(result_dict["score"], 75.0)
        self.assertEqual(result_dict["graded_by"], "llm")


class TestGradingAgent(unittest.TestCase):
    """Test GradingAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.agent = GradingAgent(model_name="gpt-3.5-turbo", temperature=0.3)

        self.essay_question = AssessmentQuestion(
            question_id="q-test-123",
            question_text="Explain the concept of object-oriented programming.",
            question_type="essay",
            difficulty="medium",
            module_id="m01-programming",
            correct_answer="OOP is a programming paradigm based on objects containing data and methods.",
            answer_rubric="Look for: encapsulation, inheritance, polymorphism",
            points=10.0,
        )

        self.code_question = AssessmentQuestion(
            question_id="q-test-456",
            question_text="Write a function to reverse a string.",
            question_type="code",
            difficulty="easy",
            module_id="m01-python",
            correct_answer="def reverse(s): return s[::-1]",
            points=5.0,
        )

    def test_initialization(self):
        """Test agent initialization."""
        agent = GradingAgent()
        self.assertIsNotNone(agent)
        self.assertIsNotNone(agent.llm)

    def test_validation_empty_answer(self):
        """Test validation fails with empty answer."""
        with self.assertRaises(ValueError) as cm:
            self.agent.grade_response(self.essay_question, "")
        self.assertIn("cannot be empty", str(cm.exception))

    def test_validation_empty_question_text(self):
        """Test validation fails with empty question text."""
        invalid_question = AssessmentQuestion(
            question_id="q-test",
            question_text="",
            question_type="essay",
            difficulty="medium",
            module_id="m01-test",
            points=5.0,
        )
        with self.assertRaises(ValueError) as cm:
            self.agent.grade_response(invalid_question, "Some answer")
        self.assertIn("Question text cannot be empty", str(cm.exception))

    def test_validation_invalid_points(self):
        """Test validation fails with invalid points."""
        invalid_question = AssessmentQuestion(
            question_id="q-test",
            question_text="Test?",
            question_type="essay",
            difficulty="medium",
            module_id="m01-test",
            points=150.0,
        )
        with self.assertRaises(ValueError) as cm:
            self.agent.grade_response(invalid_question, "Some answer")
        self.assertIn("points must be between 0 and 100", str(cm.exception))

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_grade_essay_response(self, mock_chat):
        """Test grading an essay response."""
        # Mock LLM response
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 8,
            "is_correct": True,
            "strengths": ["Clear explanation", "Good examples"],
            "improvements": ["Could mention polymorphism"],
            "feedback": "Well done! Good understanding of OOP concepts.",
        })
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        result = self.agent.grade_response(
            self.essay_question,
            "OOP is a paradigm that uses objects with data and methods. "
            "Key concepts include encapsulation and inheritance."
        )

        self.assertIsInstance(result, GradingResult)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertEqual(result.graded_by, "llm")
        self.assertIsInstance(result.strengths, list)
        self.assertIsInstance(result.improvements, list)

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_grade_code_response(self, mock_chat):
        """Test grading a code response."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 5,
            "is_correct": True,
            "strengths": ["Correct solution", "Efficient"],
            "improvements": [],
            "feedback": "Perfect!",
            "rubric_scores": {
                "correctness": 50,
                "code_quality": 25,
                "efficiency": 15,
                "best_practices": 10,
            },
        })
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        result = self.agent.grade_response(
            self.code_question, "def reverse(s): return s[::-1]"
        )

        self.assertIsInstance(result, GradingResult)
        self.assertEqual(result.graded_by, "llm")
        self.assertIsNotNone(result.rubric_scores)

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_score_normalization(self, mock_chat):
        """Test score is normalized to 0-100 range."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        # LLM returns score of 8 out of 10 points
        mock_response.content = json.dumps({
            "score": 8,
            "is_correct": True,
            "feedback": "Good work",
            "strengths": ["Clear"],
            "improvements": [],
        })
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        result = self.agent.grade_response(self.essay_question, "Test answer")

        # 8/10 = 80%
        self.assertEqual(result.score, 80.0)

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_score_clamping(self, mock_chat):
        """Test score is clamped to [0, 100]."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        # LLM returns invalid score
        mock_response.content = json.dumps({
            "score": 15,  # Out of 10 max
            "is_correct": True,
            "feedback": "Great",
            "strengths": [],
            "improvements": [],
        })
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        # Should raise ValueError for out-of-range score
        with self.assertRaises(ValueError) as cm:
            self.agent.grade_response(self.essay_question, "Test answer")
        self.assertIn("out of valid range", str(cm.exception))

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_fallback_grading_on_parse_error(self, mock_chat):
        """Test fallback grading when LLM response is invalid."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Invalid JSON response"
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        result = self.agent.grade_response(self.essay_question, "Test answer")

        # Fallback should return 50% score
        self.assertEqual(result.score, 50.0)
        self.assertFalse(result.is_correct)
        self.assertIn("Unable to parse", result.feedback)
        self.assertEqual(result.graded_by, "llm")

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_batch_grading(self, mock_chat):
        """Test batch grading multiple responses."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 5,
            "is_correct": True,
            "feedback": "Good",
            "strengths": ["Clear"],
            "improvements": [],
        })
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        questions = [self.essay_question, self.code_question]
        answers = ["Answer 1", "Answer 2"]

        results = self.agent.batch_grade(questions, answers)

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], GradingResult)
        self.assertIsInstance(results[1], GradingResult)

    def test_batch_grading_mismatched_lengths(self):
        """Test batch grading fails with mismatched lengths."""
        questions = [self.essay_question]
        answers = ["Answer 1", "Answer 2"]

        with self.assertRaises(ValueError) as cm:
            self.agent.batch_grade(questions, answers)
        self.assertIn("must match", str(cm.exception))

    @patch("src.agents.grading_agent.ChatOpenAI")
    def test_graded_by_field_set(self, mock_chat):
        """Test that graded_by field is always set."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 7,
            "is_correct": True,
            "feedback": "Good",
            "strengths": [],
            "improvements": [],
        })
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        result = self.agent.grade_response(self.essay_question, "Test answer")

        self.assertIsNotNone(result.graded_by)
        self.assertEqual(result.graded_by, "llm")


if __name__ == "__main__":
    unittest.main()
