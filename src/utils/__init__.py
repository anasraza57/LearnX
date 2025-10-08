"""
Utility modules for EduGPT-PersonalisedLearning.

This module contains utility functions:
- validation: JSON Schema validation with auto-repair
- progress: Analytics and progress tracking helpers
- (Future) file_handlers: File I/O helpers
- (Future) preprocessing: Data preprocessing utilities
"""

from .validation import (
    SyllabusValidator,
    LearnerProfileValidator,
    validate_syllabus,
    validate_learner_profile,
)
from .progress import (
    mastery_histogram,
    mastery_summary,
    mastery_percentile,
    mastery_by_category,
    learning_velocity,
)

__all__ = [
    "SyllabusValidator",
    "LearnerProfileValidator",
    "validate_syllabus",
    "validate_learner_profile",
    "mastery_histogram",
    "mastery_summary",
    "mastery_percentile",
    "mastery_by_category",
    "learning_velocity",
]
