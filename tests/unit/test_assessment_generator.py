"""
Unit tests for Assessment Generator (Phase 4).

Tests question generation, validation, and RAG integration.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import uuid

from src.agents.assessment_generator import (
    AssessmentGenerator,
    AssessmentQuestion,
)


class TestAssessmentQuestion(unittest.TestCase):
    """Test AssessmentQuestion dataclass and validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_mcq = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=[
                {"option_id": "A", "text": "A programming language", "is_correct": True},
                {"option_id": "B", "text": "A snake", "is_correct": False},
                {"option_id": "C", "text": "A database", "is_correct": False},
            ],
            points=5.0,
        )

    def test_mcq_validation_success(self):
        """Test MCQ validation passes with valid data."""
        try:
            self.valid_mcq.validate()
        except ValueError:
            self.fail("Valid MCQ should not raise ValueError")

    def test_mcq_validation_no_options(self):
        """Test MCQ validation fails without options."""
        invalid_mcq = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=None,
            points=5.0,
        )
        with self.assertRaises(ValueError) as cm:
            invalid_mcq.validate()
        self.assertIn("at least 2 options", str(cm.exception))

    def test_mcq_validation_insufficient_options(self):
        """Test MCQ validation fails with only 1 option."""
        invalid_mcq = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=[
                {"option_id": "A", "text": "A programming language", "is_correct": True},
            ],
            points=5.0,
        )
        with self.assertRaises(ValueError) as cm:
            invalid_mcq.validate()
        self.assertIn("at least 2 options", str(cm.exception))

    def test_mcq_validation_no_correct_option(self):
        """Test MCQ validation fails without correct option."""
        invalid_mcq = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=[
                {"option_id": "A", "text": "A snake", "is_correct": False},
                {"option_id": "B", "text": "A database", "is_correct": False},
            ],
            points=5.0,
        )
        with self.assertRaises(ValueError) as cm:
            invalid_mcq.validate()
        self.assertIn("at least one correct option", str(cm.exception))

    def test_mcq_validation_invalid_option_id(self):
        """Test MCQ validation fails with invalid option_id."""
        invalid_mcq = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=[
                {"option_id": "X", "text": "A programming language", "is_correct": True},
                {"option_id": "Y", "text": "A snake", "is_correct": False},
            ],
            points=5.0,
        )
        with self.assertRaises(ValueError) as cm:
            invalid_mcq.validate()
        self.assertIn("invalid option_id", str(cm.exception))

    def test_true_false_validation_success(self):
        """Test True/False validation passes with valid data."""
        tf_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Python is a programming language",
            question_type="true_false",
            difficulty="easy",
            module_id="m01-python-basics",
            correct_answer="true",
            points=2.0,
        )
        try:
            tf_question.validate()
        except ValueError:
            self.fail("Valid True/False should not raise ValueError")

    def test_true_false_validation_invalid_answer(self):
        """Test True/False validation fails with invalid answer."""
        tf_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Python is a programming language",
            question_type="true_false",
            difficulty="easy",
            module_id="m01-python-basics",
            correct_answer="yes",
            points=2.0,
        )
        with self.assertRaises(ValueError) as cm:
            tf_question.validate()
        self.assertIn("'true' or 'false'", str(cm.exception))

    def test_points_validation_zero(self):
        """Test validation fails with zero points."""
        invalid_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Test question",
            question_type="short_answer",
            difficulty="medium",
            module_id="m01-test",
            points=0.0,
        )
        with self.assertRaises(ValueError) as cm:
            invalid_question.validate()
        self.assertIn("points must be between 0 and 100", str(cm.exception))

    def test_points_validation_exceeds_max(self):
        """Test validation fails with points > 100."""
        invalid_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Test question",
            question_type="short_answer",
            difficulty="medium",
            module_id="m01-test",
            points=150.0,
        )
        with self.assertRaises(ValueError) as cm:
            invalid_question.validate()
        self.assertIn("points must be between 0 and 100", str(cm.exception))

    def test_normalize_page_number_zero_indexed(self):
        """Test page number normalization from 0-indexed."""
        self.assertEqual(AssessmentQuestion.normalize_page_number(0, zero_indexed=True), 1)
        self.assertEqual(AssessmentQuestion.normalize_page_number(5, zero_indexed=True), 6)

    def test_normalize_page_number_one_indexed(self):
        """Test page number normalization from 1-indexed."""
        self.assertEqual(AssessmentQuestion.normalize_page_number(1, zero_indexed=False), 1)
        self.assertEqual(AssessmentQuestion.normalize_page_number(5, zero_indexed=False), 5)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = self.valid_mcq.to_dict()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["question_text"], "What is Python?")
        self.assertEqual(result["question_type"], "multiple_choice")
        self.assertEqual(result["difficulty"], "medium")
        self.assertEqual(len(result["options"]), 3)


