"""
Unit tests for Phase 4 Assessment Schemas.

Tests validation of assessment.schema.json and quiz_session.schema.json.
"""

import unittest
import uuid

from src.utils.validation import SchemaValidator


class TestAssessmentSchema(unittest.TestCase):
    """Test assessment.schema.json validation."""

    def setUp(self):
        """Set up schema validator."""
        self.validator = SchemaValidator("assessment")

    def test_valid_mcq_question(self):
        """Test valid MCQ question passes validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "What is Python?",
            "question_type": "multiple_choice",
            "difficulty": "medium",
            "module_id": "m01-python-basics",
            "options": [
                {"option_id": "A", "text": "A language", "is_correct": True},
                {"option_id": "B", "text": "A snake", "is_correct": False},
                {"option_id": "C", "text": "A database", "is_correct": False},
            ],
            "points": 5,
        }

        errors = self.validator.validate(question)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_valid_true_false_question(self):
        """Test valid True/False question passes validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Python is a programming language",
            "question_type": "true_false",
            "difficulty": "easy",
            "module_id": "m01-python-basics",
            "correct_answer": "true",
            "points": 2,
        }

        errors = self.validator.validate(question)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_valid_short_answer_question(self):
        """Test valid short answer question passes validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Explain inheritance in OOP",
            "question_type": "short_answer",
            "difficulty": "medium",
            "module_id": "m02-oop",
            "correct_answer": "Inheritance allows a class to inherit properties from parent",
            "answer_rubric": "Look for: parent class, child class, code reuse",
            "points": 10,
        }

        errors = self.validator.validate(question)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_invalid_question_id_format(self):
        """Test invalid question ID format fails validation."""
        question = {
            "question_id": "invalid-id-format",
            "question_text": "Test?",
            "question_type": "multiple_choice",
            "difficulty": "medium",
            "module_id": "m01-test",
            "options": [
                {"option_id": "A", "text": "Yes", "is_correct": True},
                {"option_id": "B", "text": "No", "is_correct": False},
            ],
        }

        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("question_id" in str(e) for e in errors))

    def test_missing_required_fields(self):
        """Test missing required fields fails validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Test?",
            # Missing: question_type, difficulty, module_id
        }

        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)

    def test_invalid_difficulty_level(self):
        """Test invalid difficulty level fails validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Test?",
            "question_type": "multiple_choice",
            "difficulty": "super_hard",  # Invalid
            "module_id": "m01-test",
            "options": [
                {"option_id": "A", "text": "Yes", "is_correct": True},
                {"option_id": "B", "text": "No", "is_correct": False},
            ],
        }

        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("difficulty" in str(e) for e in errors))

    def test_invalid_question_type(self):
        """Test invalid question type fails validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Test?",
            "question_type": "fill_in_blank",  # Invalid
            "difficulty": "medium",
            "module_id": "m01-test",
        }

        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("question_type" in str(e) for e in errors))

    def test_mcq_option_validation(self):
        """Test MCQ option structure validation."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Test?",
            "question_type": "multiple_choice",
            "difficulty": "medium",
            "module_id": "m01-test",
            "options": [
                {"option_id": "A", "text": "Yes", "is_correct": True},
                {"option_id": "1", "text": "No", "is_correct": False},  # Invalid ID
            ],
        }

        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("option_id" in str(e) for e in errors))

    def test_bloom_level_validation(self):
        """Test Bloom's taxonomy level validation."""
        valid_levels = ["remember", "understand", "apply", "analyze", "evaluate", "create", None]

        for level in valid_levels:
            question = {
                "question_id": f"q-{uuid.uuid4()}",
                "question_text": "Test?",
                "question_type": "short_answer",
                "difficulty": "medium",
                "module_id": "m01-test",
                "bloom_level": level,
            }
            errors = self.validator.validate(question)
            self.assertEqual(len(errors), 0, f"Level {level} should be valid")

    def test_source_material_with_uri(self):
        """Test source_material with URI field."""
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Test?",
            "question_type": "short_answer",
            "difficulty": "medium",
            "module_id": "m01-test",
            "source_material": {
                "source": "Python Textbook",
                "page": 42,
                "section": "Chapter 3",
                "uri": "file:///path/to/textbook.pdf",
            },
        }

        errors = self.validator.validate(question)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_points_validation(self):
        """Test points field validation."""
        # Valid points
        question = {
            "question_id": f"q-{uuid.uuid4()}",
            "question_text": "Test?",
            "question_type": "short_answer",
            "difficulty": "medium",
            "module_id": "m01-test",
            "points": 50,
        }
        errors = self.validator.validate(question)
        self.assertEqual(len(errors), 0)

        # Invalid: negative points
        question["points"] = -5
        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)

        # Invalid: points > 100
        question["points"] = 150
        errors = self.validator.validate(question)
        self.assertGreater(len(errors), 0)


