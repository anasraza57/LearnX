"""
Shared pytest fixtures and configuration for LearnX tests.

This file is automatically discovered by pytest and provides
fixtures available to all tests.
"""

import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def valid_syllabus():
    """
    Fixture providing a valid syllabus for testing.

    Returns:
        dict: A complete, valid syllabus that passes all validation
    """
    return {
        "meta": {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "pytest",
        },
        "topic": "Introduction to Machine Learning",
        "duration_weeks": 8,
        "weekly_time_hours": 10,
        "modules": [
            {
                "id": "m01-fundamentals",
                "title": "ML Fundamentals",
                "description": "Basic machine learning concepts",
                "outcomes": ["Understand supervised learning principles"],
                "topics": ["Classification", "Regression", "Model Evaluation"],
                "estimated_hours": 20,
            },
            {
                "id": "m02-neural-networks",
                "title": "Neural Networks",
                "description": "Introduction to deep learning",
                "outcomes": ["Build and train simple neural networks"],
                "topics": ["Perceptrons", "Backpropagation", "Activation Functions"],
                "prerequisites": ["m01-fundamentals"],
                "estimated_hours": 30,
            },
        ],
        "total_estimated_hours": 50,
        "workload_feasible": True,
    }


@pytest.fixture
def minimal_syllabus():
    """
    Fixture providing a minimal syllabus (requires auto-repair).

    Returns:
        dict: A minimal syllabus missing optional fields
    """
    return {
        "topic": "Python Programming",
        "duration_weeks": 6,
        "weekly_time_hours": 8,
        "modules": [
            {
                "title": "Python Basics",
                "outcomes": ["Write Python scripts successfully"],
                "topics": ["Variables", "Functions", "Control Flow"],
                "estimated_hours": 15,
            }
        ],
    }


@pytest.fixture
def invalid_syllabus():
    """
    Fixture providing an invalid syllabus for testing validation errors.

    Returns:
        dict: A syllabus with validation errors
    """
    return {
        "meta": {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "topic": "Test",
        "duration_weeks": -1,  # Invalid: negative
        "weekly_time_hours": 100,  # Invalid: > 40
        "modules": [],  # Invalid: minItems = 1
    }


@pytest.fixture(autouse=True)
def reset_token_tracker():
    """
    Auto-fixture to reset token tracker before each test.

    This ensures tests don't interfere with each other.
    """
    from config import token_tracker

    token_tracker.reset()
    yield
    token_tracker.reset()


@pytest.fixture(autouse=True)
def fast_learner_model(monkeypatch):
    """
    Auto-fixture to disable validation in LearnerModel for faster tests.

    Validation itself is tested separately in validation-specific tests.
    """
    try:
        from src.models.learner_profile import LearnerModel
        original_init = LearnerModel.__init__

        def fast_init(self, *args, **kwargs):
            kwargs.setdefault("validate", False)
            return original_init(self, *args, **kwargs)

        monkeypatch.setattr(LearnerModel, "__init__", fast_init)
    except ImportError:
        # Module not yet created, skip
        pass


@pytest.fixture
def temp_schema_file(tmp_path):
    """
    Fixture providing a temporary schema file for testing.

    Args:
        tmp_path: pytest's tmp_path fixture

    Returns:
        Path: Path to temporary schema file
    """
    import json

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"test": {"type": "string"}},
        "required": ["test"],
    }

    schema_file = tmp_path / "test.schema.json"
    with open(schema_file, "w") as f:
        json.dump(schema, f)

    return schema_file


# Pytest hooks for better test output


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Mark tests in unit/ directory as unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Mark tests in integration/ directory as integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
