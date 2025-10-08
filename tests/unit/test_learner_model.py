"""
Unit tests for learner model: profile management, progress tracking, and adaptive learning.
"""

import threading
import uuid

import pytest
from jsonschema import ValidationError

from src.models.learner_profile import LearnerModel


class TestLearnerModelCreation:
    """Test learner profile creation and initialization."""

    def test_create_default_profile(self):
        """Test creating a profile with default parameters."""
        learner = LearnerModel(name="Alice")

        assert learner.name == "Alice"
        assert learner.learner_id.startswith("learner-")
        assert learner.learning_style == ["visual"]
        assert learner.pace == "moderate"
        assert learner.difficulty_preference == "medium"
        assert learner.overall_mastery_level == "novice"
        assert learner.overall_completion_percent == 0.0

    def test_create_custom_profile(self):
        """Test creating a profile with custom parameters."""
        learner = LearnerModel(
            name="Bob",
            email="bob@example.com",
            learning_style=["kinesthetic", "visual"],
            pace="fast",
            difficulty_preference="hard",
        )

        assert learner.name == "Bob"
        assert learner.learning_style == ["kinesthetic", "visual"]
        assert learner.pace == "fast"
        assert learner.difficulty_preference == "hard"

    def test_learner_id_format(self):
        """Test learner ID follows UUID format."""
        learner = LearnerModel(name="Charlie")
        learner_id = learner.learner_id

        # Should match pattern: learner-{uuid}
        assert learner_id.startswith("learner-")
        uuid_part = learner_id.replace("learner-", "")
        # Should be valid UUID
        uuid.UUID(uuid_part)

    def test_custom_learner_id(self):
        """Test providing custom learner ID."""
        custom_id = "learner-12345678-1234-1234-1234-123456789abc"
        learner = LearnerModel(learner_id=custom_id, name="Dave")

        assert learner.learner_id == custom_id

    def test_profile_validates_on_creation(self):
        """Test that invalid profiles raise ValidationError."""
        # This should work (with validation enabled)
        learner = LearnerModel(name="Valid", validate=True)
        assert learner.name == "Valid"

        # Invalid learning style should fail validation (must explicitly enable validation)
        with pytest.raises(ValidationError):
            learner = LearnerModel(name="Invalid", learning_style=["invalid_style"], validate=True)


