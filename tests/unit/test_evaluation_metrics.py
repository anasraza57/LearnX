"""
Unit tests for Evaluation Metrics Framework.

Tests the evaluation metrics calculations including:
- Learning gain calculations (Hake's normalized gain)
- Retention metrics
- Engagement metrics
- Statistical comparisons (t-tests, Cohen's d)
- Baseline comparisons
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import numpy as np

from src.evaluation.metrics import (
    EvaluationFramework,
    LearningGainMetrics,
    PersonalizationEffectiveness,
)


class TestLearningGainMetrics(unittest.TestCase):
    """Test learning gain calculations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = EvaluationFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_normalized_gain_calculation(self):
        """Test Hake's normalized gain formula."""
        # Test case: pre=40, post=85, max=100
        # Expected: (85-40)/(100-40) = 45/60 = 0.75
        gain = LearningGainMetrics.calculate(40.0, 85.0, 100.0)
        self.assertAlmostEqual(gain, 0.75, places=2)

    def test_normalized_gain_no_room_to_improve(self):
        """Test normalized gain when learner starts at max score."""
        # If pre_score = max_score, gain should be 0
        gain = LearningGainMetrics.calculate(100.0, 100.0, 100.0)
        self.assertEqual(gain, 0.0)

    def test_normalized_gain_perfect_improvement(self):
        """Test normalized gain with perfect improvement."""
        # From 0 to 100 should give gain of 1.0
        gain = LearningGainMetrics.calculate(0.0, 100.0, 100.0)
        self.assertAlmostEqual(gain, 1.0, places=2)

    def test_calculate_learning_gain(self):
        """Test complete learning gain calculation."""
        gain = self.framework.calculate_learning_gain(
            learner_id="test_001",
            module_id="test_module",
            pre_test_score=40.0,
            post_test_score=85.0,
        )

        self.assertEqual(gain.learner_id, "test_001")
        self.assertEqual(gain.module_id, "test_module")
        self.assertEqual(gain.pre_test_score, 40.0)
        self.assertEqual(gain.post_test_score, 85.0)
        self.assertEqual(gain.absolute_gain, 45.0)
        self.assertAlmostEqual(gain.relative_gain, 1.125, places=2)
        self.assertAlmostEqual(gain.normalized_gain, 0.75, places=2)

    def test_score_validation_pre_test(self):
        """Test that pre-test scores outside [0, 100] raise ValueError."""
        with self.assertRaises(ValueError) as cm:
            self.framework.calculate_learning_gain(
                learner_id="test",
                module_id="test",
                pre_test_score=-10.0,  # Invalid
                post_test_score=85.0,
            )
        self.assertIn("pre_test_score must be in [0, 100]", str(cm.exception))

    def test_score_validation_post_test(self):
        """Test that post-test scores outside [0, 100] raise ValueError."""
        with self.assertRaises(ValueError) as cm:
            self.framework.calculate_learning_gain(
                learner_id="test",
                module_id="test",
                pre_test_score=40.0,
                post_test_score=150.0,  # Invalid
            )
        self.assertIn("post_test_score must be in [0, 100]", str(cm.exception))

    def test_interpret_normalized_gain_high(self):
        """Test interpretation of high normalized gain."""
        interp = self.framework._interpret_normalized_gain(0.8)
        self.assertIn("High gain", interp)

    def test_interpret_normalized_gain_medium(self):
        """Test interpretation of medium normalized gain."""
        interp = self.framework._interpret_normalized_gain(0.5)
        self.assertIn("Medium gain", interp)

    def test_interpret_normalized_gain_low(self):
        """Test interpretation of low normalized gain."""
        interp = self.framework._interpret_normalized_gain(0.2)
        self.assertIn("Low gain", interp)

    def test_analyze_learning_gains(self):
        """Test analysis of multiple learning gains."""
        gains = [
            LearningGainMetrics(
                learner_id=f"learner_{i}",
                module_id="test",
                pre_test_score=40.0,
                post_test_score=85.0,
                absolute_gain=45.0,
                relative_gain=1.125,
                normalized_gain=0.75,
                timestamp="2025-01-01",
            )
            for i in range(10)
        ]

        analysis = self.framework.analyze_learning_gains(gains)

        self.assertEqual(analysis["n"], 10)
        self.assertAlmostEqual(analysis["normalized_gain"]["mean"], 0.75)
        self.assertIn("interpretation", analysis["normalized_gain"])


