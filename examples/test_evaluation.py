"""
Example: Testing the Evaluation Framework

This script demonstrates how to test and use the evaluation framework yourself.
Run this to verify everything works and see the evaluation metrics in action.

Usage:
    python examples/test_evaluation.py
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import (
    EvaluationFramework,
    ABTestFramework,
)
import numpy as np


def test_learning_gains():
    """Test 1: Calculate learning gains for a learner."""
    print("\n" + "=" * 70)
    print("TEST 1: LEARNING GAINS")
    print("=" * 70)

    framework = EvaluationFramework(data_dir=Path("data/evaluation"))

    # Simulate a learner taking pre and post tests
    learner_id = "demo_learner_001"
    module_id = "python_basics"

    # Scenario: Learner starts with 45% knowledge, ends with 88% after learning
    pre_test = 45.0
    post_test = 88.0

    print(f"\nScenario:")
    print(f"  Learner: {learner_id}")
    print(f"  Module: {module_id}")
    print(f"  Pre-test Score: {pre_test}%")
    print(f"  Post-test Score: {post_test}%")

    # Calculate learning gain
    gain = framework.calculate_learning_gain(
        learner_id=learner_id,
        module_id=module_id,
        pre_test_score=pre_test,
        post_test_score=post_test,
    )

    print(f"\nResults:")
    print(f"  ✅ Absolute Gain: {gain.absolute_gain:.1f} points")
    print(f"  ✅ Relative Gain: {gain.relative_gain:.2f}x improvement")
    print(f"  ✅ Normalized Gain (Hake): {gain.normalized_gain:.2f}")
    print(f"\nInterpretation:")
    interpretation = framework._interpret_normalized_gain(gain.normalized_gain)
    print(f"  {interpretation}")

    if gain.normalized_gain > 0.7:
        print(f"  🎉 EXCELLENT! Your system is highly effective!")
    elif gain.normalized_gain > 0.5:
        print(f"  👍 GOOD! Your system shows solid learning gains.")
    elif gain.normalized_gain > 0.3:
        print(f"  ⚠️  MODERATE. Room for improvement.")
    else:
        print(f"  ❌ LOW. System needs significant improvement.")

    return gain


def test_retention():
    """Test 2: Measure knowledge retention over time."""
    print("\n" + "=" * 70)
    print("TEST 2: RETENTION METRICS")
    print("=" * 70)

    framework = EvaluationFramework(data_dir=Path("data/evaluation"))

    learner_id = "demo_learner_001"
    module_id = "python_basics"

    # Scenario: Learner scored 88% immediately, 78% after 30 days
    initial_score = 88.0
    retention_score_7d = 85.0
    retention_score_30d = 78.0
    retention_score_90d = 70.0

    print(f"\nScenario:")
    print(f"  Initial Score: {initial_score}%")
    print(f"  Score after 7 days: {retention_score_7d}%")
    print(f"  Score after 30 days: {retention_score_30d}%")
    print(f"  Score after 90 days: {retention_score_90d}%")

    # Calculate retention at different time points
    retention_7d = framework.calculate_retention(
        learner_id=learner_id,
        module_id=module_id,
        initial_score=initial_score,
        retention_score=retention_score_7d,
        days_elapsed=7,
    )

    retention_30d = framework.calculate_retention(
        learner_id=learner_id,
        module_id=module_id,
        initial_score=initial_score,
        retention_score=retention_score_30d,
        days_elapsed=30,
    )

    retention_90d = framework.calculate_retention(
        learner_id=learner_id,
        module_id=module_id,
        initial_score=initial_score,
        retention_score=retention_score_90d,
        days_elapsed=90,
    )

    print(f"\nResults:")
    print(f"  ✅ Retention Rate (7 days): {retention_7d.retention_rate:.1%}")
    print(f"  ✅ Retention Rate (30 days): {retention_30d.retention_rate:.1%}")
    print(f"  ✅ Retention Rate (90 days): {retention_90d.retention_rate:.1%}")

    avg_retention = (retention_7d.retention_rate + retention_30d.retention_rate + retention_90d.retention_rate) / 3

    print(f"\nInterpretation:")
    if avg_retention > 0.8:
        print(f"  🎉 EXCELLENT! Knowledge is sticking long-term!")
    elif avg_retention > 0.6:
        print(f"  👍 GOOD! Learners retain knowledge well.")
    elif avg_retention > 0.4:
        print(f"  ⚠️  MODERATE. Some forgetting occurring.")
    else:
        print(f"  ❌ POOR. Significant forgetting - need spaced repetition.")

    return retention_30d


def test_engagement():
    """Test 3: Calculate engagement metrics."""
    print("\n" + "=" * 70)
    print("TEST 3: ENGAGEMENT METRICS")
    print("=" * 70)

    framework = EvaluationFramework(data_dir=Path("data/evaluation"))

    # Create a mock learner profile
    learner_data = {
        "learner_id": "demo_learner_001",
        "performance_analytics": {
            "assessment_history": [
                {"score": 85, "timestamp": "2025-01-01"},
                {"score": 88, "timestamp": "2025-01-05"},
                {"score": 92, "timestamp": "2025-01-10"},
                {"score": 90, "timestamp": "2025-01-15"},
            ]
        },
        "progress": {
            "total_study_time_minutes": 240,
            "learning_streak_days": 12,
            "module_progress": {
                "module_1": {"status": "completed"},
                "module_2": {"status": "completed"},
                "module_3": {"status": "in_progress"},
            }
        }
    }

    print(f"\nScenario:")
    print(f"  Total Assessments: {len(learner_data['performance_analytics']['assessment_history'])}")
    print(f"  Total Study Time: {learner_data['progress']['total_study_time_minutes']} minutes")
    print(f"  Learning Streak: {learner_data['progress']['learning_streak_days']} days")
    print(f"  Modules Started: {len(learner_data['progress']['module_progress'])}")

    engagement = framework.calculate_engagement(learner_data)

    print(f"\nResults:")
    print(f"  ✅ Total Sessions: {engagement.total_sessions}")
    print(f"  ✅ Avg Session Time: {engagement.average_session_time:.1f} minutes")
    print(f"  ✅ Completion Rate: {engagement.completion_rate:.1%}")
    print(f"  ✅ Dropout Rate: {engagement.dropout_rate:.1%}")
    print(f"  ✅ Learning Streak: {engagement.learning_streak_days} days")

    print(f"\nInterpretation:")
    if engagement.completion_rate > 0.8:
        print(f"  🎉 EXCELLENT! High engagement and completion!")
    elif engagement.completion_rate > 0.6:
        print(f"  👍 GOOD! Learners are staying engaged.")
    elif engagement.completion_rate > 0.4:
        print(f"  ⚠️  MODERATE. Some dropout occurring.")
    else:
        print(f"  ❌ POOR. High dropout - improve UX and content.")

    return engagement


def test_ab_testing():
    """Test 4: Run an A/B test experiment."""
    print("\n" + "=" * 70)
    print("TEST 4: A/B TESTING")
    print("=" * 70)

    framework = ABTestFramework(data_dir=Path("data/experiments"))

    # Create experiment
    print("\n1. Creating Experiment...")
    experiment = framework.create_experiment(
        name="Adaptive Difficulty Test",
        description="Testing if adaptive difficulty improves learning outcomes",
        control_variant="fixed_difficulty",
        experimental_variants=["adaptive_difficulty"],
        allocation_ratio={"fixed_difficulty": 0.5, "adaptive_difficulty": 0.5},
        primary_metric="average_score",
    )

    print(f"  ✅ Experiment ID: {experiment.experiment_id}")
    print(f"  ✅ Control: {experiment.control_variant}")
    print(f"  ✅ Experimental: {experiment.experimental_variants[0]}")

    # Start experiment
    framework.start_experiment(experiment.experiment_id)
    print(f"\n2. Experiment started!")

    # Simulate 40 learners
    print(f"\n3. Assigning 40 learners to variants...")
    np.random.seed(42)
    learner_ids = [f"learner_{i:03d}" for i in range(40)]

    assignments = {"fixed_difficulty": [], "adaptive_difficulty": []}

    for learner_id in learner_ids:
        assignment = framework.assign_learner(learner_id, experiment.experiment_id)
        assignments[assignment.variant].append(learner_id)

    print(f"  ✅ Fixed Difficulty: {len(assignments['fixed_difficulty'])} learners")
    print(f"  ✅ Adaptive Difficulty: {len(assignments['adaptive_difficulty'])} learners")

    # Simulate results (adaptive performs 12% better)
    print(f"\n4. Recording results...")

    for learner_id in assignments["fixed_difficulty"]:
        # Control: mean 73, std 10
        score = np.random.normal(73, 10)
        score = max(0, min(100, score))  # Clamp to 0-100
        framework.record_result(learner_id, experiment.experiment_id, score)

    for learner_id in assignments["adaptive_difficulty"]:
        # Experimental: mean 82, std 10 (12% better!)
        score = np.random.normal(82, 10)
        score = max(0, min(100, score))  # Clamp to 0-100
        framework.record_result(learner_id, experiment.experiment_id, score)

    print(f"  ✅ Recorded results for {len(learner_ids)} learners")

    # Analyze results
    print(f"\n5. Analyzing Experiment...")
    analysis = framework.analyze_experiment(experiment.experiment_id)

    print(f"\nResults:")
    print(f"  Total Participants: {analysis['total_participants']}")

    for variant, stats in analysis['variant_statistics'].items():
        print(f"\n  {variant}:")
        print(f"    N: {stats['n']}")
        print(f"    Mean: {stats['mean']:.1f}")
        print(f"    Std: {stats['std']:.1f}")

    for comparison in analysis['statistical_comparisons']:
        print(f"\n  Statistical Comparison:")
        print(f"    Improvement: {comparison['improvement_percentage']:.1f}%")
        print(f"    P-value: {comparison['p_value']:.6f}")
        print(f"    Effect Size (Cohen's d): {comparison['effect_size_cohens_d']:.2f}")
        print(f"    Statistically Significant: {'✅ YES' if comparison['statistically_significant'] else '❌ NO'}")
        print(f"\n  {comparison['interpretation']}")

    print(f"\n  RECOMMENDATION:")
    print(f"  {analysis['recommendation']}")

    # Stop experiment
    framework.stop_experiment(experiment.experiment_id)

    return analysis


def test_baseline_comparison():
    """Test 5: Compare to a baseline system."""
    print("\n" + "=" * 70)
    print("TEST 5: BASELINE COMPARISON")
    print("=" * 70)

    framework = EvaluationFramework(data_dir=Path("data/evaluation"))

    # Simulate data
    np.random.seed(42)

    # Your personalized system: mean 83, std 9
    your_system_scores = list(np.random.normal(83, 9, 30))
    your_system_scores = [max(0, min(100, s)) for s in your_system_scores]

    # Traditional classroom: mean 72, std 12
    traditional_scores = list(np.random.normal(72, 12, 30))
    traditional_scores = [max(0, min(100, s)) for s in traditional_scores]

    print(f"\nScenario:")
    print(f"  Your System: {len(your_system_scores)} learners")
    print(f"  Traditional Classroom: {len(traditional_scores)} learners")

    comparison = framework.compare_to_baseline(
        system_scores=your_system_scores,
        baseline_scores=traditional_scores,
        baseline_name="Traditional Classroom"
    )

    print(f"\nResults:")
    print(f"  Your System Mean: {comparison['system_mean']:.1f}")
    print(f"  Baseline Mean: {comparison['baseline_mean']:.1f}")
    print(f"  Improvement: {comparison['improvement_percentage']:.1f}%")
    print(f"  P-value: {comparison['p_value']:.6f}")
    print(f"  Effect Size: {comparison['effect_size_cohens_d']:.2f}")
    print(f"  Statistically Significant: {'✅ YES' if comparison['statistically_significant'] else '❌ NO'}")

    print(f"\nInterpretation:")
    print(f"  {comparison['interpretation']}")

    return comparison


def test_sample_size_calculation():
    """Test 6: Calculate required sample size for an experiment."""
    print("\n" + "=" * 70)
    print("TEST 6: SAMPLE SIZE CALCULATION")
    print("=" * 70)

    framework = ABTestFramework(data_dir=Path("data/experiments"))

    print(f"\nScenario:")
    print(f"  Current system average: 75%")
    print(f"  Standard deviation: 12%")
    print(f"  Want to detect: 10% improvement")
    print(f"  Confidence level: 95% (α = 0.05)")
    print(f"  Statistical power: 80%")

    sample_size = framework.calculate_sample_size(
        baseline_mean=75.0,
        baseline_std=12.0,
        minimum_detectable_effect=10.0,
        alpha=0.05,
        power=0.80,
    )

    print(f"\nResults:")
    print(f"  ✅ Sample size per group: {sample_size['sample_size_per_group']}")
    print(f"  ✅ Total sample size: {sample_size['total_sample_size']}")
    print(f"\nRecommendation:")
    print(f"  {sample_size['recommendation']}")

    print(f"\nWhat this means:")
    print(f"  To reliably detect a 10% improvement, you need to enroll")
    print(f"  at least {sample_size['sample_size_per_group']} learners in EACH group")
    print(f"  (control and experimental).")

    return sample_size


def main():
    """Run all evaluation tests."""
    print("\n" + "=" * 70)
    print(" EVALUATION FRAMEWORK - COMPREHENSIVE TEST")
    print("=" * 70)
    print("\nThis will demonstrate all evaluation capabilities:")
    print("  1. Learning Gains (How much do learners improve?)")
    print("  2. Retention (Do they remember over time?)")
    print("  3. Engagement (Are they staying engaged?)")
    print("  4. A/B Testing (Does feature X improve outcomes?)")
    print("  5. Baseline Comparison (Are you better than alternatives?)")
    print("  6. Sample Size (How many learners do you need?)")

    try:
        # Run all tests
        gain = test_learning_gains()
        retention = test_retention()
        engagement = test_engagement()
        ab_result = test_ab_testing()
        baseline = test_baseline_comparison()
        sample_size = test_sample_size_calculation()

        # Summary
        print("\n" + "=" * 70)
        print(" SUMMARY")
        print("=" * 70)

        print(f"\n✅ ALL TESTS COMPLETED SUCCESSFULLY!")

        print(f"\nKey Findings:")
        print(f"  1. Learning Gain: {gain.normalized_gain:.2f} (Hake's normalized)")
        print(f"  2. Retention (30d): {retention.retention_rate:.1%}")
        print(f"  3. Completion Rate: {engagement.completion_rate:.1%}")
        print(f"  4. A/B Test: Adaptive {'WINS' if ab_result['statistical_comparisons'][0]['statistically_significant'] else 'inconclusive'}")
        print(f"  5. Baseline: {baseline['improvement_percentage']:.1f}% improvement over traditional")
        print(f"  6. Need {sample_size['sample_size_per_group']} learners per group for experiments")

        print(f"\n📊 Evaluation data saved to:")
        print(f"  - data/evaluation/")
        print(f"  - data/experiments/")

        print(f"\n🎉 You now know how to scientifically evaluate your system!")
        print(f"   Use these methods with real learner data to prove effectiveness.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