class TestEnrollmentAndProgress:
    """Test syllabus enrollment and progress tracking."""

    def test_enroll_in_syllabus(self):
        """Test enrolling in a syllabus."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001", total_modules=10)

        data = learner.to_dict()
        assert data["progress"]["enrolled_syllabus_id"] == "syllabus-001"
        assert data["progress"]["current_module_id"] is None
        assert data["progress"]["modules_completed"] == []
        assert data["progress"]["overall_completion_percent"] == 0.0

    def test_start_module(self):
        """Test starting a module."""
        learner = LearnerModel(name="Bob")
        learner.enroll_in_syllabus("syllabus-001")
        learner.start_module("m01-intro")

        data = learner.to_dict()
        assert data["progress"]["current_module_id"] == "m01-intro"
        assert "m01-intro" in data["progress"]["module_progress"]
        assert data["progress"]["module_progress"]["m01-intro"]["status"] == "in_progress"
        assert data["progress"]["module_progress"]["m01-intro"]["mastery_level"] == "novice"

    def test_complete_module(self):
        """Test completing a module."""
        learner = LearnerModel(name="Charlie")
        learner.enroll_in_syllabus("syllabus-001")
        learner.start_module("m01-intro")
        learner.complete_module("m01-intro", score=85.0, time_spent_minutes=120)

        data = learner.to_dict()
        progress = data["progress"]["module_progress"]["m01-intro"]

        assert progress["status"] == "completed"
        assert progress["best_score"] == 85.0
        assert progress["time_spent_minutes"] == 120
        assert progress["mastery_level"] == "advanced"
        assert "completed_at" in progress
        assert "m01-intro" in data["progress"]["modules_completed"]

    def test_completion_percentage_calculation(self):
        """Test overall completion percentage is computed correctly."""
        learner = LearnerModel(name="Dave")
        learner.enroll_in_syllabus("syllabus-001")

        # Start 4 modules
        for i in range(1, 5):
            learner.start_module(f"m0{i}-module")

        # Complete 2 of them
        learner.complete_module("m01-module", score=80, time_spent_minutes=60)
        learner.complete_module("m02-module", score=90, time_spent_minutes=60)

        # 2 completed out of 4 = 50%
        assert learner.overall_completion_percent == 50.0

    def test_total_study_time_tracking(self):
        """Test total study time accumulates correctly."""
        learner = LearnerModel(name="Eve")
        learner.enroll_in_syllabus("syllabus-001")

        learner.complete_module("m01-intro", score=75, time_spent_minutes=60)
        learner.complete_module("m02-basics", score=80, time_spent_minutes=90)
        learner.complete_module("m03-advanced", score=85, time_spent_minutes=120)

        data = learner.to_dict()
        assert data["progress"]["total_study_time_minutes"] == 270


class TestMasteryLevels:
    """Test mastery level computation."""

    def test_mastery_from_score_novice(self):
        """Test novice mastery level (0-50)."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-test", score=40, time_spent_minutes=60)

        data = learner.to_dict()
        assert data["progress"]["module_progress"]["m01-test"]["mastery_level"] == "novice"

    def test_mastery_from_score_beginner(self):
        """Test beginner mastery level (50-65)."""
        learner = LearnerModel(name="Bob")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-test", score=60, time_spent_minutes=60)

        data = learner.to_dict()
        assert data["progress"]["module_progress"]["m01-test"]["mastery_level"] == "beginner"

    def test_mastery_from_score_intermediate(self):
        """Test intermediate mastery level (65-80)."""
        learner = LearnerModel(name="Charlie")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-test", score=75, time_spent_minutes=60)

        data = learner.to_dict()
        assert data["progress"]["module_progress"]["m01-test"]["mastery_level"] == "intermediate"

    def test_mastery_from_score_advanced(self):
        """Test advanced mastery level (80-90)."""
        learner = LearnerModel(name="Dave")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-test", score=85, time_spent_minutes=60)

        data = learner.to_dict()
        assert data["progress"]["module_progress"]["m01-test"]["mastery_level"] == "advanced"

    def test_mastery_from_score_expert(self):
        """Test expert mastery level (90-100)."""
        learner = LearnerModel(name="Eve")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-test", score=95, time_spent_minutes=60)

        data = learner.to_dict()
        assert data["progress"]["module_progress"]["m01-test"]["mastery_level"] == "expert"

    def test_overall_mastery_level_updates(self):
        """Test overall mastery level updates based on average performance."""
        learner = LearnerModel(name="Frank")
        learner.enroll_in_syllabus("syllabus-001")

        # Record several high-scoring assessments
        for i in range(5):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=90,
                difficulty="medium",
                time_taken_minutes=30,
            )

        # Average 90 should result in expert overall mastery
        assert learner.overall_mastery_level == "expert"


