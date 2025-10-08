"""
Unit tests for schema validation.

Tests:
- JSON Schema validation
- Auto-repair functionality
- Workload feasibility checks
- Prerequisite validation
- Module ID uniqueness
- Topological sorting
"""

import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils.validate import (
    validate_syllabus,
    SyllabusValidator,
    SchemaValidator,
    ValidationResult,
)


class TestValidationResult:
    """Test suite for ValidationResult class."""

    def test_valid_result_is_truthy(self):
        """Test that valid results are truthy."""
        result = ValidationResult(valid=True, errors=[])
        assert bool(result) is True

    def test_invalid_result_is_falsy(self):
        """Test that invalid results are falsy."""
        result = ValidationResult(valid=False, errors=["error"])
        assert bool(result) is False

    def test_str_representation_valid(self):
        """Test string representation of valid result."""
        result = ValidationResult(valid=True, errors=[])
        assert "✓" in str(result)
        assert "passed" in str(result).lower()

    def test_str_representation_invalid(self):
        """Test string representation of invalid result."""
        result = ValidationResult(valid=False, errors=["error1", "error2"])
        assert "✗" in str(result)
        assert "2" in str(result)
        assert "error1" in str(result)

    def test_repairs_tracked(self):
        """Test that repairs are tracked in result."""
        result = ValidationResult(
            valid=True, errors=[], repairs=["repair1", "repair2"]
        )
        assert len(result.repairs) == 2
        assert "repair1" in result.repairs


