"""
Unit tests for Phase 5 Syllabus Planner.

Tests multi-agent syllabus generation:
- Learner Advocate agent initialization and behavior
- Curriculum Designer agent initialization and behavior
- Negotiation protocol between agents
- Structured JSON extraction from negotiation
- Schema validation and auto-fixing
"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.agents.syllabus_planner import (
    SyllabusPlanner,
    LearnerAdvocateAgent,
    CurriculumDesignerAgent,
)
from src.models.learner_profile import LearnerModel
from langchain.schema import AIMessage


class TestLearnerAdvocateAgent(unittest.TestCase):
    """Test Learner Advocate Agent."""

    def setUp(self):
        """Set up test fixtures."""
        self.learner = LearnerModel(
            name="Test Learner",
            difficulty_preference="easy",
        )
        self.learner._data["goals"] = ["Learn Python basics", "Build simple programs"]
        self.learner._data["learning_style"] = "visual"
        self.learner._data["pace"] = "moderate"

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_initialization(self, mock_openai):
        """Test agent initialization with learner profile."""
        agent = LearnerAdvocateAgent(
            learner=self.learner,
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=5.0,
        )

        self.assertEqual(agent.learner, self.learner)
        self.assertEqual(agent.topic, "Python Programming")
        self.assertEqual(agent.duration_weeks, 4)
        self.assertEqual(agent.weekly_hours, 5.0)

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_system_prompt_includes_goals(self, mock_openai):
        """Test system prompt includes learner goals."""
        agent = LearnerAdvocateAgent(
            learner=self.learner,
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=5.0,
        )

        prompt = agent.system_message.content
        self.assertIn("Learn Python basics", prompt)
        self.assertIn("Build simple programs", prompt)
        self.assertIn("visual", prompt)
        self.assertIn("moderate", prompt)

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_get_initial_requirements(self, mock_openai):
        """Test initial requirements generation."""
        agent = LearnerAdvocateAgent(
            learner=self.learner,
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=5.0,
        )

        requirements = agent.get_initial_requirements()

        self.assertIn("Test Learner", requirements)
        self.assertIn("Python Programming", requirements)
        self.assertIn("Learn Python basics", requirements)
        self.assertIn("5.0 hours per week", requirements)
        self.assertIn("4 weeks", requirements)


class TestCurriculumDesignerAgent(unittest.TestCase):
    """Test Curriculum Designer Agent."""

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_initialization(self, mock_openai):
        """Test agent initialization."""
        agent = CurriculumDesignerAgent(topic="Python Programming")

        self.assertEqual(agent.topic, "Python Programming")

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_system_prompt_includes_topic(self, mock_openai):
        """Test system prompt includes topic."""
        agent = CurriculumDesignerAgent(topic="Python Programming")

        prompt = agent.system_message.content
        self.assertIn("Python Programming", prompt)
        self.assertIn("Curriculum Designer", prompt)

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_create_initial_proposal(self, mock_openai):
        """Test initial proposal creation."""
        agent = CurriculumDesignerAgent(topic="Python Programming")

        requirements = "Learn Python in 4 weeks, 5 hours per week"
        proposal = agent.create_initial_proposal(requirements)

        self.assertIn("Python Programming", proposal)
        self.assertIn(requirements, proposal)
        self.assertIn("m01", proposal)


class TestSyllabusPlanner(unittest.TestCase):
    """Test Syllabus Planner orchestration."""

    def setUp(self):
        """Set up test fixtures."""
        self.learner = LearnerModel(
            name="Test Learner",
            difficulty_preference="medium",
        )
        self.learner._data["goals"] = ["Learn Python"]

        self.temp_dir = tempfile.mkdtemp()

    def test_initialization(self):
        """Test planner initialization."""
        planner = SyllabusPlanner(learner=self.learner)

        self.assertEqual(planner.learner, self.learner)
        self.assertIsNotNone(planner.validator)
        self.assertEqual(planner.negotiation_history, [])

    @patch("src.agents.syllabus_planner.ChatOpenAI")
    def test_generate_syllabus_structure(self, mock_openai):
        """Test syllabus generation returns correct structure."""
        # Mock LLM responses
        mock_model = Mock()
        mock_openai.return_value = mock_model

        # Mock negotiation responses
        mock_model.return_value = AIMessage(content="APPROVED - Syllabus looks good.")

        planner = SyllabusPlanner(learner=self.learner)

        # This will use fallback since mocked responses won't create valid modules
        syllabus = planner.generate_syllabus(
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=5.0,
            max_negotiation_rounds=1,
        )

        # Check structure
        self.assertIn("meta", syllabus)
        self.assertIn("topic", syllabus)
        self.assertIn("modules", syllabus)
        self.assertIn("duration_weeks", syllabus)
        self.assertIn("weekly_time_hours", syllabus)

    def test_fallback_syllabus(self):
        """Test fallback syllabus generation."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner._create_fallback_syllabus(
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=5.0,
        )

        # Check structure
        self.assertEqual(syllabus["topic"], "Python Programming")
        self.assertEqual(syllabus["duration_weeks"], 4)
        self.assertEqual(syllabus["weekly_time_hours"], 5.0)
        self.assertGreater(len(syllabus["modules"]), 0)

        # Check module structure
        module = syllabus["modules"][0]
        self.assertIn("id", module)
        self.assertIn("title", module)
        self.assertIn("outcomes", module)
        self.assertIn("topics", module)
        self.assertIn("estimated_hours", module)

    def test_auto_fix_module_ids(self):
        """Test auto-fixing module ID patterns."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = {
            "meta": {"schema_version": 1},
            "topic": "Test",
            "duration_weeks": 4,
            "weekly_time_hours": 5.0,
            "modules": [
                {"id": "invalid-id", "title": "Module 1"},
                {"id": "01-python", "title": "Module 2"},
                {"id": "M03_Python", "title": "Module 3"},
            ],
        }

        fixed = planner._auto_fix_schema_issues(syllabus)

        # Check IDs are fixed
        self.assertTrue(fixed["modules"][0]["id"].startswith("m"))
        self.assertTrue(fixed["modules"][1]["id"].startswith("m"))
        self.assertTrue(fixed["modules"][2]["id"].startswith("m"))
        self.assertIn("-", fixed["modules"][0]["id"])

    def test_auto_fix_meta_fields(self):
        """Test auto-fixing missing meta fields."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = {
            "topic": "Test",
            "modules": [],
        }

        fixed = planner._auto_fix_schema_issues(syllabus)

        self.assertIn("meta", fixed)
        self.assertEqual(fixed["meta"]["schema_version"], 1)
        self.assertIn("created_at", fixed["meta"])
        self.assertIn("generated_by", fixed["meta"])

    def test_save_syllabus(self):
        """Test syllabus persistence."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": "2024-01-15T10:00:00Z",
            },
            "topic": "Python Programming",
            "duration_weeks": 4,
            "weekly_time_hours": 5.0,
            "modules": [],
        }

        output_dir = Path(self.temp_dir)
        filepath = planner.save_syllabus(syllabus, output_dir=output_dir)

        self.assertTrue(filepath.exists())

        # Load and verify
        with open(filepath, "r") as f:
            loaded = json.load(f)

        self.assertEqual(loaded["topic"], "Python Programming")
        self.assertEqual(loaded["duration_weeks"], 4)

    def test_extract_structured_syllabus_json_parsing(self):
        """Test JSON extraction from negotiation history."""
        planner = SyllabusPlanner(learner=self.learner)

        # Simulate negotiation history
        planner.negotiation_history = [
            {
                "role": "advocate",
                "content": "We need modules for Python basics, functions, and OOP",
            },
            {
                "role": "designer",
                "content": "I propose: m01-basics (8h), m02-functions (6h), m03-oop (10h)",
            },
        ]

        # This will likely hit fallback, but test the flow
        syllabus = planner._extract_structured_syllabus(
            negotiation_history=planner.negotiation_history,
            topic="Python Programming",
            duration_weeks=4,
            weekly_hours=6.0,
        )

        self.assertIn("modules", syllabus)
        self.assertIn("total_estimated_hours", syllabus)
        self.assertIn("workload_feasible", syllabus)

    def test_workload_feasibility_calculation(self):
        """Test workload feasibility calculation."""
        planner = SyllabusPlanner(learner=self.learner)

        # Test feasible workload
        syllabus = {
            "modules": [
                {"estimated_hours": 8.0},
                {"estimated_hours": 6.0},
                {"estimated_hours": 5.0},
            ],
        }
        total = sum(m["estimated_hours"] for m in syllabus["modules"])
        # 19 hours total, 4 weeks * 5 hours = 20 hours available, feasible

        planner.negotiation_history = []
        result = planner._extract_structured_syllabus(
            negotiation_history=[],
            topic="Test",
            duration_weeks=4,
            weekly_hours=5.0,
        )
        # Fallback will be used, check it has workload_feasible field
        self.assertIn("workload_feasible", result)

    def test_learner_profile_in_syllabus(self):
        """Test learner profile included in generated syllabus."""
        self.learner._data["goals"] = ["Master Python", "Build projects"]
        self.learner._data["learning_style"] = "kinesthetic"
        self.learner._data["pace"] = "fast"

        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner._create_fallback_syllabus(
            topic="Python Programming",
            duration_weeks=6,
            weekly_hours=8.0,
        )

        self.assertIn("learner_profile", syllabus)
        profile = syllabus["learner_profile"]
        self.assertIn("goals", profile)
        self.assertIn("preferences", profile)
        self.assertEqual(profile["preferences"]["learning_style"], "kinesthetic")
        self.assertEqual(profile["preferences"]["pacing"], "fast")

    def test_module_prerequisites(self):
        """Test prerequisite handling in generated modules."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner._create_fallback_syllabus(
            topic="Python",
            duration_weeks=4,
            weekly_hours=5.0,
        )

        # First module should have no prerequisites
        self.assertEqual(syllabus["modules"][0]["prerequisites"], [])

        # Subsequent modules should reference previous
        if len(syllabus["modules"]) > 1:
            self.assertGreater(len(syllabus["modules"][1]["prerequisites"]), 0)

    def test_prerequisite_ids_exist_and_unique(self):
        """Test prerequisite IDs reference existing modules and all IDs are unique."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner._create_fallback_syllabus(
            topic="Python Programming",
            duration_weeks=8,
            weekly_hours=6.0,
        )

        # Collect all module IDs
        module_ids = {m["id"] for m in syllabus["modules"]}

        # Check uniqueness
        self.assertEqual(len(module_ids), len(syllabus["modules"]),
                        "Module IDs should be unique")

        # Check prerequisites reference existing modules
        for module in syllabus["modules"]:
            prereqs = module.get("prerequisites", [])
            for prereq_id in prereqs:
                self.assertIn(prereq_id, module_ids,
                             f"Prerequisite {prereq_id} not found in module IDs")

    def test_prerequisite_ordering_valid(self):
        """Test prerequisites only reference earlier modules (no forward references)."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner._create_fallback_syllabus(
            topic="Data Science",
            duration_weeks=10,
            weekly_hours=8.0,
        )

        # Build index of module positions
        module_positions = {m["id"]: idx for idx, m in enumerate(syllabus["modules"])}

        # Check each module's prerequisites come before it
        for idx, module in enumerate(syllabus["modules"]):
            prereqs = module.get("prerequisites", [])
            for prereq_id in prereqs:
                prereq_position = module_positions.get(prereq_id)
                self.assertIsNotNone(prereq_position,
                                    f"Prerequisite {prereq_id} not found")
                self.assertLess(prereq_position, idx,
                               f"Module {module['id']} references forward prerequisite {prereq_id}")

    def test_no_circular_prerequisites(self):
        """Test syllabus has no circular prerequisite dependencies."""
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner._create_fallback_syllabus(
            topic="Machine Learning",
            duration_weeks=12,
            weekly_hours=10.0,
        )

        def has_cycle(module_id, visited, rec_stack, prereq_map):
            """DFS to detect cycles."""
            visited.add(module_id)
            rec_stack.add(module_id)

            for prereq in prereq_map.get(module_id, []):
                if prereq not in visited:
                    if has_cycle(prereq, visited, rec_stack, prereq_map):
                        return True
                elif prereq in rec_stack:
                    return True

            rec_stack.remove(module_id)
            return False

        # Build prerequisite map
        prereq_map = {m["id"]: m.get("prerequisites", []) for m in syllabus["modules"]}

        # Check for cycles
        visited = set()
        for module in syllabus["modules"]:
            if module["id"] not in visited:
                self.assertFalse(
                    has_cycle(module["id"], visited, set(), prereq_map),
                    f"Circular prerequisite dependency detected in syllabus"
                )


if __name__ == "__main__":
    unittest.main()