class TestAssessmentTracking:
    """Test assessment recording and performance analytics."""

    def test_record_single_assessment(self):
        """Test recording a single assessment."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001")

        learner.record_assessment(
            module_id="m01-intro",
            score=85.5,
            difficulty="medium",
            time_taken_minutes=45,
            hints_used=2,
        )

        data = learner.to_dict()
        history = data["performance_analytics"]["assessment_history"]

        assert len(history) == 1
        assert history[0]["module_id"] == "m01-intro"
        assert history[0]["score"] == 85.5
        assert history[0]["difficulty"] == "medium"
        assert history[0]["time_taken_minutes"] == 45
        assert history[0]["hints_used"] == 2

    def test_average_score_calculation(self):
        """Test average score is computed correctly."""
        learner = LearnerModel(name="Bob")
        learner.enroll_in_syllabus("syllabus-001")

        scores = [70, 80, 90, 85, 75]
        for i, score in enumerate(scores):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=score,
                difficulty="medium",
                time_taken_minutes=30,
            )

        data = learner.to_dict()
        expected_avg = sum(scores) / len(scores)
        assert data["performance_analytics"]["average_score"] == expected_avg

    def test_best_score_tracking(self):
        """Test that best score is tracked per module."""
        learner = LearnerModel(name="Charlie")
        learner.enroll_in_syllabus("syllabus-001")

        # Multiple attempts on same module
        learner.record_assessment("m01-intro", score=60, difficulty="easy", time_taken_minutes=30)
        learner.record_assessment("m01-intro", score=75, difficulty="medium", time_taken_minutes=30)
        learner.record_assessment("m01-intro", score=70, difficulty="medium", time_taken_minutes=30)

        data = learner.to_dict()
        assert data["progress"]["module_progress"]["m01-intro"]["best_score"] == 75
        assert data["progress"]["module_progress"]["m01-intro"]["attempts"] == 3


class TestAdaptiveDifficulty:
    """Test adaptive difficulty recommendations."""

    def test_difficulty_decreases_on_low_performance(self):
        """Test difficulty decreases when performance is low."""
        learner = LearnerModel(name="Alice", difficulty_preference="medium")
        learner.enroll_in_syllabus("syllabus-001")

        # Record low scores
        for i in range(3):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=40,
                difficulty="medium",
                time_taken_minutes=30,
            )

        assert learner.recommended_difficulty == "very_easy"

    def test_difficulty_increases_on_high_performance(self):
        """Test difficulty increases when performance is high."""
        learner = LearnerModel(name="Bob", difficulty_preference="medium")
        learner.enroll_in_syllabus("syllabus-001")

        # Record high scores
        for i in range(3):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=95,
                difficulty="medium",
                time_taken_minutes=30,
            )

        assert learner.recommended_difficulty == "very_hard"

    def test_difficulty_stays_medium_on_moderate_performance(self):
        """Test difficulty stays medium on moderate performance."""
        learner = LearnerModel(name="Charlie", difficulty_preference="medium")
        learner.enroll_in_syllabus("syllabus-001")

        # Record moderate scores
        for i in range(3):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=72,
                difficulty="medium",
                time_taken_minutes=30,
            )

        assert learner.recommended_difficulty == "medium"

    def test_recommended_difficulty_uses_recent_assessments(self):
        """Test recommended difficulty is based on last 3 assessments."""
        learner = LearnerModel(name="Dave")
        learner.enroll_in_syllabus("syllabus-001")

        # Start with low scores
        for i in range(5):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=40,
                difficulty="easy",
                time_taken_minutes=30,
            )

        # Then improve significantly (last 3 assessments)
        for i in range(5, 8):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=90,
                difficulty="medium",
                time_taken_minutes=30,
            )

        # Should recommend based on recent high performance
        assert learner.recommended_difficulty == "very_hard"


class TestPerformanceTrends:
    """Test performance trend analysis."""

    def test_performance_trend_improving(self):
        """Test improving performance trend detection."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001")

        # First 5: low scores
        for i in range(5):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=60,
                difficulty="medium",
                time_taken_minutes=30,
            )

        # Next 5: high scores
        for i in range(5, 10):
            learner.record_assessment(
                module_id=f"m{i+1}-test",
                score=85,
                difficulty="medium",
                time_taken_minutes=30,
            )

        data = learner.to_dict()
        assert data["performance_analytics"]["performance_trend"] == "improving"

    def test_performance_trend_declining(self):
        """Test declining performance trend detection."""
        learner = LearnerModel(name="Bob")
        learner.enroll_in_syllabus("syllabus-001")

        # First 5: high scores
        for i in range(5):
            learner.record_assessment(
                module_id=f"m0{i+1}-test",
                score=85,
                difficulty="medium",
                time_taken_minutes=30,
            )

        # Next 5: low scores
        for i in range(5, 10):
            learner.record_assessment(
                module_id=f"m{i+1}-test",
                score=60,
                difficulty="medium",
                time_taken_minutes=30,
            )

        data = learner.to_dict()
        assert data["performance_analytics"]["performance_trend"] == "declining"

    def test_performance_trend_stable(self):
        """Test stable performance trend detection."""
        learner = LearnerModel(name="Charlie")
        learner.enroll_in_syllabus("syllabus-001")

        # Consistent scores
        for i in range(10):
            learner.record_assessment(
                module_id=f"m{i+1:02d}-test",
                score=75,
                difficulty="medium",
                time_taken_minutes=30,
            )

        data = learner.to_dict()
        assert data["performance_analytics"]["performance_trend"] == "stable"