class TestSyllabusValidation:
    """Test suite for syllabus validation."""

    def get_valid_syllabus(self):
        """Get a valid syllabus for testing."""
        return {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "test",
            },
            "topic": "Introduction to Machine Learning",
            "duration_weeks": 8,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m01-fundamentals",
                    "title": "ML Fundamentals",
                    "description": "Basic concepts",
                    "outcomes": ["Understand supervised learning concepts"],
                    "topics": ["Classification", "Regression"],
                    "estimated_hours": 20,
                },
                {
                    "id": "m02-neural-networks",
                    "title": "Neural Networks",
                    "description": "Deep learning basics",
                    "outcomes": ["Build a simple neural network"],
                    "topics": ["Perceptrons", "Backpropagation"],
                    "prerequisites": ["m01-fundamentals"],
                    "estimated_hours": 30,
                },
            ],
            "total_estimated_hours": 50,
            "workload_feasible": True,
        }

    def test_valid_syllabus_passes(self):
        """Test that a valid syllabus passes validation."""
        syllabus = self.get_valid_syllabus()
        result = validate_syllabus(syllabus, auto_repair=False)

        assert result.valid
        assert len(result.errors) == 0

    def test_auto_repair_adds_missing_meta(self):
        """Test that auto-repair adds missing metadata."""
        syllabus = {
            "topic": "Python Programming",
            "duration_weeks": 6,
            "weekly_time_hours": 8,
            "modules": [
                {
                    "title": "Python Basics",
                    "outcomes": ["Write Python scripts successfully"],
                    "topics": ["Variables", "Functions"],
                    "estimated_hours": 15,
                }
            ],
        }

        result = validate_syllabus(syllabus, auto_repair=True)

        assert result.valid
        assert result.data["meta"]["schema_version"] == 1
        assert "created_at" in result.data["meta"]
        assert any("schema_version" in r for r in result.repairs)

    def test_auto_repair_generates_module_ids(self):
        """Test that auto-repair generates valid module IDs."""
        syllabus = {
            "topic": "Python Programming",
            "duration_weeks": 6,
            "weekly_time_hours": 8,
            "modules": [
                {
                    "title": "Python Basics",
                    "outcomes": ["Write Python scripts successfully"],
                    "topics": ["Variables", "Functions"],
                    "estimated_hours": 15,
                }
            ],
        }

        result = validate_syllabus(syllabus, auto_repair=True)

        assert result.valid
        module_id = result.data["modules"][0]["id"]
        assert module_id.startswith("m0")
        assert "python-basics" in module_id

    def test_workload_validation_rejects_overload(self):
        """Test that workload validation rejects infeasible workloads."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test Topic",
            "duration_weeks": 1,
            "weekly_time_hours": 5,
            "modules": [
                {
                    "id": "m01-test",
                    "title": "Test Module",
                    "outcomes": ["Test outcome here"],
                    "topics": ["Testing"],
                    "estimated_hours": 100,  # Too many hours!
                }
            ],
            "total_estimated_hours": 100,
        }

        result = validate_syllabus(syllabus, auto_repair=True)

        assert not result.valid
        assert any("workload" in err.lower() for err in result.errors)

    def test_duplicate_module_ids_rejected(self):
        """Test that duplicate module IDs are rejected."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m01-test",
                    "title": "Module 1",
                    "outcomes": ["Outcome A for testing"],
                    "topics": ["Topic X"],
                    "estimated_hours": 10,
                },
                {
                    "id": "m01-test",  # Duplicate!
                    "title": "Module 2",
                    "outcomes": ["Outcome B for testing"],
                    "topics": ["Topic Y"],
                    "estimated_hours": 10,
                },
            ],
            "total_estimated_hours": 20,
        }

        result = validate_syllabus(syllabus, auto_repair=False)

        assert not result.valid
        assert any("duplicate" in err.lower() for err in result.errors)

    def test_cyclic_prerequisites_rejected(self):
        """Test that cyclic prerequisite graphs are rejected."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test Course",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m01-module-a",
                    "title": "Module A",
                    "prerequisites": ["m02-module-b"],  # Cycle!
                    "outcomes": ["Understand the basics of module A"],
                    "topics": ["Topic A1", "Topic A2"],
                    "estimated_hours": 10,
                },
                {
                    "id": "m02-module-b",
                    "title": "Module B",
                    "prerequisites": ["m01-module-a"],  # Cycle!
                    "outcomes": ["Understand the basics of module B"],
                    "topics": ["Topic B1", "Topic B2"],
                    "estimated_hours": 10,
                },
            ],
            "total_estimated_hours": 20,
        }

        result = validate_syllabus(syllabus, auto_repair=False)

        assert not result.valid
        assert any("cycle" in err.lower() for err in result.errors)

    def test_topological_sorting(self):
        """Test that modules are sorted topologically."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test Course",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m03-advanced",
                    "title": "Advanced Topics",
                    "prerequisites": ["m02-intermediate"],
                    "outcomes": ["Master advanced concepts in the field"],
                    "topics": ["Advanced Topic A", "Advanced Topic B"],
                    "estimated_hours": 10,
                },
                {
                    "id": "m01-basics",
                    "title": "Basic Concepts",
                    "outcomes": ["Understand basic concepts thoroughly"],
                    "topics": ["Basic Topic A", "Basic Topic B"],
                    "estimated_hours": 10,
                },
                {
                    "id": "m02-intermediate",
                    "title": "Intermediate Skills",
                    "prerequisites": ["m01-basics"],
                    "outcomes": ["Develop intermediate skills effectively"],
                    "topics": ["Intermediate Topic A", "Intermediate Topic B"],
                    "estimated_hours": 10,
                },
            ],
            "total_estimated_hours": 30,
        }

        result = validate_syllabus(syllabus, auto_repair=True)

        assert result.valid
        sorted_ids = [m["id"] for m in result.data["modules"]]
        assert sorted_ids == ["m01-basics", "m02-intermediate", "m03-advanced"]

    def test_unknown_prerequisite_rejected(self):
        """Test that unknown prerequisite references are rejected."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m01-test",
                    "title": "Test",
                    "prerequisites": ["m99-nonexistent"],  # Unknown!
                    "outcomes": ["Test outcome here"],
                    "topics": ["Testing"],
                    "estimated_hours": 10,
                }
            ],
            "total_estimated_hours": 10,
        }

        result = validate_syllabus(syllabus, auto_repair=False)

        assert not result.valid
        assert any("unknown prerequisite" in err.lower() for err in result.errors)

    def test_self_prerequisite_rejected(self):
        """Test that self-prerequisites are rejected."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m01-test",
                    "title": "Test",
                    "prerequisites": ["m01-test"],  # Self-prerequisite!
                    "outcomes": ["Test outcome here"],
                    "topics": ["Testing"],
                    "estimated_hours": 10,
                }
            ],
            "total_estimated_hours": 10,
        }

        result = validate_syllabus(syllabus, auto_repair=False)

        assert not result.valid
        assert any("itself" in err.lower() for err in result.errors)

    def test_configurable_workload_buffer(self):
        """Test that workload buffer is configurable."""
        syllabus = {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "topic": "Test",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "id": "m01-test",
                    "title": "Test",
                    "outcomes": ["Test outcome here"],
                    "topics": ["Testing"],
                    "estimated_hours": 42,  # 10.5 hrs/week
                }
            ],
            "total_estimated_hours": 42,
        }

        # With 10% buffer: should pass (10 * 1.1 = 11 > 10.5)
        validator_10pct = SyllabusValidator(buffer_ratio=0.10)
        result1 = validator_10pct.validate(syllabus, auto_repair=False)

        # With 0% buffer: should fail (10 * 1.0 = 10 < 10.5)
        validator_0pct = SyllabusValidator(buffer_ratio=0.0)
        result2 = validator_0pct.validate(syllabus, auto_repair=False)

        assert result1.valid
        assert not result2.valid