class TestRetentionMetrics(unittest.TestCase):
    """Test retention metrics calculations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = EvaluationFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_calculate_retention(self):
        """Test retention rate calculation."""
        retention = self.framework.calculate_retention(
            learner_id="test_001",
            module_id="test_module",
            initial_score=85.0,
            retention_score=72.0,
            days_elapsed=30,
        )

        self.assertEqual(retention.learner_id, "test_001")
        self.assertEqual(retention.initial_score, 85.0)
        self.assertEqual(retention.retention_score, 72.0)
        self.assertEqual(retention.days_elapsed, 30)
        self.assertAlmostEqual(retention.retention_rate, 72.0 / 85.0, places=3)
        self.assertAlmostEqual(retention.forgetting_rate, 1.0 - (72.0 / 85.0), places=3)

    def test_interpret_retention_excellent(self):
        """Test interpretation of excellent retention."""
        interp = self.framework._interpret_retention(0.85)
        self.assertIn("Excellent", interp)

    def test_interpret_retention_poor(self):
        """Test interpretation of poor retention."""
        interp = self.framework._interpret_retention(0.35)
        self.assertIn("Poor", interp)


class TestEngagementMetrics(unittest.TestCase):
    """Test engagement metrics calculations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = EvaluationFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_calculate_engagement(self):
        """Test engagement calculation from learner data."""
        learner_data = {
            "learner_id": "test_001",
            "performance_analytics": {
                "assessment_history": [
                    {"score": 85, "timestamp": "2025-01-01"},
                    {"score": 88, "timestamp": "2025-01-05"},
                    {"score": 92, "timestamp": "2025-01-10"},
                ]
            },
            "progress": {
                "total_study_time_minutes": 180,
                "learning_streak_days": 10,
                "module_progress": {
                    "module_1": {"status": "completed"},
                    "module_2": {"status": "completed"},
                    "module_3": {"status": "in_progress"},
                }
            }
        }

        engagement = self.framework.calculate_engagement(learner_data)

        self.assertEqual(engagement.learner_id, "test_001")
        self.assertEqual(engagement.total_sessions, 3)
        self.assertEqual(engagement.total_time_minutes, 180)
        self.assertAlmostEqual(engagement.average_session_time, 60.0, places=1)
        self.assertAlmostEqual(engagement.completion_rate, 2.0 / 3.0, places=2)
        self.assertEqual(engagement.learning_streak_days, 10)

    def test_calculate_engagement_fallback_format(self):
        """Test engagement calculation with simple counter format (backward compatibility)."""
        learner_data = {
            "learner_id": "test_002",
            "performance_analytics": {
                "assessment_history": [
                    {"score": 85},
                    {"score": 88},
                ]
            },
            "progress": {
                "total_study_time_minutes": 120,
                "learning_streak_days": 5,
                "modules_total": 5,  # Fallback format
                "modules_completed": 4,  # Fallback format
            }
        }

        engagement = self.framework.calculate_engagement(learner_data)

        self.assertEqual(engagement.learner_id, "test_002")
        self.assertEqual(engagement.total_sessions, 2)
        self.assertAlmostEqual(engagement.completion_rate, 4.0 / 5.0, places=2)  # 0.8
        self.assertEqual(engagement.learning_streak_days, 5)