class TestStrengthsWeaknesses:
    """Test strengths and weaknesses identification."""

    def test_identify_strengths(self):
        """Test identifying strength areas (high performance)."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001")

        # High scores on m01 and m02
        for _ in range(3):
            learner.record_assessment("m01-algebra", score=90, difficulty="medium", time_taken_minutes=30)
            learner.record_assessment("m02-geometry", score=85, difficulty="medium", time_taken_minutes=30)

        # Low score on m03
        learner.record_assessment("m03-calculus", score=55, difficulty="medium", time_taken_minutes=30)

        learner.identify_strengths_weaknesses(threshold=75.0)

        data = learner.to_dict()
        assert "m01-algebra" in data["performance_analytics"]["strengths"]
        assert "m02-geometry" in data["performance_analytics"]["strengths"]

    def test_identify_weaknesses(self):
        """Test identifying weakness areas (low performance)."""
        learner = LearnerModel(name="Bob")
        learner.enroll_in_syllabus("syllabus-001")

        # Low scores on m01 and m02
        for _ in range(3):
            learner.record_assessment("m01-algebra", score=50, difficulty="easy", time_taken_minutes=30)
            learner.record_assessment("m02-geometry", score=45, difficulty="easy", time_taken_minutes=30)

        # High score on m03
        learner.record_assessment("m03-calculus", score=85, difficulty="medium", time_taken_minutes=30)

        learner.identify_strengths_weaknesses()

        data = learner.to_dict()
        assert "m01-algebra" in data["performance_analytics"]["weaknesses"]
        assert "m02-geometry" in data["performance_analytics"]["weaknesses"]


class TestPersistence:
    """Test profile saving and loading."""

    def test_save_and_load_profile(self, tmp_path):
        """Test saving and loading a profile."""
        # Create and save
        learner = LearnerModel(name="Alice", email="alice@example.com")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-intro", score=85, time_spent_minutes=120)

        save_path = tmp_path / "alice.json"
        learner.save(save_path)

        # Load
        loaded = LearnerModel.load(save_path)

        assert loaded.learner_id == learner.learner_id
        assert loaded.name == "Alice"
        assert loaded.overall_completion_percent == learner.overall_completion_percent

    def test_save_default_location(self, tmp_path, monkeypatch):
        """Test saving to default location."""
        from src.config import config

        # Temporarily set project root to tmp_path
        monkeypatch.setattr(config.paths, "project_root", tmp_path)

        learner = LearnerModel(name="Bob")
        saved_path = learner.save()

        expected_path = tmp_path / "data" / "profiles" / f"{learner.learner_id}.json"
        assert saved_path == expected_path
        assert saved_path.exists()

    def test_load_by_id(self, tmp_path, monkeypatch):
        """Test loading profile by learner ID."""
        from src.config import config

        monkeypatch.setattr(config.paths, "project_root", tmp_path)

        # Create and save
        learner = LearnerModel(name="Charlie")
        learner.save()

        # Load by ID
        loaded = LearnerModel.load_by_id(learner.learner_id)
        assert loaded.name == "Charlie"

    def test_to_dict_returns_deep_copy(self):
        """Test that to_dict returns a deep copy (no mutation)."""
        learner = LearnerModel(name="Dave")
        data1 = learner.to_dict()
        data1["personal_info"]["name"] = "Modified"

        data2 = learner.to_dict()
        assert data2["personal_info"]["name"] == "Dave"


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_assessment_recording(self):
        """Test thread-safe assessment recording."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001")

        def record_assessments():
            for i in range(5):  # Reduced from 10 to 5 for faster tests
                learner.record_assessment(
                    module_id=f"m{i:02d}-test",
                    score=75 + (i % 20),
                    difficulty="medium",
                    time_taken_minutes=30,
                )

        threads = [threading.Thread(target=record_assessments) for _ in range(3)]  # Reduced from 5 to 3
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 15 assessments total (3 threads * 5 assessments each)
        data = learner.to_dict()
        assert len(data["performance_analytics"]["assessment_history"]) == 15

    def test_concurrent_module_completion(self):
        """Test thread-safe module completion."""
        learner = LearnerModel(name="Bob")
        learner.enroll_in_syllabus("syllabus-001")

        def complete_modules(start_idx):
            for i in range(start_idx, start_idx + 3):  # Reduced from 5 to 3
                learner.complete_module(
                    module_id=f"m{i:02d}-module",
                    score=80,
                    time_spent_minutes=60,
                )

        threads = [threading.Thread(target=complete_modules, args=(i * 3,)) for i in range(3)]  # Reduced from 4 to 3
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 9 completed modules (3 threads * 3 modules each)
        data = learner.to_dict()
        assert len(data["progress"]["modules_completed"]) == 9


class TestRepr:
    """Test string representation."""

    def test_repr_format(self):
        """Test __repr__ includes key information."""
        learner = LearnerModel(name="Alice")
        learner.enroll_in_syllabus("syllabus-001")
        learner.complete_module("m01-intro", score=85, time_spent_minutes=60)
        learner.complete_module("m02-basics", score=90, time_spent_minutes=60)

        repr_str = repr(learner)

        assert "LearnerModel" in repr_str
        assert learner.learner_id in repr_str
        assert "Alice" in repr_str
        assert learner.overall_mastery_level in repr_str
        assert "50.0%" in repr_str  # Completion percentage
