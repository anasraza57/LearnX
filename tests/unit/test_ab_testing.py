"""
Unit tests for A/B Testing Framework.

Tests the A/B testing infrastructure including:
- Experiment creation and management
- Random assignment
- Result recording
- Statistical analysis
- Sample size calculations
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import numpy as np

from src.evaluation.ab_testing import (
    ABTestFramework,
)


class TestExperimentManagement(unittest.TestCase):
    """Test experiment creation and lifecycle management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = ABTestFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_create_experiment(self):
        """Test experiment creation."""
        experiment = self.framework.create_experiment(
            name="Test Experiment",
            description="Testing experiment creation",
            control_variant="control",
            experimental_variants=["variant_a"],
            allocation_ratio={"control": 0.5, "variant_a": 0.5},
            primary_metric="score",
        )

        self.assertIsNotNone(experiment.experiment_id)
        self.assertEqual(experiment.name, "Test Experiment")
        self.assertEqual(experiment.control_variant, "control")
        self.assertEqual(experiment.experimental_variants, ["variant_a"])
        self.assertEqual(experiment.status, "draft")

    def test_allocation_ratio_validation(self):
        """Test that allocation ratios must sum to 1.0."""
        with self.assertRaises(ValueError):
            self.framework.create_experiment(
                name="Invalid Experiment",
                description="Testing validation",
                control_variant="control",
                experimental_variants=["variant_a"],
                allocation_ratio={"control": 0.4, "variant_a": 0.4},  # Sum = 0.8, not 1.0
            )

    def test_start_experiment(self):
        """Test starting an experiment."""
        experiment = self.framework.create_experiment(
            name="Test Experiment",
            description="Test",
            control_variant="control",
            experimental_variants=["variant_a"],
        )

        self.framework.start_experiment(experiment.experiment_id)
        self.assertEqual(self.framework.experiments[experiment.experiment_id].status, "active")

    def test_stop_experiment(self):
        """Test stopping an experiment."""
        experiment = self.framework.create_experiment(
            name="Test Experiment",
            description="Test",
            control_variant="control",
            experimental_variants=["variant_a"],
        )

        self.framework.start_experiment(experiment.experiment_id)
        self.framework.stop_experiment(experiment.experiment_id)

        self.assertEqual(self.framework.experiments[experiment.experiment_id].status, "completed")
        self.assertIsNotNone(self.framework.experiments[experiment.experiment_id].end_date)


class TestLearnerAssignment(unittest.TestCase):
    """Test learner assignment to experiment variants."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = ABTestFramework(data_dir=self.temp_dir)
        self.experiment = self.framework.create_experiment(
            name="Assignment Test",
            description="Testing assignment",
            control_variant="control",
            experimental_variants=["experimental"],
            allocation_ratio={"control": 0.5, "experimental": 0.5},
        )
        self.framework.start_experiment(self.experiment.experiment_id)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_assign_learner(self):
        """Test assigning a learner to a variant."""
        assignment = self.framework.assign_learner(
            learner_id="learner_001",
            experiment_id=self.experiment.experiment_id,
        )

        self.assertEqual(assignment.learner_id, "learner_001")
        self.assertEqual(assignment.experiment_id, self.experiment.experiment_id)
        self.assertIn(assignment.variant, ["control", "experimental"])

    def test_assignment_is_sticky(self):
        """Test that learners get the same variant on repeated assignment."""
        assignment1 = self.framework.assign_learner(
            learner_id="learner_001",
            experiment_id=self.experiment.experiment_id,
        )

        assignment2 = self.framework.assign_learner(
            learner_id="learner_001",
            experiment_id=self.experiment.experiment_id,
        )

        self.assertEqual(assignment1.variant, assignment2.variant)

    def test_force_variant(self):
        """Test forcing a specific variant assignment."""
        assignment = self.framework.assign_learner(
            learner_id="learner_002",
            experiment_id=self.experiment.experiment_id,
            force_variant="control",
        )

        self.assertEqual(assignment.variant, "control")

    def test_allocation_distribution(self):
        """Test that allocation ratios are roughly respected."""
        np.random.seed(42)

        assignments = {"control": 0, "experimental": 0}

        # Assign 100 learners
        for i in range(100):
            assignment = self.framework.assign_learner(
                learner_id=f"learner_{i:03d}",
                experiment_id=self.experiment.experiment_id,
            )
            assignments[assignment.variant] += 1

        # With 50-50 split and 100 learners, expect ~50 each (allow some variance)
        self.assertGreater(assignments["control"], 30)  # At least 30%
        self.assertLess(assignments["control"], 70)     # At most 70%
        self.assertGreater(assignments["experimental"], 30)
        self.assertLess(assignments["experimental"], 70)

    def test_get_variant(self):
        """Test retrieving a learner's assigned variant."""
        assignment = self.framework.assign_learner(
            learner_id="learner_003",
            experiment_id=self.experiment.experiment_id,
        )

        variant = self.framework.get_variant("learner_003", self.experiment.experiment_id)
        self.assertEqual(variant, assignment.variant)

    def test_get_variant_not_assigned(self):
        """Test getting variant for unassigned learner."""
        variant = self.framework.get_variant("unassigned_learner", self.experiment.experiment_id)
        self.assertIsNone(variant)


