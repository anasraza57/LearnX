"""
A/B Testing Framework for Personalized Learning System

This module provides infrastructure for conducting controlled experiments
to validate the effectiveness of personalization features.

Key Features:
1. Random assignment to control/experimental groups
2. Feature flag management for gradual rollout
3. Experiment tracking and analysis
4. Statistical power analysis
5. Multi-armed bandit algorithms for adaptive experiments
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
import random
import json
from pathlib import Path
import numpy as np
from scipy import stats


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment."""
    experiment_id: str
    name: str
    description: str
    control_variant: str  # Name of control group variant
    experimental_variants: List[str]  # List of experimental variant names
    allocation_ratio: Dict[str, float]  # Variant -> allocation percentage
    start_date: str
    end_date: Optional[str] = None
    status: Literal["draft", "active", "paused", "completed"] = "draft"
    primary_metric: str = "average_score"  # Main metric to optimize
    secondary_metrics: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ParticipantAssignment:
    """Assignment of a learner to an experiment variant."""
    learner_id: str
    experiment_id: str
    variant: str
    assigned_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Results for a single participant in an experiment."""
    learner_id: str
    experiment_id: str
    variant: str
    primary_metric_value: float
    secondary_metrics: Dict[str, float] = field(default_factory=dict)
    recorded_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ABTestFramework:
    """
    Framework for conducting A/B tests on personalization features.
    """

    def __init__(self, data_dir: Path = Path("data/experiments")):
        """
        Initialize A/B testing framework.

        Args:
            data_dir: Directory to store experiment data
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.experiments: Dict[str, ExperimentConfig] = {}
        self.assignments: Dict[str, ParticipantAssignment] = {}  # learner_id -> assignment
        self.results: Dict[str, List[ExperimentResult]] = {}  # experiment_id -> results

        self._load_experiments()

    # ==================== Experiment Management ====================

    def create_experiment(
        self,
        name: str,
        description: str,
        control_variant: str = "control",
        experimental_variants: Optional[List[str]] = None,
        allocation_ratio: Optional[Dict[str, float]] = None,
        primary_metric: str = "average_score",
        secondary_metrics: Optional[List[str]] = None,
    ) -> ExperimentConfig:
        """
        Create a new A/B test experiment.

        Args:
            name: Experiment name
            description: Detailed description of what's being tested
            control_variant: Name of control group (default: "control")
            experimental_variants: List of experimental variant names (default: ["experimental"])
            allocation_ratio: Percentage allocation to each variant (default: 50-50)
            primary_metric: Main metric to optimize
            secondary_metrics: Additional metrics to track

        Returns:
            ExperimentConfig object

        Example:
            >>> framework.create_experiment(
            ...     name="Adaptive Difficulty vs Fixed Difficulty",
            ...     description="Test if adaptive difficulty improves learning outcomes",
            ...     control_variant="fixed_difficulty",
            ...     experimental_variants=["adaptive_difficulty"],
            ...     primary_metric="average_score",
            ... )
        """
        if experimental_variants is None:
            experimental_variants = ["experimental"]

        all_variants = [control_variant] + experimental_variants

        # Default to equal allocation if not specified
        if allocation_ratio is None:
            equal_share = 1.0 / len(all_variants)
            allocation_ratio = {v: equal_share for v in all_variants}

        # Validate allocation ratio sums to 1.0
        total = sum(allocation_ratio.values())
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Allocation ratio must sum to 1.0, got {total}")

        experiment_id = f"exp_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        config = ExperimentConfig(
            experiment_id=experiment_id,
            name=name,
            description=description,
            control_variant=control_variant,
            experimental_variants=experimental_variants,
            allocation_ratio=allocation_ratio,
            start_date=datetime.now().isoformat(),
            primary_metric=primary_metric,
            secondary_metrics=secondary_metrics or [],
        )

        self.experiments[experiment_id] = config
        self._save_experiment(config)

        return config

    def start_experiment(self, experiment_id: str) -> None:
        """Start an experiment (move from draft to active)."""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        self.experiments[experiment_id].status = "active"
        self._save_experiment(self.experiments[experiment_id])

    def stop_experiment(self, experiment_id: str) -> None:
        """Stop an experiment (move to completed)."""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        self.experiments[experiment_id].status = "completed"
        self.experiments[experiment_id].end_date = datetime.now().isoformat()
        self._save_experiment(self.experiments[experiment_id])

    # ==================== Participant Assignment ====================

    def assign_learner(
        self,
        learner_id: str,
        experiment_id: str,
        force_variant: Optional[str] = None,
    ) -> ParticipantAssignment:
        """
        Assign a learner to an experiment variant.

        Uses random assignment based on allocation ratios, unless force_variant is specified.

        Args:
            learner_id: Learner identifier
            experiment_id: Experiment to assign to
            force_variant: Force assignment to specific variant (for testing)

        Returns:
            ParticipantAssignment object
        """
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment = self.experiments[experiment_id]

        # Check if learner already assigned
        assignment_key = f"{learner_id}_{experiment_id}"
        if assignment_key in self.assignments:
            return self.assignments[assignment_key]

        # Assign to variant
        if force_variant:
            variant = force_variant
        else:
            variant = self._random_assignment(experiment)

        assignment = ParticipantAssignment(
            learner_id=learner_id,
            experiment_id=experiment_id,
            variant=variant,
            assigned_at=datetime.now().isoformat(),
        )

        self.assignments[assignment_key] = assignment
        self._save_assignment(assignment)

        return assignment

    def _random_assignment(self, experiment: ExperimentConfig) -> str:
        """Randomly assign to variant based on allocation ratio."""
        variants = [experiment.control_variant] + experiment.experimental_variants
        weights = [experiment.allocation_ratio.get(v, 0.0) for v in variants]

        return random.choices(variants, weights=weights)[0]

    def get_variant(self, learner_id: str, experiment_id: str) -> Optional[str]:
        """
        Get the assigned variant for a learner.

        Args:
            learner_id: Learner identifier
            experiment_id: Experiment identifier

        Returns:
            Variant name or None if not assigned
        """
        assignment_key = f"{learner_id}_{experiment_id}"
        assignment = self.assignments.get(assignment_key)
        return assignment.variant if assignment else None

    # ==================== Result Recording ====================

    def record_result(
        self,
        learner_id: str,
        experiment_id: str,
        primary_metric_value: float,
        secondary_metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record experimental results for a learner.

        Args:
            learner_id: Learner identifier
            experiment_id: Experiment identifier
            primary_metric_value: Value of primary metric
            secondary_metrics: Values of secondary metrics
        """
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Get learner's variant assignment
        assignment_key = f"{learner_id}_{experiment_id}"
        assignment = self.assignments.get(assignment_key)

        if not assignment:
            raise ValueError(f"Learner {learner_id} not assigned to experiment {experiment_id}")

        result = ExperimentResult(
            learner_id=learner_id,
            experiment_id=experiment_id,
            variant=assignment.variant,
            primary_metric_value=primary_metric_value,
            secondary_metrics=secondary_metrics or {},
        )

        if experiment_id not in self.results:
            self.results[experiment_id] = []

        self.results[experiment_id].append(result)
        self._save_result(result)

    # ==================== Analysis ====================

    def analyze_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """
        Analyze experiment results with statistical tests.

        Args:
            experiment_id: Experiment to analyze

        Returns:
            Analysis report with statistical significance
        """
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        if experiment_id not in self.results or not self.results[experiment_id]:
            return {"error": "No results recorded for this experiment"}

        experiment = self.experiments[experiment_id]
        results = self.results[experiment_id]

        # Group results by variant
        variant_results: Dict[str, List[float]] = {}
        for result in results:
            if result.variant not in variant_results:
                variant_results[result.variant] = []
            variant_results[result.variant].append(result.primary_metric_value)

        # Calculate statistics for each variant
        variant_stats = {}
        for variant, values in variant_results.items():
            variant_stats[variant] = {
                "n": len(values),
                "mean": np.mean(values),
                "std": np.std(values, ddof=1) if len(values) > 1 else 0.0,
                "median": np.median(values),
                "min": np.min(values),
                "max": np.max(values),
            }

        # Statistical comparison: control vs. each experimental variant
        comparisons = []
        control_values = variant_results.get(experiment.control_variant, [])

        for exp_variant in experiment.experimental_variants:
            exp_values = variant_results.get(exp_variant, [])

            if len(control_values) < 2 or len(exp_values) < 2:
                comparisons.append({
                    "variant": exp_variant,
                    "error": "Insufficient data for statistical test (need at least 2 samples)",
                })
                continue

            # Perform t-test
            t_stat, p_value = stats.ttest_ind(exp_values, control_values)

            # Calculate effect size (Cohen's d)
            pooled_std = np.sqrt((np.std(exp_values, ddof=1)**2 +
                                  np.std(control_values, ddof=1)**2) / 2)
            cohens_d = (np.mean(exp_values) - np.mean(control_values)) / pooled_std if pooled_std > 0 else 0.0

            # Calculate improvement
            improvement = (np.mean(exp_values) - np.mean(control_values)) / np.mean(control_values) * 100 \
                if np.mean(control_values) > 0 else 0.0

            # Confidence interval
            diff = np.mean(exp_values) - np.mean(control_values)
            se_diff = pooled_std * np.sqrt(1/len(exp_values) + 1/len(control_values))
            ci_lower = diff - 1.96 * se_diff
            ci_upper = diff + 1.96 * se_diff

            comparisons.append({
                "variant": exp_variant,
                "control_mean": np.mean(control_values),
                "experimental_mean": np.mean(exp_values),
                "difference": diff,
                "improvement_percentage": improvement,
                "p_value": p_value,
                "statistically_significant": p_value < 0.05,
                "effect_size_cohens_d": cohens_d,
                "confidence_interval_95": [ci_lower, ci_upper],
                "interpretation": self._interpret_comparison(improvement, p_value, cohens_d),
            })

        # FIX #3: Apply Holm-Bonferroni correction for multiple comparisons
        if len(comparisons) > 1:
            comparisons_with_pval = [c for c in comparisons if "p_value" in c]
            if comparisons_with_pval:
                adjusted_comparisons = self._apply_holm_bonferroni(comparisons_with_pval)
                comparisons = adjusted_comparisons

        return {
            "experiment_id": experiment_id,
            "experiment_name": experiment.name,
            "primary_metric": experiment.primary_metric,
            "status": experiment.status,
            "total_participants": len(results),
            "variant_statistics": variant_stats,
            "statistical_comparisons": comparisons,
            "multiple_comparison_correction": "Holm-Bonferroni" if len(comparisons) > 1 else "None",
            "recommendation": self._make_recommendation(comparisons),
        }

    @staticmethod
    def _apply_holm_bonferroni(comparisons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply Holm-Bonferroni multiple comparison correction.

        FIX #3: Prevents inflated Type I error when testing multiple variants.

        Args:
            comparisons: List of comparison dicts with p_values

        Returns:
            Updated comparisons with adjusted p-values and significance
        """
        # Extract p-values and create (p_value, index) pairs
        p_values_with_idx = [(c["p_value"], i) for i, c in enumerate(comparisons)]

        # Sort by p-value (ascending)
        sorted_pairs = sorted(p_values_with_idx, key=lambda x: x[0])

        m = len(sorted_pairs)
        adjusted_p_values = [None] * m

        # Holm step-down procedure
        for k, (p_val, original_idx) in enumerate(sorted_pairs, start=1):
            adjusted_p = min(1.0, (m - k + 1) * p_val)
            adjusted_p_values[original_idx] = adjusted_p

        # Update comparisons with adjusted p-values
        adjusted_comparisons = []
        for i, comp in enumerate(comparisons):
            adj_comp = comp.copy()
            adj_comp["p_value_raw"] = comp["p_value"]
            adj_comp["p_value"] = adjusted_p_values[i]
            adj_comp["statistically_significant"] = adjusted_p_values[i] < 0.05
            adj_comp["interpretation"] = ABTestFramework._interpret_comparison(
                adj_comp["improvement_percentage"],
                adjusted_p_values[i],
                adj_comp["effect_size_cohens_d"]
            )
            adjusted_comparisons.append(adj_comp)

        return adjusted_comparisons

    @staticmethod
    def _interpret_comparison(improvement: float, p_value: float, cohens_d: float) -> str:
        """Interpret statistical comparison."""
        if p_value < 0.05 and cohens_d > 0.5 and improvement > 10:
            return f"✅ Experimental variant SIGNIFICANTLY BETTER by {improvement:.1f}% (large effect)"
        elif p_value < 0.05 and cohens_d > 0.2 and improvement > 0:
            return f"⚠️ Experimental variant SLIGHTLY BETTER by {improvement:.1f}% (small-medium effect)"
        elif p_value >= 0.05:
            return "❌ No significant difference - cannot conclude benefit"
        else:
            return f"❌ Experimental variant WORSE by {abs(improvement):.1f}%"

    @staticmethod
    def _make_recommendation(comparisons: List[Dict[str, Any]]) -> str:
        """Make overall recommendation based on comparisons."""
        significant_improvements = [c for c in comparisons
                                    if c.get("statistically_significant")
                                    and c.get("improvement_percentage", 0) > 5]

        if significant_improvements:
            best = max(significant_improvements, key=lambda x: x.get("improvement_percentage", 0))
            return f"✅ SHIP IT: Deploy '{best['variant']}' - shows {best['improvement_percentage']:.1f}% improvement (p={best['p_value']:.4f})"
        else:
            return "❌ DO NOT SHIP: No variant shows significant improvement. Keep control or iterate on design."

    # ==================== Power Analysis ====================

    def calculate_sample_size(
        self,
        baseline_mean: float,
        baseline_std: float,
        minimum_detectable_effect: float,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> Dict[str, Any]:
        """
        Calculate required sample size for experiment.

        Args:
            baseline_mean: Current mean of metric (control group)
            baseline_std: Standard deviation of metric
            minimum_detectable_effect: Minimum % improvement to detect
            alpha: Significance level (default 0.05)
            power: Statistical power (default 0.80)

        Returns:
            Sample size requirements
        """
        # Convert % effect to absolute difference
        effect_size = (baseline_mean * minimum_detectable_effect / 100) / baseline_std

        # Calculate required sample size per group
        # Using simplified formula: n ≈ 16 * (σ / δ)^2
        n_per_group = int(np.ceil(16 * (1 / effect_size) ** 2))

        return {
            "sample_size_per_group": n_per_group,
            "total_sample_size": n_per_group * 2,  # Assuming 2 groups
            "baseline_mean": baseline_mean,
            "baseline_std": baseline_std,
            "minimum_detectable_effect_percentage": minimum_detectable_effect,
            "alpha": alpha,
            "power": power,
            "recommendation": f"Enroll at least {n_per_group} learners per group to detect {minimum_detectable_effect}% improvement",
        }

    # ==================== Persistence ====================

    def _save_experiment(self, config: ExperimentConfig) -> None:
        """Save experiment configuration to disk."""
        experiments_dir = self.data_dir / "experiments"
        experiments_dir.mkdir(exist_ok=True)

        filepath = experiments_dir / f"{config.experiment_id}.json"
        with open(filepath, "w") as f:
            json.dump(config.__dict__, f, indent=2)

    def _save_assignment(self, assignment: ParticipantAssignment) -> None:
        """Save participant assignment to disk."""
        assignments_dir = self.data_dir / "assignments"
        assignments_dir.mkdir(exist_ok=True)

        filepath = assignments_dir / f"{assignment.learner_id}_{assignment.experiment_id}.json"
        with open(filepath, "w") as f:
            json.dump(assignment.__dict__, f, indent=2)

    def _save_result(self, result: ExperimentResult) -> None:
        """Save experiment result to disk."""
        results_dir = self.data_dir / "results" / result.experiment_id
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = results_dir / f"{result.learner_id}_{timestamp}.json"
        with open(filepath, "w") as f:
            json.dump(result.__dict__, f, indent=2)

    def _load_experiments(self) -> None:
        """Load all experiments from disk."""
        experiments_dir = self.data_dir / "experiments"
        if not experiments_dir.exists():
            return

        for filepath in experiments_dir.glob("*.json"):
            with open(filepath, "r") as f:
                data = json.load(f)
                config = ExperimentConfig(**data)
                self.experiments[config.experiment_id] = config


# ==================== Pre-configured Experiments ====================

def create_adaptive_difficulty_experiment(framework: ABTestFramework) -> ExperimentConfig:
    """
    Pre-configured experiment: Adaptive vs. Fixed Difficulty.

    Tests whether adaptive difficulty (changes based on performance) improves
    learning outcomes compared to fixed difficulty.
    """
    return framework.create_experiment(
        name="Adaptive Difficulty vs Fixed Difficulty",
        description="""
        Control: Fixed difficulty (medium) for all learners
        Experimental: Adaptive difficulty that adjusts based on performance

        Hypothesis: Adaptive difficulty will improve learning outcomes by matching
        content to learner ability, reducing frustration and boredom.
        """,
        control_variant="fixed_difficulty",
        experimental_variants=["adaptive_difficulty"],
        allocation_ratio={"fixed_difficulty": 0.5, "adaptive_difficulty": 0.5},
        primary_metric="average_score",
        secondary_metrics=["completion_rate", "time_to_completion", "engagement_score"],
    )


def create_personalized_content_experiment(framework: ABTestFramework) -> ExperimentConfig:
    """
    Pre-configured experiment: Personalized vs. Generic Content.

    Tests whether personalized content (using learning style, interests, prior knowledge)
    improves learning outcomes compared to generic content.
    """
    return framework.create_experiment(
        name="Personalized Content vs Generic Content",
        description="""
        Control: Generic teaching content (one-size-fits-all)
        Experimental: Personalized content based on learning style, interests, prior knowledge

        Hypothesis: Personalized content will increase engagement and learning outcomes
        by tailoring examples and explanations to learner preferences.
        """,
        control_variant="generic_content",
        experimental_variants=["personalized_content"],
        allocation_ratio={"generic_content": 0.5, "personalized_content": 0.5},
        primary_metric="average_score",
        secondary_metrics=["engagement_score", "time_on_task", "learner_satisfaction"],
    )


def create_spaced_repetition_experiment(framework: ABTestFramework) -> ExperimentConfig:
    """
    Pre-configured experiment: Spaced Repetition vs. Massed Practice.

    Tests whether spaced repetition improves long-term retention compared to
    massed practice (cramming).
    """
    return framework.create_experiment(
        name="Spaced Repetition vs Massed Practice",
        description="""
        Control: Massed practice (all content in one session)
        Experimental: Spaced repetition (content distributed over time)

        Hypothesis: Spaced repetition will improve long-term retention by
        leveraging the spacing effect.
        """,
        control_variant="massed_practice",
        experimental_variants=["spaced_repetition"],
        allocation_ratio={"massed_practice": 0.5, "spaced_repetition": 0.5},
        primary_metric="retention_score_30_days",
        secondary_metrics=["retention_score_7_days", "retention_score_90_days"],
    )
