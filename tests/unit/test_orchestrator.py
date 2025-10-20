"""
Unit tests for Phase 5 Learning Orchestrator.

Tests the complete learning pipeline orchestration including:
- Syllabus generation integration
- Learner enrollment
- Teaching session management
- Assessment orchestration
- Mastery-based pathway adaptation
- Session persistence
"""

import unittest
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.orchestrator import LearningOrchestrator
from src.models.learner_profile import LearnerModel
from src.agents.assessment_generator import AssessmentQuestion


class TestLearningOrchestrator(unittest.TestCase):
    """Test LearningOrchestrator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.persist_dir = Path(self.temp_dir)

        # Create test learner
        self.learner = LearnerModel(
            name="Test Learner",
            difficulty_preference="medium",
        )
        self.learner._data["goals"] = ["Learn Python"]

        # Create test syllabus
        self.syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": "2024-01-15T10:00:00Z",
                "generated_by": "EduGPT-Test",
            },
            "topic": "Python Programming",
            "duration_weeks": 4,
            "weekly_time_hours": 5.0,
            "modules": [
                {
                    "id": "m01-python-basics",
                    "title": "Python Basics",
                    "difficulty": "easy",
                    "outcomes": ["Understand Python syntax"],
                    "topics": ["Variables", "Data Types", "Control Flow"],
                    "estimated_hours": 8.0,
                },
                {
                    "id": "m02-functions",
                    "title": "Functions",
                    "difficulty": "medium",
                    "outcomes": ["Write functions"],
                    "topics": ["Function definition", "Parameters", "Return values"],
                    "estimated_hours": 6.0,
                },
            ],
        }

        self.orchestrator = LearningOrchestrator(
            learner=self.learner,
            syllabus=self.syllabus,
            persist_dir=self.persist_dir,
        )

    def test_initialization(self):
        """Test orchestrator initialization."""
        self.assertIsNotNone(self.orchestrator)
        self.assertEqual(self.orchestrator.learner, self.learner)
        self.assertEqual(self.orchestrator.syllabus, self.syllabus)
        self.assertTrue(self.orchestrator.persist_dir.exists())

    def test_enroll_learner(self):
        """Test learner enrollment in module."""
        result = self.orchestrator.enroll_learner("m01-python-basics")

        self.assertEqual(result["module_id"], "m01-python-basics")
        self.assertEqual(result["title"], "Python Basics")
        self.assertTrue(result["enrolled"])
        self.assertEqual(result["learner_id"], self.learner.learner_id)
        self.assertEqual(self.orchestrator.current_module_id, "m01-python-basics")

    def test_enroll_invalid_module(self):
        """Test enrollment with invalid module ID."""
        with self.assertRaises(ValueError):
            self.orchestrator.enroll_learner("m99-nonexistent")

    def test_enroll_without_syllabus(self):
        """Test enrollment fails without syllabus."""
        orchestrator = LearningOrchestrator(
            learner=self.learner,
            syllabus=None,
            persist_dir=self.persist_dir,
        )

        with self.assertRaises(ValueError):
            orchestrator.enroll_learner("m01-python-basics")

    def test_start_teaching_session(self):
        """Test teaching session initialization."""
        self.orchestrator.enroll_learner("m01-python-basics")

        result = self.orchestrator.start_teaching_session(
            module_id="m01-python-basics",
            load_documents=False,
        )

        self.assertIn("teaching_session_id", result)
        self.assertEqual(result["module_id"], "m01-python-basics")
        self.assertEqual(result["status"], "active")
        self.assertFalse(result["rag_enabled"])

    def test_start_teaching_session_without_module(self):
        """Test teaching session requires module."""
        with self.assertRaises(ValueError):
            self.orchestrator.start_teaching_session(
                module_id=None,
                load_documents=False,
            )

    @patch("src.orchestrator.RAGInstructor")
    def test_teach_requires_session(self, mock_instructor):
        """Test teach method requires active session."""
        with self.assertRaises(ValueError):
            self.orchestrator.teach("What is Python?")

    def test_start_assessment(self):
        """Test assessment session initialization."""
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)

        result = self.orchestrator.start_assessment(
            module_id="m01-python-basics",
            num_questions=5,
            difficulty="medium",
            adaptive=True,
        )

        self.assertIn("quiz_session_id", result)
        self.assertEqual(result["module_id"], "m01-python-basics")
        self.assertEqual(result["num_questions"], 5)
        self.assertTrue(result["adaptive"])
        self.assertEqual(result["starting_difficulty"], "medium")
        self.assertIsNotNone(self.orchestrator.current_quiz_session)

    def test_start_assessment_without_module(self):
        """Test assessment requires module."""
        with self.assertRaises(ValueError):
            self.orchestrator.start_assessment(
                module_id=None,
                num_questions=5,
            )

    @patch("src.orchestrator.AssessmentGenerator")
    def test_generate_question(self, mock_generator_class):
        """Test question generation."""
        # Set up mocks
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator

        test_question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is a variable?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=[
                {"option_id": "A", "text": "Storage", "is_correct": True},
                {"option_id": "B", "text": "Function", "is_correct": False},
            ],
        )
        mock_generator.generate_question.return_value = test_question

        # Start assessment
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.assessment_generator = mock_generator
        self.orchestrator.start_assessment(num_questions=5)

        # Generate question
        question = self.orchestrator.generate_question(
            topic="Variables",
            question_type="multiple_choice",
        )

        self.assertIsNotNone(question)
        self.assertEqual(question.question_text, "What is a variable?")

    def test_submit_answer(self):
        """Test answer submission and grading."""
        # Set up assessment
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.start_assessment(num_questions=3)

        # Create and add a question
        question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="easy",
            module_id="m01-python-basics",
            options=[
                {"option_id": "A", "text": "A language", "is_correct": True},
                {"option_id": "B", "text": "A snake", "is_correct": False},
            ],
        )
        question.validate()
        self.orchestrator.current_quiz_session.add_question(question)

        # Submit correct answer
        result = self.orchestrator.submit_answer(
            question_id=question.question_id,
            answer="A",
            time_taken_seconds=30,
        )

        self.assertIsNotNone(result)
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["score"], 100)

    def test_complete_assessment(self):
        """Test assessment completion."""
        # Set up and complete assessment
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.start_assessment(num_questions=2)

        # Add questions and answers
        for i in range(2):
            question = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Question {i+1}?",
                question_type="multiple_choice",
                difficulty="medium",
                module_id="m01-python-basics",
                options=[
                    {"option_id": "A", "text": "Correct", "is_correct": True},
                    {"option_id": "B", "text": "Wrong", "is_correct": False},
                ],
                points=10,
            )
            question.validate()
            self.orchestrator.current_quiz_session.add_question(question)
            self.orchestrator.submit_answer(question.question_id, "A")

        # Complete assessment
        result = self.orchestrator.complete_assessment()

        self.assertIn("score", result)
        self.assertIn("passed", result)
        self.assertEqual(len(self.orchestrator.session_history), 1)

    def test_adapt_pathway_no_assessments(self):
        """Test pathway adaptation with no assessments."""
        # Enroll learner in a module first
        self.orchestrator.enroll_learner("m01-python-basics")

        result = self.orchestrator.adapt_pathway()

        self.assertEqual(result["action"], "assess")
        self.assertIn("No assessments yet", result["message"])

    def test_adapt_pathway_high_mastery(self):
        """Test pathway adaptation recommends advance for high mastery."""
        # Set up completed assessment with high score
        self.orchestrator.enroll_learner("m01-python-basics")
        self.learner.record_quiz_result(
            quiz_session_id=f"qs-{uuid.uuid4()}",
            module_id="m01-python-basics",
            score=90,
            difficulty="medium",
            num_questions=5,
            time_taken_minutes=10,
            passed=True,
        )

        # Manually set high mastery score in module progress
        self.learner._data["progress"]["module_progress"]["m01-python-basics"]["best_score"] = 85.0

        result = self.orchestrator.adapt_pathway()

        self.assertEqual(result["action"], "advance")
        self.assertGreaterEqual(result["current_mastery"], 0.75)

    def test_adapt_pathway_low_mastery(self):
        """Test pathway adaptation recommends review for low mastery."""
        # Set up completed assessment with low score
        self.orchestrator.enroll_learner("m01-python-basics")
        self.learner.record_quiz_result(
            quiz_session_id=f"qs-{uuid.uuid4()}",
            module_id="m01-python-basics",
            score=55,
            difficulty="medium",
            num_questions=5,
            time_taken_minutes=10,
            passed=False,
        )

        result = self.orchestrator.adapt_pathway()

        self.assertEqual(result["action"], "review")
        self.assertLess(result["current_mastery"], 0.60)

    def test_save_and_load_state(self):
        """Test state persistence."""
        # Set up some state
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.session_history.append({
            "type": "teaching",
            "timestamp": "2024-01-15T10:00:00Z",
        })

        # Save state
        filepath = self.orchestrator.save_state()
        self.assertTrue(filepath.exists())

        # Load state into new orchestrator
        new_orchestrator = LearningOrchestrator(
            learner=self.learner,
            syllabus=self.syllabus,
            persist_dir=self.persist_dir,
        )
        new_orchestrator.load_state(filepath)

        self.assertEqual(new_orchestrator.current_module_id, "m01-python-basics")
        self.assertEqual(len(new_orchestrator.session_history), 1)

    def test_get_learner_summary(self):
        """Test learner summary generation."""
        self.orchestrator.enroll_learner("m01-python-basics")

        summary = self.orchestrator.get_learner_summary()

        self.assertEqual(summary["learner_id"], self.learner.learner_id)
        self.assertEqual(summary["name"], self.learner.name)
        self.assertIn("overall_gpa", summary)
        self.assertIn("mastery_levels", summary)
        self.assertIn("total_assessments", summary)

    def test_get_next_module(self):
        """Test getting next module from syllabus."""
        next_module = self.orchestrator._get_next_module("m01-python-basics")
        self.assertEqual(next_module, "m02-functions")

        # Test last module returns None
        last_module = self.orchestrator._get_next_module("m02-functions")
        self.assertIsNone(last_module)

    def test_find_module(self):
        """Test finding module in syllabus."""
        module = self.orchestrator._find_module("m01-python-basics")
        self.assertIsNotNone(module)
        self.assertEqual(module["title"], "Python Basics")

        # Test non-existent module
        module = self.orchestrator._find_module("m99-nonexistent")
        self.assertIsNone(module)

    @patch("src.agents.syllabus_planner.SyllabusPlanner")
    def test_generate_syllabus(self, mock_planner_class):
        """Test syllabus generation integration."""
        mock_planner = Mock()
        mock_planner_class.return_value = mock_planner
        mock_planner.generate_syllabus.return_value = self.syllabus
        mock_planner.save_syllabus.return_value = Path("test_syllabus.json")

        orchestrator = LearningOrchestrator(
            learner=self.learner,
            persist_dir=self.persist_dir,
        )

        syllabus = orchestrator.generate_syllabus(
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=5.0,
        )

        self.assertEqual(syllabus, self.syllabus)
        self.assertEqual(orchestrator.syllabus, self.syllabus)
        mock_planner.generate_syllabus.assert_called_once()

    # ==================== SessionState Tests ====================

    def test_session_state_created_on_enrollment(self):
        """Test SessionState is created when learner enrolls."""
        result = self.orchestrator.enroll_learner("m01-python-basics")

        self.assertIsNotNone(self.orchestrator.session_state)
        self.assertEqual(self.orchestrator.session_state.learner_id, self.learner.learner_id)
        self.assertEqual(self.orchestrator.session_state.module_id, "m01-python-basics")
        self.assertEqual(self.orchestrator.session_state.topic_cursor, 0)
        self.assertEqual(self.orchestrator.session_state.difficulty_hint, 0)
        self.assertFalse(self.orchestrator.session_state.completed)

    def test_session_state_persistence_atomic(self):
        """Test SessionState is saved atomically."""
        from src.orchestrator import SESSION_DIR

        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.session_state.difficulty_hint = -1
        self.orchestrator.session_state.history.append({"test": "event"})

        # Save state
        self.orchestrator._save_session_state()

        # Verify file exists
        session_dir = Path(SESSION_DIR)
        filepath = session_dir / f"{self.learner.learner_id}_session.json"
        self.assertTrue(filepath.exists())

        # Verify no temp file left behind
        temp_file = filepath.with_suffix(".json.tmp")
        self.assertFalse(temp_file.exists())

        # Load and verify
        loaded = self.orchestrator._load_session_state(self.learner.learner_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.difficulty_hint, -1)
        self.assertEqual(len(loaded.history), 1)

    def test_advance_cursor_increments_and_completes(self):
        """Test _advance_cursor increments cursor and marks completion."""
        from src.orchestrator import SessionState

        module = self.syllabus["modules"][0]
        state = SessionState(
            session_id="test-sess",
            learner_id=self.learner.learner_id,
            module_id="m01-python-basics",
            topic_cursor=0,
            difficulty_hint=0,
            history=[],
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Advance within module
        state = self.orchestrator._advance_cursor(state, module)
        self.assertEqual(state.topic_cursor, 1)
        self.assertFalse(state.completed)

        # Advance to end (module has 3 topics)
        state.topic_cursor = 2
        state = self.orchestrator._advance_cursor(state, module)
        self.assertEqual(state.topic_cursor, 3)
        self.assertTrue(state.completed)

    def test_apply_remediation_lowers_difficulty(self):
        """Test _apply_remediation decreases difficulty_hint."""
        from src.orchestrator import SessionState, MIN_DIFFICULTY

        state = SessionState(
            session_id="test-sess",
            learner_id=self.learner.learner_id,
            module_id="m01-python-basics",
            topic_cursor=0,
            difficulty_hint=1,
            history=[],
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Apply remediation
        state = self.orchestrator._apply_remediation(state)
        self.assertEqual(state.difficulty_hint, 0)

        # Apply again
        state = self.orchestrator._apply_remediation(state)
        self.assertEqual(state.difficulty_hint, -1)

        # Test floor
        state.difficulty_hint = MIN_DIFFICULTY
        state = self.orchestrator._apply_remediation(state)
        self.assertEqual(state.difficulty_hint, MIN_DIFFICULTY)

    def test_difficulty_hint_maps_to_assessment_difficulty(self):
        """Test difficulty_hint is mapped to assessment difficulty string."""
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)

        # Set difficulty hint to -2 (should map to "easy")
        self.orchestrator.session_state.difficulty_hint = -2

        result = self.orchestrator.start_assessment(num_questions=3)

        # Verify quiz was created with easy difficulty
        self.assertEqual(self.orchestrator.current_quiz_session.starting_difficulty, "easy")

    def test_complete_assessment_creates_session_event(self):
        """Test completing assessment creates SessionEvent in history."""
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.start_assessment(num_questions=2)

        # Add questions and answers
        for i in range(2):
            question = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Question {i+1}?",
                question_type="multiple_choice",
                difficulty="medium",
                module_id="m01-python-basics",
                options=[
                    {"option_id": "A", "text": "Correct", "is_correct": True},
                    {"option_id": "B", "text": "Wrong", "is_correct": False},
                ],
                points=10,
            )
            question.validate()
            self.orchestrator.current_quiz_session.add_question(question)
            self.orchestrator.submit_answer(question.question_id, "A")

        # Complete assessment
        result = self.orchestrator.complete_assessment()

        # Verify SessionEvent was created
        self.assertIsNotNone(self.orchestrator.session_state)
        self.assertEqual(len(self.orchestrator.session_state.history), 1)

        event = self.orchestrator.session_state.history[0]
        self.assertIn("score", event)
        self.assertIn("mastery_delta", event)
        self.assertIn("difficulty_hint", event)
        self.assertIn("started_at", event)
        self.assertIn("ended_at", event)

    def test_citations_tracked_in_session_event(self):
        """Test citations from teaching are included in SessionEvent."""
        from src.agents.rag_instructor import Citation, TeachingResponse

        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.start_teaching_session(load_documents=False)

        # Mock instructor to return citations
        mock_response = TeachingResponse(
            answer="Python is a programming language.",
            citations=[
                Citation(source="python_docs.pdf", page=1, content="Python overview", relevance_score=0.9),
                Citation(source="tutorial.pdf", page=5, content="Introduction", relevance_score=0.8),
            ],
            retrieved_docs=[],
            confidence=0.9,
        )
        self.orchestrator.instructor = Mock()
        self.orchestrator.instructor.teach = Mock(return_value=mock_response)

        # Teach and capture citations
        self.orchestrator.teach("What is Python?")

        # Start assessment
        self.orchestrator.start_assessment(num_questions=1)

        # Add and answer question
        question = AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is Python?",
            question_type="multiple_choice",
            difficulty="medium",
            module_id="m01-python-basics",
            options=[
                {"option_id": "A", "text": "A language", "is_correct": True},
                {"option_id": "B", "text": "A snake", "is_correct": False},
            ],
            points=10,
        )
        question.validate()
        self.orchestrator.current_quiz_session.add_question(question)
        self.orchestrator.submit_answer(question.question_id, "A")

        # Complete assessment
        self.orchestrator.complete_assessment()

        # Verify citations in SessionEvent
        event = self.orchestrator.session_state.history[0]
        self.assertIn("cited_sources", event)
        self.assertEqual(len(event["cited_sources"]), 2)
        self.assertIn("python_docs.pdf", event["cited_sources"][0])

    def test_happy_path_end_to_end(self):
        """Test complete learning cycle: enroll → teach → assess → pass → advance."""
        from src.agents.rag_instructor import TeachingResponse
        from src.orchestrator import PASS_THRESHOLD

        # 1. Enroll
        self.orchestrator.enroll_learner("m01-python-basics")
        self.assertEqual(self.orchestrator.session_state.topic_cursor, 0)

        # 2. Teach
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.instructor = Mock()
        self.orchestrator.instructor.teach = Mock(return_value=TeachingResponse(
            answer="Python is great", citations=[], retrieved_docs=[], confidence=0.9
        ))
        self.orchestrator.teach("What is Python?")

        # 3. Assess
        self.orchestrator.start_assessment(num_questions=2)

        for i in range(2):
            question = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Question {i+1}?",
                question_type="multiple_choice",
                difficulty="medium",
                module_id="m01-python-basics",
                options=[
                    {"option_id": "A", "text": "Correct", "is_correct": True},
                    {"option_id": "B", "text": "Wrong", "is_correct": False},
                ],
                points=10,
            )
            question.validate()
            self.orchestrator.current_quiz_session.add_question(question)
            self.orchestrator.submit_answer(question.question_id, "A")

        # 4. Complete (should pass and advance)
        result = self.orchestrator.complete_assessment()

        self.assertTrue(result["passed"])
        self.assertGreaterEqual(result["score"], PASS_THRESHOLD * 100)

        # Verify cursor advanced
        self.assertEqual(self.orchestrator.session_state.topic_cursor, 1)

    def test_remedial_cycle_fail_remediate_retry(self):
        """Test remedial path: fail → remediate → lower difficulty → retry."""
        from src.agents.rag_instructor import TeachingResponse

        # 1. Enroll
        self.orchestrator.enroll_learner("m01-python-basics")
        initial_hint = self.orchestrator.session_state.difficulty_hint

        # 2. Teach
        self.orchestrator.start_teaching_session(load_documents=False)
        self.orchestrator.instructor = Mock()
        self.orchestrator.instructor.teach = Mock(return_value=TeachingResponse(
            answer="Content", citations=[], retrieved_docs=[], confidence=0.9
        ))
        self.orchestrator.teach("Question")

        # 3. Assess and fail
        self.orchestrator.start_assessment(num_questions=2)

        for i in range(2):
            question = AssessmentQuestion(
                question_id=f"q-{uuid.uuid4()}",
                question_text=f"Question {i+1}?",
                question_type="multiple_choice",
                difficulty="medium",
                module_id="m01-python-basics",
                options=[
                    {"option_id": "A", "text": "Correct", "is_correct": True},
                    {"option_id": "B", "text": "Wrong", "is_correct": False},
                ],
                points=10,
            )
            question.validate()
            self.orchestrator.current_quiz_session.add_question(question)
            # Give wrong answer
            self.orchestrator.submit_answer(question.question_id, "B")

        # Complete assessment (should fail and remediate)
        result = self.orchestrator.complete_assessment()

        self.assertFalse(result["passed"])

        # Verify remediation applied
        self.assertEqual(self.orchestrator.session_state.difficulty_hint, initial_hint - 1)
        self.assertEqual(self.orchestrator.session_state.topic_cursor, 0)  # Cursor unchanged

    def test_resume_session_from_saved_state(self):
        """Test loading saved SessionState and continuing."""
        from src.orchestrator import SESSION_DIR

        # Create initial session
        self.orchestrator.enroll_learner("m01-python-basics")
        self.orchestrator.session_state.topic_cursor = 2
        self.orchestrator.session_state.difficulty_hint = -1
        self.orchestrator.session_state.history = [{"test": "event1"}, {"test": "event2"}]

        # Save
        self.orchestrator._save_session_state()
        saved_session_id = self.orchestrator.session_state.session_id

        # Create new orchestrator
        new_orch = LearningOrchestrator(
            learner=self.learner,
            syllabus=self.syllabus,
            persist_dir=self.persist_dir,
        )

        # Load state
        loaded_state = new_orch._load_session_state(self.learner.learner_id)
        self.assertIsNotNone(loaded_state)

        # Verify state restored
        self.assertEqual(loaded_state.session_id, saved_session_id)
        self.assertEqual(loaded_state.topic_cursor, 2)
        self.assertEqual(loaded_state.difficulty_hint, -1)
        self.assertEqual(len(loaded_state.history), 2)

        # Continue session
        new_orch.session_state = loaded_state
        new_orch.current_module_id = loaded_state.module_id

        # Should be able to continue from where left off
        self.assertEqual(new_orch.session_state.topic_cursor, 2)


if __name__ == "__main__":
    unittest.main()