class TestResultRecording(unittest.TestCase):
    """Test recording and analyzing experiment results."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = ABTestFramework(data_dir=self.temp_dir)
        self.experiment = self.framework.create_experiment(
            name="Results Test",
            description="Testing result recording",
            control_variant="control",
            experimental_variants=["experimental"],
        )
        self.framework.start_experiment(self.experiment.experiment_id)

        # Assign a learner
        self.assignment = self.framework.assign_learner(
            learner_id="learner_001",
            experiment_id=self.experiment.experiment_id,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_record_result(self):
        """Test recording a result for a learner."""
        self.framework.record_result(
            learner_id="learner_001",
            experiment_id=self.experiment.experiment_id,
            primary_metric_value=85.0,
            secondary_metrics={"time": 45.0},
        )

        self.assertIn(self.experiment.experiment_id, self.framework.results)
        results = self.framework.results[self.experiment.experiment_id]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].primary_metric_value, 85.0)

    def test_record_result_unassigned_learner(self):
        """Test that recording result for unassigned learner raises error."""
        with self.assertRaises(ValueError):
            self.framework.record_result(
                learner_id="unassigned_learner",
                experiment_id=self.experiment.experiment_id,
                primary_metric_value=85.0,
            )


class TestStatisticalAnalysis(unittest.TestCase):
    """Test experiment statistical analysis."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = ABTestFramework(data_dir=self.temp_dir)
        self.experiment = self.framework.create_experiment(
            name="Analysis Test",
            description="Testing analysis",
            control_variant="control",
            experimental_variants=["experimental"],
            allocation_ratio={"control": 0.5, "experimental": 0.5},
        )
        self.framework.start_experiment(self.experiment.experiment_id)

        # Create simulated data: experimental performs better
        np.random.seed(42)

        # Assign 40 learners
        for i in range(40):
            assignment = self.framework.assign_learner(
                learner_id=f"learner_{i:03d}",
                experiment_id=self.experiment.experiment_id,
            )

            # Control: mean 72, std 10
            # Experimental: mean 82, std 10
            if assignment.variant == "control":
                score = np.random.normal(72, 10)
            else:
                score = np.random.normal(82, 10)

            score = max(0, min(100, score))  # Clamp to 0-100

            self.framework.record_result(
                learner_id=f"learner_{i:03d}",
                experiment_id=self.experiment.experiment_id,
                primary_metric_value=score,
            )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_analyze_experiment(self):
        """Test analyzing experiment results."""
        analysis = self.framework.analyze_experiment(self.experiment.experiment_id)

        self.assertEqual(analysis["experiment_id"], self.experiment.experiment_id)
        self.assertEqual(analysis["status"], "active")
        self.assertGreater(analysis["total_participants"], 0)

        # Check variant statistics
        self.assertIn("control", analysis["variant_statistics"])
        self.assertIn("experimental", analysis["variant_statistics"])

        # Check statistical comparisons
        self.assertGreater(len(analysis["statistical_comparisons"]), 0)

        comparison = analysis["statistical_comparisons"][0]
        self.assertIn("p_value", comparison)
        self.assertIn("effect_size_cohens_d", comparison)
        self.assertIn("improvement_percentage", comparison)

        # With our simulated data (10 point difference), should show improvement
        self.assertGreater(comparison["experimental_mean"], comparison["control_mean"])

    def test_analyze_insufficient_data(self):
        """Test analysis with insufficient data."""
        # Create new experiment with no results
        experiment = self.framework.create_experiment(
            name="Empty Experiment",
            description="No data",
            control_variant="control",
            experimental_variants=["experimental"],
        )

        analysis = self.framework.analyze_experiment(experiment.experiment_id)
        self.assertIn("error", analysis)

    def test_interpretation(self):
        """Test that interpretations are generated."""
        analysis = self.framework.analyze_experiment(self.experiment.experiment_id)

        comparison = analysis["statistical_comparisons"][0]
        self.assertIn("interpretation", comparison)
        self.assertIsInstance(comparison["interpretation"], str)

    def test_recommendation(self):
        """Test that recommendations are made."""
        analysis = self.framework.analyze_experiment(self.experiment.experiment_id)

        self.assertIn("recommendation", analysis)
        self.assertIsInstance(analysis["recommendation"], str)


