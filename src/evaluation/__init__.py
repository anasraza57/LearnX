"""
Evaluation Module for EduGPT Personalized Learning System

This module provides comprehensive evaluation tools to scientifically assess
the effectiveness of the personalized learning system.

Modules:
- metrics: Core evaluation metrics (learning gain, retention, engagement)
- ab_testing: A/B testing framework for controlled experiments
- benchmarks: Baseline comparison methods and industry benchmarks
"""

from .metrics import (
    EvaluationFramework,
    LearningGainMetrics,
    RetentionMetrics,
    EngagementMetrics,
    PersonalizationEffectiveness,
    ContentQualityMetrics,
    SystemPerformanceMetrics,
)

from .ab_testing import (
    ABTestFramework,
    ExperimentConfig,
    ParticipantAssignment,
    ExperimentResult,
    create_adaptive_difficulty_experiment,
    create_personalized_content_experiment,
    create_spaced_repetition_experiment,
)

__all__ = [
    # Evaluation Framework
    "EvaluationFramework",
    "LearningGainMetrics",
    "RetentionMetrics",
    "EngagementMetrics",
    "PersonalizationEffectiveness",
    "ContentQualityMetrics",
    "SystemPerformanceMetrics",
    # A/B Testing
    "ABTestFramework",
    "ExperimentConfig",
    "ParticipantAssignment",
    "ExperimentResult",
    "create_adaptive_difficulty_experiment",
    "create_personalized_content_experiment",
    "create_spaced_repetition_experiment",
]