class TestStatisticalComparisons(unittest.TestCase):
    """Test statistical comparison methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = EvaluationFramework(data_dir=self.temp_dir)
        np.random.seed(42)  # For reproducible tests

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_compare_personalization_effectiveness(self):
        """Test A/B comparison with statistical tests."""
        # Create two groups with known difference
        control = [70.0, 72.0, 68.0, 71.0, 69.0, 73.0, 70.0, 72.0]
        experimental = [85.0, 87.0, 83.0, 86.0, 84.0, 88.0, 85.0, 87.0]

        result = self.framework.compare_personalization_effectiveness(
            experimental_group=experimental,
            control_group=control,
            alpha=0.05,
        )

        self.assertGreater(result.experimental_group_avg, result.control_group_avg)
        self.assertLess(result.p_value, 0.05)  # Should be significant
        self.assertGreater(result.effect_size, 0.5)  # Should be large effect
        self.assertGreater(result.improvement_percentage, 0)

    def test_compare_no_difference(self):
        """Test A/B comparison when there's no real difference."""
        # Two groups with same distribution
        control = [75.0, 73.0, 77.0, 74.0, 76.0, 75.0, 74.0, 76.0]
        experimental = [74.0, 76.0, 75.0, 73.0, 77.0, 75.0, 76.0, 74.0]

        result = self.framework.compare_personalization_effectiveness(
            experimental_group=experimental,
            control_group=control,
            alpha=0.05,
        )

        # Should not be significant
        self.assertGreaterEqual(result.p_value, 0.05)

    def test_interpret_ab_test_significant(self):
        """Test interpretation of significant A/B test."""
        metrics = PersonalizationEffectiveness(
            experimental_group_avg=85.0,
            control_group_avg=75.0,
            effect_size=0.8,
            p_value=0.001,
            improvement_percentage=13.3,
            confidence_interval=(5.0, 15.0),
            sample_size_experimental=30,
            sample_size_control=30,
            timestamp="2025-01-01",
        )

        interpretation = self.framework.interpret_ab_test(metrics)

        self.assertIn("Statistically significant", interpretation["statistical_significance"])
        self.assertIn("Large effect", interpretation["effect_size_interpretation"])
        self.assertIn("EFFECTIVE", interpretation["overall_conclusion"])

    def test_compare_to_baseline(self):
        """Test baseline comparison."""
        system_scores = [85.0, 87.0, 83.0, 86.0, 84.0, 88.0, 85.0, 87.0]
        baseline_scores = [70.0, 72.0, 68.0, 71.0, 69.0, 73.0, 70.0, 72.0]

        comparison = self.framework.compare_to_baseline(
            system_scores=system_scores,
            baseline_scores=baseline_scores,
            baseline_name="Traditional Method"
        )

        self.assertEqual(comparison["baseline"], "Traditional Method")
        self.assertGreater(comparison["system_mean"], comparison["baseline_mean"])
        self.assertGreater(comparison["improvement_percentage"], 0)
        self.assertTrue(comparison["statistically_significant"])

    def test_insufficient_data(self):
        """Test error handling with insufficient data."""
        with self.assertRaises(ValueError):
            self.framework.compare_personalization_effectiveness(
                experimental_group=[85.0],  # Only 1 sample
                control_group=[75.0],  # Only 1 sample
            )


class TestDataPersistence(unittest.TestCase):
    """Test that metrics are properly saved and loaded."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = EvaluationFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_save_learning_gain(self):
        """Test that learning gain metrics are saved."""
        gain = self.framework.calculate_learning_gain(
            learner_id="test_001",
            module_id="test_module",
            pre_test_score=40.0,
            post_test_score=85.0,
        )

        # Check that file was created
        metrics_dir = self.temp_dir / "learning_gain"
        self.assertTrue(metrics_dir.exists())
        self.assertGreater(len(list(metrics_dir.glob("*.json"))), 0)

    def test_load_metrics(self):
        """Test loading saved metrics."""
        # Create some metrics
        self.framework.calculate_learning_gain(
            learner_id="test_001",
            module_id="test_module",
            pre_test_score=40.0,
            post_test_score=85.0,
        )

        # Load them back
        loaded_metrics = self.framework.load_metrics("learning_gain")
        self.assertGreater(len(loaded_metrics), 0)
        self.assertEqual(loaded_metrics[0]["learner_id"], "test_001")


if __name__ == "__main__":
    unittest.main()