class TestQuizSessionSchema(unittest.TestCase):
    """Test quiz_session.schema.json validation."""

    def setUp(self):
        """Set up schema validator."""
        self.validator = SchemaValidator("quiz_session")

    def test_valid_quiz_session(self):
        """Test valid quiz session passes validation."""
        session = {
            "session_id": f"qs-{uuid.uuid4()}",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-python-basics",
            "quiz_type": "formative",
            "status": "in_progress",
            "adaptive": True,
            "questions": [
                {
                    "question_id": f"q-{uuid.uuid4()}",
                    "question_text": "What is Python?",
                    "question_type": "multiple_choice",
                    "difficulty": "medium",
                    "points": 5,
                    "response_status": "answered",
                }
            ],
            "total_questions": 1,
            "answered_questions": 1,
            "passing_score": 70,
        }

        errors = self.validator.validate(session)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_invalid_session_id_format(self):
        """Test invalid session ID format fails validation."""
        session = {
            "session_id": "invalid-session-id",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-test",
            "status": "in_progress",
            "questions": [],
            "total_questions": 0,
            "answered_questions": 0,
        }

        errors = self.validator.validate(session)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("session_id" in str(e) for e in errors))

    def test_question_response_with_points(self):
        """Test question_response includes points field."""
        session = {
            "session_id": f"qs-{uuid.uuid4()}",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-test",
            "status": "completed",
            "questions": [
                {
                    "question_id": f"q-{uuid.uuid4()}",
                    "question_text": "Test?",
                    "question_type": "multiple_choice",
                    "difficulty": "medium",
                    "points": 10,  # Points field for reproducible scoring
                    "learner_answer": "A",
                    "is_correct": True,
                    "score": 100,
                    "response_status": "graded",
                    "graded_by": "auto",
                }
            ],
            "total_questions": 1,
            "answered_questions": 1,
            "score": 100,
            "passed": True,
        }

        errors = self.validator.validate(session)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_teaching_session_id_field(self):
        """Test teaching_session_id field for Phase 3→4 integration."""
        session = {
            "session_id": f"qs-{uuid.uuid4()}",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-test",
            "teaching_session_id": f"ts-{uuid.uuid4()}",  # Phase 3 reference
            "status": "in_progress",
            "questions": [],
            "total_questions": 0,
            "answered_questions": 0,
        }

        errors = self.validator.validate(session)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_invalid_teaching_session_id_format(self):
        """Test invalid teaching_session_id format fails."""
        session = {
            "session_id": f"qs-{uuid.uuid4()}",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-test",
            "teaching_session_id": "invalid-format",  # Should be ts-<uuid>
            "status": "in_progress",
            "questions": [],
            "total_questions": 0,
            "answered_questions": 0,
        }

        errors = self.validator.validate(session)
        self.assertGreater(len(errors), 0)

    def test_recommendations_with_next_topic_id(self):
        """Test recommendations include next_topic_id."""
        session = {
            "session_id": f"qs-{uuid.uuid4()}",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-test",
            "status": "completed",
            "questions": [],
            "total_questions": 0,
            "answered_questions": 0,
            "score": 85,
            "passed": True,
            "recommendations": {
                "should_review": [],
                "next_difficulty": "hard",
                "next_topic_id": "topic-002",
                "ready_for_next_module": True,
            },
        }

        errors = self.validator.validate(session)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_recommendations_next_difficulty_null(self):
        """Test next_difficulty can be null (topic-driven)."""
        session = {
            "session_id": f"qs-{uuid.uuid4()}",
            "timestamp": "2024-01-15T10:30:00Z",
            "learner_id": f"learner-{uuid.uuid4()}",
            "module_id": "m01-test",
            "status": "completed",
            "questions": [],
            "total_questions": 0,
            "answered_questions": 0,
            "score": 75,
            "passed": True,
            "recommendations": {
                "should_review": ["topic-001"],
                "next_difficulty": None,  # Can be null
                "next_topic_id": "topic-001",
                "ready_for_next_module": False,
            },
        }

        errors = self.validator.validate(session)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

    def test_graded_by_field_validation(self):
        """Test graded_by field accepts valid values."""
        valid_graders = ["auto", "llm", "human", None]

        for grader in valid_graders:
            session = {
                "session_id": f"qs-{uuid.uuid4()}",
                "timestamp": "2024-01-15T10:30:00Z",
                "learner_id": f"learner-{uuid.uuid4()}",
                "module_id": "m01-test",
                "status": "in_progress",
                "questions": [
                    {
                        "question_id": f"q-{uuid.uuid4()}",
                        "question_text": "Test?",
                        "question_type": "short_answer",
                        "difficulty": "medium",
                        "points": 5,
                        "response_status": "graded",
                        "graded_by": grader,
                    }
                ],
                "total_questions": 1,
                "answered_questions": 1,
            }
            errors = self.validator.validate(session)
            self.assertEqual(len(errors), 0, f"Grader '{grader}' should be valid")

    def test_quiz_status_validation(self):
        """Test quiz status enum validation."""
        valid_statuses = ["in_progress", "completed", "abandoned", "expired"]

        for status in valid_statuses:
            session = {
                "session_id": f"qs-{uuid.uuid4()}",
                "timestamp": "2024-01-15T10:30:00Z",
                "learner_id": f"learner-{uuid.uuid4()}",
                "module_id": "m01-test",
                "status": status,
                "questions": [],
                "total_questions": 0,
                "answered_questions": 0,
            }
            errors = self.validator.validate(session)
            self.assertEqual(len(errors), 0, f"Status '{status}' should be valid")


if __name__ == "__main__":
    unittest.main()
