"""
Unit tests for learner profile validation.

Tests:
- JSON Schema validation for learner profiles
- Completion percentage consistency
- Module progress consistency
- Assessment history validation
"""

import pytest
from datetime import datetime, timezone

from src.utils.validation import (
    LearnerProfileValidator,
    validate_learner_profile,
    ValidationResult,
)


@pytest.fixture
def valid_profile():
    """Fixture providing a valid learner profile."""
    return {
        "meta": {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        "learner_id": "learner-12345678-1234-1234-1234-123456789abc",
        "personal_info": {
            "name": "Test Learner",
        },
        "cognitive_profile": {
            "learning_style": ["visual"],
            "pace": "moderate",
        },
        "learning_preferences": {
            "difficulty_preference": "medium",
        },
        "progress": {
            "enrolled_syllabus_id": "test-syllabus",
            "current_module_id": "m01-intro",
            "modules_completed": [],
            "overall_completion_percent": 0.0,
            "module_progress": {
                "m01-intro": {
                    "status": "in_progress",
                    "mastery_level": "novice",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "time_spent_minutes": 0,
                    "attempts": 0,
                    "best_score": 0.0,
                }
            },
            "learning_streak_days": 0,
            "total_study_time_minutes": 0,
        },
        "performance_analytics": {
            "overall_mastery_level": "novice",
            "average_score": 0.0,
            "strengths": [],
            "weaknesses": [],
            "recommended_difficulty": "medium",
            "performance_trend": "stable",
            "assessment_history": [],
        },
    }


class TestLearnerProfileValidator:
    """Test suite for LearnerProfileValidator."""

    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        validator = LearnerProfileValidator()
        assert validator.schema is not None
        assert validator.validator is not None

    def test_valid_profile(self, valid_profile):
        """Test validation of a valid learner profile."""
        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert result.valid
        assert len(result.errors) == 0

    def test_missing_required_field(self, valid_profile):
        """Test validation fails when required field is missing."""
        del valid_profile["learner_id"]

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        assert any("learner_id" in error.lower() for error in result.errors)

    def test_invalid_learner_id_format(self, valid_profile):
        """Test validation fails for invalid learner ID format."""
        valid_profile["learner_id"] = "invalid-id"

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        assert any("learner_id" in error.lower() or "pattern" in error.lower() for error in result.errors)

    def test_invalid_learning_style(self, valid_profile):
        """Test validation fails for invalid learning style."""
        valid_profile["cognitive_profile"]["learning_style"] = ["invalid_style"]

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid

    def test_invalid_mastery_level(self, valid_profile):
        """Test validation fails for invalid mastery level."""
        valid_profile["performance_analytics"]["overall_mastery_level"] = "super_expert"

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid

    def test_score_out_of_range(self, valid_profile):
        """Test validation fails for score > 100."""
        valid_profile["performance_analytics"]["average_score"] = 150.0

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        assert any("150" in error or "maximum" in error.lower() for error in result.errors)


class TestCompletionPercentageValidation:
    """Test completion percentage consistency checks."""

    def test_correct_completion_percentage(self, valid_profile):
        """Test validation passes when completion percentage is correct."""
        # 2 modules, 1 completed = 50%
        valid_profile["progress"]["module_progress"] = {
            "m01-intro": {
                "status": "completed",
                "mastery_level": "intermediate",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "time_spent_minutes": 60,
                "attempts": 1,
                "best_score": 80.0,
            },
            "m02-advanced": {
                "status": "in_progress",
                "mastery_level": "novice",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "time_spent_minutes": 30,
                "attempts": 0,
                "best_score": 0.0,
            },
        }
        valid_profile["progress"]["modules_completed"] = ["m01-intro"]
        valid_profile["progress"]["overall_completion_percent"] = 50.0

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert result.valid

    def test_incorrect_completion_percentage(self, valid_profile):
        """Test validation fails when completion percentage is incorrect."""
        # 2 modules, 1 completed should be 50%, but we set it to 75%
        valid_profile["progress"]["module_progress"] = {
            "m01-intro": {
                "status": "completed",
                "mastery_level": "intermediate",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "time_spent_minutes": 60,
                "attempts": 1,
                "best_score": 80.0,
            },
            "m02-advanced": {
                "status": "in_progress",
                "mastery_level": "novice",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "time_spent_minutes": 30,
                "attempts": 0,
                "best_score": 0.0,
            },
        }
        valid_profile["progress"]["modules_completed"] = ["m01-intro"]
        valid_profile["progress"]["overall_completion_percent"] = 75.0  # Wrong!

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        assert any("completion percentage mismatch" in error.lower() for error in result.errors)


class TestModuleProgressConsistency:
    """Test module progress consistency checks."""

    def test_completed_module_not_in_progress(self, valid_profile):
        """Test validation fails when completed module is not in module_progress."""
        valid_profile["progress"]["modules_completed"] = ["m01-intro", "m02-basics"]
        valid_profile["progress"]["module_progress"] = {
            "m01-intro": {
                "status": "completed",
                "mastery_level": "intermediate",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "time_spent_minutes": 60,
                "attempts": 1,
                "best_score": 80.0,
            }
            # m02-basics is missing!
        }

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        assert any("m02-basics" in error for error in result.errors)

    def test_current_module_not_in_progress(self, valid_profile):
        """Test validation fails when current module is not in module_progress."""
        valid_profile["progress"]["current_module_id"] = "m99-missing"
        valid_profile["progress"]["module_progress"] = {
            "m01-intro": {
                "status": "in_progress",
                "mastery_level": "novice",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "time_spent_minutes": 0,
                "attempts": 0,
                "best_score": 0.0,
            }
        }

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        assert any("m99-missing" in error for error in result.errors)

    def test_null_current_module_is_valid(self, valid_profile):
        """Test that null current_module_id is valid."""
        valid_profile["progress"]["current_module_id"] = None
        valid_profile["progress"]["module_progress"] = {}

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert result.valid


class TestAssessmentHistoryValidation:
    """Test assessment history validation."""

    def test_valid_assessment_history(self, valid_profile):
        """Test validation passes with valid assessment history."""
        valid_profile["performance_analytics"]["assessment_history"] = [
            {
                "module_id": "m01-intro",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "score": 85.5,
                "difficulty": "medium",
                "time_taken_minutes": 45,
                "hints_used": 2,
            }
        ]

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert result.valid

    def test_invalid_module_id_in_assessment(self, valid_profile):
        """Test validation fails for invalid module_id in assessment history."""
        valid_profile["performance_analytics"]["assessment_history"] = [
            {
                "module_id": "invalid-module",  # Wrong format
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "score": 85.5,
                "difficulty": "medium",
                "time_taken_minutes": 45,
                "hints_used": 2,
            }
        ]

        validator = LearnerProfileValidator()
        result = validator.validate(valid_profile)

        assert not result.valid
        # Error can come from schema validation (pattern) or custom validation (invalid module_id format)
        assert any(
            "invalid module_id format" in error.lower() or
            "pattern" in error.lower() or
            "assessment" in error.lower()
            for error in result.errors
        )


class TestConvenienceFunction:
    """Test convenience function for validation."""

    def test_validate_learner_profile_function(self, valid_profile):
        """Test validate_learner_profile convenience function."""
        result = validate_learner_profile(valid_profile)

        assert result.valid
        assert isinstance(result, ValidationResult)

    def test_validate_invalid_profile(self, valid_profile):
        """Test convenience function with invalid profile."""
        del valid_profile["learner_id"]

        result = validate_learner_profile(valid_profile)

        assert not result.valid
        assert len(result.errors) > 0