class TestAssessmentGenerator(unittest.TestCase):
    """Test AssessmentGenerator agent."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_vector_store = Mock()
        self.generator = AssessmentGenerator(
            vector_store=self.mock_vector_store,
            model_name="gpt-3.5-turbo",
            temperature=0.7,
        )

    @patch("src.agents.assessment_generator.ChatOpenAI")
    def test_initialization(self, mock_chat):
        """Test generator initialization."""
        generator = AssessmentGenerator()
        self.assertIsNotNone(generator)
        self.assertIsNone(generator.vector_store)

    def test_suggest_bloom_level(self):
        """Test Bloom's level suggestion based on difficulty."""
        # Very easy -> remember
        self.assertEqual(
            self.generator._suggest_bloom_level("very_easy"), "remember"
        )
        # Easy -> understand
        self.assertEqual(self.generator._suggest_bloom_level("easy"), "understand")
        # Medium -> apply
        self.assertEqual(self.generator._suggest_bloom_level("medium"), "apply")
        # Hard -> analyze
        self.assertEqual(self.generator._suggest_bloom_level("hard"), "analyze")
        # Very hard -> evaluate
        self.assertEqual(
            self.generator._suggest_bloom_level("very_hard"), "evaluate"
        )

    @patch.object(AssessmentGenerator, "_generate_mcq")
    def test_generate_mcq_without_rag(self, mock_generate):
        """Test MCQ generation without RAG."""
        mock_generate.return_value = {
            "question_text": "What is Python?",
            "options": [
                {"option_id": "A", "text": "A language", "is_correct": True},
                {"option_id": "B", "text": "A snake", "is_correct": False},
            ],
            "explanation": "Python is a programming language",
        }

        question = self.generator.generate_question(
            module_id="m01-python",
            topic="Python basics",
            question_type="multiple_choice",
            difficulty="medium",
            use_rag=False,
        )

        self.assertIsInstance(question, AssessmentQuestion)
        self.assertEqual(question.question_type, "multiple_choice")
        self.assertEqual(question.difficulty, "medium")
        self.assertTrue(question.question_id.startswith("q-"))

    @patch.object(AssessmentGenerator, "_generate_mcq")
    def test_generate_mcq_with_rag(self, mock_generate):
        """Test MCQ generation with RAG context."""
        # Mock vector store response
        mock_doc = Mock()
        mock_doc.content = "Python is a high-level programming language."
        self.mock_vector_store.search.return_value = [(mock_doc, 0.9)]

        mock_generate.return_value = {
            "question_text": "What is Python?",
            "options": [
                {"option_id": "A", "text": "A language", "is_correct": True},
                {"option_id": "B", "text": "A snake", "is_correct": False},
            ],
            "explanation": "Python is a programming language",
        }

        question = self.generator.generate_question(
            module_id="m01-python",
            topic="Python basics",
            question_type="multiple_choice",
            difficulty="medium",
            use_rag=True,
        )

        # Verify RAG was called
        self.mock_vector_store.search.assert_called_once()
        self.assertIsInstance(question, AssessmentQuestion)

    def test_question_id_format(self):
        """Test that generated questions have correct ID format."""
        with patch.object(AssessmentGenerator, "_generate_mcq") as mock_gen:
            mock_gen.return_value = {
                "question_text": "Test?",
                "options": [
                    {"option_id": "A", "text": "Yes", "is_correct": True},
                    {"option_id": "B", "text": "No", "is_correct": False},
                ],
            }

            question = self.generator.generate_question(
                module_id="m01-test",
                topic="Testing",
                question_type="multiple_choice",
                use_rag=False,
            )

            # Check UUID v4 format with q- prefix
            self.assertTrue(question.question_id.startswith("q-"))
            # Verify it's a valid UUID after the prefix
            uuid_part = question.question_id[2:]
            try:
                uuid.UUID(uuid_part, version=4)
            except ValueError:
                self.fail("Question ID does not contain valid UUID v4")


if __name__ == "__main__":
    unittest.main()