class TestSampleSizeCalculation(unittest.TestCase):
    """Test sample size calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = ABTestFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_calculate_sample_size(self):
        """Test sample size calculation."""
        result = self.framework.calculate_sample_size(
            baseline_mean=75.0,
            baseline_std=12.0,
            minimum_detectable_effect=10.0,
            alpha=0.05,
            power=0.80,
        )

        self.assertIn("sample_size_per_group", result)
        self.assertIn("total_sample_size", result)
        self.assertIn("recommendation", result)

        # Sample size should be positive integer
        self.assertGreater(result["sample_size_per_group"], 0)
        self.assertIsInstance(result["sample_size_per_group"], int)

    def test_sample_size_larger_for_small_effects(self):
        """Test that smaller effects require larger sample sizes."""
        # Large effect (20%)
        result_large = self.framework.calculate_sample_size(
            baseline_mean=75.0,
            baseline_std=12.0,
            minimum_detectable_effect=20.0,
        )

        # Small effect (5%)
        result_small = self.framework.calculate_sample_size(
            baseline_mean=75.0,
            baseline_std=12.0,
            minimum_detectable_effect=5.0,
        )

        # Small effects need more samples
        self.assertGreater(
            result_small["sample_size_per_group"],
            result_large["sample_size_per_group"]
        )


class TestDataPersistence(unittest.TestCase):
    """Test that experiment data is properly saved and loaded."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.framework = ABTestFramework(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_experiment_persistence(self):
        """Test that experiments are saved to disk."""
        experiment = self.framework.create_experiment(
            name="Persistence Test",
            description="Testing persistence",
            control_variant="control",
            experimental_variants=["experimental"],
        )

        # Check file was created
        exp_file = self.temp_dir / "experiments" / f"{experiment.experiment_id}.json"
        self.assertTrue(exp_file.exists())

    def test_assignment_persistence(self):
        """Test that assignments are saved to disk."""
        experiment = self.framework.create_experiment(
            name="Assignment Persistence",
            description="Test",
            control_variant="control",
            experimental_variants=["experimental"],
        )

        assignment = self.framework.assign_learner("learner_001", experiment.experiment_id)

        # Check file was created
        assignment_file = self.temp_dir / "assignments" / f"learner_001_{experiment.experiment_id}.json"
        self.assertTrue(assignment_file.exists())

    def test_result_persistence(self):
        """Test that results are saved to disk."""
        experiment = self.framework.create_experiment(
            name="Result Persistence",
            description="Test",
            control_variant="control",
            experimental_variants=["experimental"],
        )

        assignment = self.framework.assign_learner("learner_001", experiment.experiment_id)
        self.framework.record_result("learner_001", experiment.experiment_id, 85.0)

        # Check file was created
        results_dir = self.temp_dir / "results" / experiment.experiment_id
        self.assertTrue(results_dir.exists())
        self.assertGreater(len(list(results_dir.glob("*.json"))), 0)


if __name__ == "__main__":
    unittest.main()