class TestAutoRepair:
    """Test suite for auto-repair functionality."""

    def test_deep_copy_prevents_mutation(self):
        """Test that auto-repair doesn't mutate original data."""
        original = {
            "topic": "Machine Learning",
            "duration_weeks": 8,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "title": "Intro",
                    "outcomes": ["Learn basics of ML"],
                    "topics": ["ML basics"],
                    "estimated_hours": 20,
                }
            ],
        }

        # Keep reference to original module
        original_module = original["modules"][0]

        result = validate_syllabus(original, auto_repair=True)

        # Original should not have been mutated
        assert "id" not in original_module
        # Repaired should have ID
        assert "id" in result.data["modules"][0]

    def test_type_coercion(self):
        """Test that string numbers are coerced to proper types."""
        syllabus = {
            "topic": "Test",
            "duration_weeks": "8",  # String instead of int
            "weekly_time_hours": "10.5",  # String instead of float
            "modules": [
                {
                    "title": "Test",
                    "outcomes": ["Test outcome here"],
                    "topics": ["Testing"],
                    "estimated_hours": "20.5",  # String instead of float
                }
            ],
        }

        result = validate_syllabus(syllabus, auto_repair=True)

        assert result.valid
        assert isinstance(result.data["duration_weeks"], int)
        assert isinstance(result.data["weekly_time_hours"], float)
        assert isinstance(result.data["modules"][0]["estimated_hours"], float)

    def test_https_upgrade(self):
        """Test that HTTP URLs are upgraded to HTTPS."""
        syllabus = {
            "topic": "Test",
            "duration_weeks": 4,
            "weekly_time_hours": 10,
            "modules": [
                {
                    "title": "Test",
                    "outcomes": ["Test outcome here"],
                    "topics": ["Testing"],
                    "estimated_hours": 10,
                    "resources": [
                        {
                            "type": "video",
                            "title": "Tutorial",
                            "url": "http://example.com/video",  # HTTP
                        }
                    ],
                }
            ],
        }

        result = validate_syllabus(syllabus, auto_repair=True)

        url = result.data["modules"][0]["resources"][0]["url"]
        assert url.startswith("https://")
        assert "https://example.com/video" == url
