"""
Data models for personalized learning.

This module contains core data models:
- LearnerProfile: Student profiles with progress tracking and analytics
- (Future) Syllabus: Course structure and curriculum
- (Future) Assessment: Quiz/test models
"""

from .learner_profile import LearnerModel

__all__ = [
    "LearnerModel",
]
