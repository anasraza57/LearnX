"""
Evaluation Metrics Module

Provides scientific evaluation methods to objectively assess the quality
and effectiveness of the personalized learning system.

This module implements:
1. Learning Gain Metrics (Pre/Post test comparison)
2. Retention Metrics (Long-term knowledge retention)
3. Engagement Metrics (Time, completion rates, streaks)
4. Personalization Effectiveness (Adaptive vs. Non-adaptive comparison)
5. Content Quality Metrics (Citation quality, source diversity)
6. System Performance Metrics (Response time, accuracy)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
from scipy import stats
import json
from pathlib import Path


# ==================== Data Classes ====================

@dataclass
class LearningGainMetrics:
    """Measures improvement from pre-test to post-test."""
    learner_id: str
    module_id: str
    pre_test_score: float  # 0-100
    post_test_score: float  # 0-100
    absolute_gain: float  # post - pre
    relative_gain: float  # (post - pre) / pre
    normalized_gain: float  # Hake's normalized gain
    timestamp: str

    @staticmethod
    def calculate(pre_score: float, post_score: float, max_score: float = 100.0) -> float:
        """
        Calculate Hake's normalized learning gain.

        Formula: g = (post - pre) / (max - pre)

        Interpretation:
        - g > 0.7: High gain
        - 0.3 < g < 0.7: Medium gain
        - g < 0.3: Low gain
        """
        if pre_score >= max_score:
            return 0.0
        return (post_score - pre_score) / (max_score - pre_score)


@dataclass
class RetentionMetrics:
    """Measures long-term knowledge retention."""
    learner_id: str
    module_id: str
    initial_score: float  # Score immediately after learning
    retention_score: float  # Score after time interval
    days_elapsed: int
    retention_rate: float  # retention_score / initial_score
    forgetting_rate: float  # 1 - retention_rate
    timestamp: str


@dataclass
class EngagementMetrics:
    """Measures learner engagement with the system."""
    learner_id: str
    total_sessions: int
    total_time_minutes: float
    average_session_time: float
    completion_rate: float  # % of started modules completed
    dropout_rate: float  # % of started modules abandoned
    learning_streak_days: int
    questions_asked: int  # Interactive Q&A count
    hints_requested: int
    timestamp: str


@dataclass
class PersonalizationEffectiveness:
    """Compares personalized vs. non-personalized learning outcomes."""
    experimental_group_avg: float  # With personalization
    control_group_avg: float  # Without personalization
    effect_size: float  # Cohen's d
    p_value: float  # Statistical significance
    improvement_percentage: float  # % improvement from personalization
    confidence_interval: Tuple[float, float]  # 95% CI
    sample_size_experimental: int
    sample_size_control: int
    timestamp: str


@dataclass
class ContentQualityMetrics:
    """Evaluates quality of teaching content."""
    session_id: str
    citation_count: int
    source_diversity: int  # Number of unique sources
    confidence_score: float  # RAG confidence
    response_relevance: float  # 0-1, requires human/automated evaluation
    source_authority_score: float  # Quality of sources
    timestamp: str


@dataclass
class SystemPerformanceMetrics:
    """Measures technical performance of the system."""
    operation: str  # "teaching", "assessment", "grading"
    response_time_ms: float
    accuracy: float  # For grading accuracy
    throughput: float  # Operations per second
    error_rate: float  # % of failed operations
    timestamp: str


# ==================== Evaluation Framework ====================

class EvaluationFramework:
    """
    Main evaluation framework for scientific assessment of the learning system.
    """

    def __init__(self, data_dir: Path = Path("data/evaluation")):
        """
        Initialize evaluation framework.

        Args:
            data_dir: Directory to store evaluation data
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ==================== Learning Gain Evaluation ====================

    def calculate_learning_gain(
        self,
        learner_id: str,
        module_id: str,
        pre_test_score: float,
        post_test_score: float,
    ) -> LearningGainMetrics:
        """
        Calculate learning gain metrics for a learner on a module.

        Args:
            learner_id: Learner identifier
            module_id: Module identifier
            pre_test_score: Score before learning (0-100)
            post_test_score: Score after learning (0-100)

        Returns:
            LearningGainMetrics object

        Raises:
            ValueError: If scores are not in [0, 100] range
        """
        # FIX #2: Score input validation
        for score, name in [(pre_test_score, "pre_test"), (post_test_score, "post_test")]:
            if not (0.0 <= score <= 100.0):
                raise ValueError(f"{name}_score must be in [0, 100], got {score}")
        absolute_gain = post_test_score - pre_test_score
        relative_gain = absolute_gain / pre_test_score if pre_test_score > 0 else 0.0
        normalized_gain = LearningGainMetrics.calculate(pre_test_score, post_test_score)

        metrics = LearningGainMetrics(
            learner_id=learner_id,
            module_id=module_id,
            pre_test_score=pre_test_score,
            post_test_score=post_test_score,
            absolute_gain=absolute_gain,
            relative_gain=relative_gain,
            normalized_gain=normalized_gain,
            timestamp=datetime.now().isoformat(),
        )

        # Save metrics
        self._save_metrics("learning_gain", metrics)

        return metrics

    def analyze_learning_gains(
        self,
        gains: List[LearningGainMetrics]
    ) -> Dict[str, Any]:
        """
        Analyze learning gains across multiple learners.

        Args:
            gains: List of LearningGainMetrics

        Returns:
            Statistical analysis of learning gains
        """
        if not gains:
            return {"error": "No data provided"}

        normalized_gains = [g.normalized_gain for g in gains]
        absolute_gains = [g.absolute_gain for g in gains]

        return {
            "n": len(gains),
            "normalized_gain": {
                "mean": np.mean(normalized_gains),
                "median": np.median(normalized_gains),
                "std": np.std(normalized_gains),
                "min": np.min(normalized_gains),
                "max": np.max(normalized_gains),
                "interpretation": self._interpret_normalized_gain(np.mean(normalized_gains)),
            },
            "absolute_gain": {
                "mean": np.mean(absolute_gains),
                "median": np.median(absolute_gains),
                "std": np.std(absolute_gains),
            },
            "high_gain_percentage": sum(1 for g in normalized_gains if g > 0.7) / len(gains) * 100,
            "medium_gain_percentage": sum(1 for g in normalized_gains if 0.3 <= g <= 0.7) / len(gains) * 100,
            "low_gain_percentage": sum(1 for g in normalized_gains if g < 0.3) / len(gains) * 100,
        }

    @staticmethod
    def _interpret_normalized_gain(gain: float) -> str:
        """Interpret normalized gain using Hake's scale."""
        if gain > 0.7:
            return "High gain - Excellent learning effectiveness"
        elif gain > 0.3:
            return "Medium gain - Moderate learning effectiveness"
        else:
            return "Low gain - Poor learning effectiveness, needs improvement"

    # ==================== Retention Evaluation ====================

    def calculate_retention(
        self,
        learner_id: str,
        module_id: str,
        initial_score: float,
        retention_score: float,
        days_elapsed: int,
    ) -> RetentionMetrics:
        """
        Calculate knowledge retention metrics.

        Args:
            learner_id: Learner identifier
            module_id: Module identifier
            initial_score: Score immediately after learning
            retention_score: Score after time interval
            days_elapsed: Days between initial and retention test

        Returns:
            RetentionMetrics object
        """
        retention_rate = retention_score / initial_score if initial_score > 0 else 0.0
        forgetting_rate = 1.0 - retention_rate

        metrics = RetentionMetrics(
            learner_id=learner_id,
            module_id=module_id,
            initial_score=initial_score,
            retention_score=retention_score,
            days_elapsed=days_elapsed,
            retention_rate=retention_rate,
            forgetting_rate=forgetting_rate,
            timestamp=datetime.now().isoformat(),
        )

        self._save_metrics("retention", metrics)

        return metrics

    def analyze_retention_curve(
        self,
        retention_data: List[RetentionMetrics]
    ) -> Dict[str, Any]:
        """
        Analyze retention curve (Ebbinghaus forgetting curve).

        Args:
            retention_data: List of RetentionMetrics at different time points

        Returns:
            Retention analysis with forgetting curve parameters
        """
        if not retention_data:
            return {"error": "No data provided"}

        # Sort by days elapsed
        sorted_data = sorted(retention_data, key=lambda x: x.days_elapsed)

        days = [r.days_elapsed for r in sorted_data]
        rates = [r.retention_rate for r in sorted_data]

        return {
            "n": len(retention_data),
            "retention_rate_by_time": [
                {"days": d, "retention_rate": r} for d, r in zip(days, rates)
            ],
            "average_retention_rate": np.mean(rates),
            "retention_at_7_days": self._interpolate_retention(sorted_data, 7),
            "retention_at_30_days": self._interpolate_retention(sorted_data, 30),
            "retention_at_90_days": self._interpolate_retention(sorted_data, 90),
            "interpretation": self._interpret_retention(np.mean(rates)),
        }

    @staticmethod
    def _interpolate_retention(data: List[RetentionMetrics], target_days: int) -> Optional[float]:
        """Interpolate retention rate at target days."""
        if not data:
            return None

        # Find closest data points
        before = [r for r in data if r.days_elapsed <= target_days]
        after = [r for r in data if r.days_elapsed >= target_days]

        if not before or not after:
            return None

        before_point = before[-1]
        after_point = after[0]

        if before_point.days_elapsed == after_point.days_elapsed:
            return before_point.retention_rate

        # Linear interpolation
        slope = (after_point.retention_rate - before_point.retention_rate) / \
                (after_point.days_elapsed - before_point.days_elapsed)
        interpolated = before_point.retention_rate + slope * (target_days - before_point.days_elapsed)

        return interpolated

    @staticmethod
    def _interpret_retention(rate: float) -> str:
        """Interpret retention rate."""
        if rate > 0.8:
            return "Excellent retention - Long-term learning achieved"
        elif rate > 0.6:
            return "Good retention - Knowledge persisting well"
        elif rate > 0.4:
            return "Moderate retention - Some forgetting occurring"
        else:
            return "Poor retention - Significant forgetting, review needed"

    # ==================== Engagement Evaluation ====================

    def calculate_engagement(
        self,
        learner_data: Dict[str, Any]
    ) -> EngagementMetrics:
        """
        Calculate engagement metrics from learner profile.

        Args:
            learner_data: Learner profile dictionary

        Returns:
            EngagementMetrics object
        """
        progress = learner_data.get("progress", {})
        analytics = learner_data.get("performance_analytics", {})

        # FIX #1: Handle both module_progress dict and simple counters
        module_progress = progress.get("module_progress")
        if isinstance(module_progress, dict) and module_progress:
            # New format: {module_id: {status: "completed", ...}}
            total_modules_started = len(module_progress)
            completed_modules = sum(1 for m in module_progress.values() if m.get("status") == "completed")
        else:
            # Fallback to simple counters if module_progress is missing/empty
            total_modules_started = progress.get("modules_total", 0)
            completed_modules = progress.get("modules_completed", 0)

        completion_rate = completed_modules / total_modules_started if total_modules_started > 0 else 0.0
        dropout_rate = 1.0 - completion_rate

        assessment_history = analytics.get("assessment_history", [])
        total_sessions = len(assessment_history)
        total_time_minutes = progress.get("total_study_time_minutes", 0)
        average_session_time = total_time_minutes / total_sessions if total_sessions > 0 else 0.0

        metrics = EngagementMetrics(
            learner_id=learner_data.get("learner_id", "unknown"),
            total_sessions=total_sessions,
            total_time_minutes=total_time_minutes,
            average_session_time=average_session_time,
            completion_rate=completion_rate,
            dropout_rate=dropout_rate,
            learning_streak_days=progress.get("learning_streak_days", 0),
            questions_asked=0,  # Would need to track separately
            hints_requested=0,  # Would need to track separately
            timestamp=datetime.now().isoformat(),
        )

        self._save_metrics("engagement", metrics)

        return metrics

    def analyze_engagement(
        self,
        engagement_data: List[EngagementMetrics]
    ) -> Dict[str, Any]:
        """
        Analyze engagement metrics across learners.

        Args:
            engagement_data: List of EngagementMetrics

        Returns:
            Engagement analysis
        """
        if not engagement_data:
            return {"error": "No data provided"}

        completion_rates = [e.completion_rate for e in engagement_data]
        session_times = [e.average_session_time for e in engagement_data]
        streaks = [e.learning_streak_days for e in engagement_data]

        return {
            "n": len(engagement_data),
            "completion_rate": {
                "mean": np.mean(completion_rates),
                "median": np.median(completion_rates),
                "std": np.std(completion_rates),
            },
            "average_session_time_minutes": {
                "mean": np.mean(session_times),
                "median": np.median(session_times),
                "std": np.std(session_times),
            },
            "learning_streak_days": {
                "mean": np.mean(streaks),
                "median": np.median(streaks),
                "max": np.max(streaks),
            },
            "high_engagement_percentage": sum(1 for e in completion_rates if e > 0.8) / len(engagement_data) * 100,
            "dropout_risk_percentage": sum(1 for e in completion_rates if e < 0.3) / len(engagement_data) * 100,
        }

    # ==================== A/B Testing for Personalization ====================

    def compare_personalization_effectiveness(
        self,
        experimental_group: List[float],  # Scores with personalization
        control_group: List[float],  # Scores without personalization
        alpha: float = 0.05,
    ) -> PersonalizationEffectiveness:
        """
        Compare learning outcomes between personalized and non-personalized groups.

        Uses independent t-test and Cohen's d effect size.

        Args:
            experimental_group: Scores from group with personalization
            control_group: Scores from group without personalization
            alpha: Significance level (default 0.05)

        Returns:
            PersonalizationEffectiveness metrics
        """
        if len(experimental_group) < 2 or len(control_group) < 2:
            raise ValueError("Need at least 2 samples in each group")

        # Calculate means
        exp_mean = np.mean(experimental_group)
        ctrl_mean = np.mean(control_group)

        # Perform independent t-test
        t_stat, p_value = stats.ttest_ind(experimental_group, control_group)

        # Calculate Cohen's d (effect size)
        # Using weighted pooled standard deviation (Cohen, 1988)
        n_exp = len(experimental_group)
        n_ctrl = len(control_group)
        sd_exp = np.std(experimental_group, ddof=1)
        sd_ctrl = np.std(control_group, ddof=1)
        pooled_std = np.sqrt(((n_exp - 1) * sd_exp**2 + (n_ctrl - 1) * sd_ctrl**2) / (n_exp + n_ctrl - 2))
        cohens_d = (exp_mean - ctrl_mean) / pooled_std if pooled_std > 0 else 0.0

        # Calculate 95% confidence interval for difference
        diff = exp_mean - ctrl_mean
        se_diff = pooled_std * np.sqrt(1/len(experimental_group) + 1/len(control_group))
        ci_lower = diff - 1.96 * se_diff
        ci_upper = diff + 1.96 * se_diff

        # Calculate improvement percentage
        improvement = (exp_mean - ctrl_mean) / ctrl_mean * 100 if ctrl_mean > 0 else 0.0

        metrics = PersonalizationEffectiveness(
            experimental_group_avg=exp_mean,
            control_group_avg=ctrl_mean,
            effect_size=cohens_d,
            p_value=p_value,
            improvement_percentage=improvement,
            confidence_interval=(ci_lower, ci_upper),
            sample_size_experimental=len(experimental_group),
            sample_size_control=len(control_group),
            timestamp=datetime.now().isoformat(),
        )

        self._save_metrics("ab_test", metrics)

        return metrics

    @staticmethod
    def interpret_ab_test(metrics: PersonalizationEffectiveness) -> Dict[str, str]:
        """
        Interpret A/B test results.

        Args:
            metrics: PersonalizationEffectiveness object

        Returns:
            Human-readable interpretation
        """
        # Statistical significance
        if metrics.p_value < 0.05:
            significance = "Statistically significant (p < 0.05)"
        else:
            significance = "Not statistically significant (p >= 0.05)"

        # Effect size interpretation (Cohen's d)
        abs_d = abs(metrics.effect_size)
        if abs_d < 0.2:
            effect_size_interp = "Negligible effect"
        elif abs_d < 0.5:
            effect_size_interp = "Small effect"
        elif abs_d < 0.8:
            effect_size_interp = "Medium effect"
        else:
            effect_size_interp = "Large effect"

        # Overall interpretation
        if metrics.p_value < 0.05 and metrics.effect_size > 0.5:
            overall = "✅ Personalization is EFFECTIVE - significant improvement with medium-to-large effect"
        elif metrics.p_value < 0.05 and metrics.effect_size > 0:
            overall = "⚠️ Personalization shows SOME benefit - significant but small effect"
        else:
            overall = "❌ Personalization NOT proven effective - no significant benefit found"

        return {
            "statistical_significance": significance,
            "effect_size_interpretation": effect_size_interp,
            "improvement": f"{metrics.improvement_percentage:.1f}%",
            "overall_conclusion": overall,
        }

    # ==================== Content Quality Evaluation ====================

    def evaluate_content_quality(
        self,
        session_data: Dict[str, Any]
    ) -> ContentQualityMetrics:
        """
        Evaluate quality of teaching content from a session.

        Args:
            session_data: Teaching session data with citations

        Returns:
            ContentQualityMetrics object
        """
        citations = session_data.get("citations", [])

        # Count unique sources
        sources = set()
        for citation in citations:
            source = citation.get("source", "")
            if source:
                sources.add(source)

        metrics = ContentQualityMetrics(
            session_id=session_data.get("teaching_session_id", "unknown"),
            citation_count=len(citations),
            source_diversity=len(sources),
            confidence_score=session_data.get("confidence", 0.5),
            response_relevance=0.0,  # Requires manual evaluation
            source_authority_score=0.0,  # Requires manual evaluation
            timestamp=datetime.now().isoformat(),
        )

        self._save_metrics("content_quality", metrics)

        return metrics

    # ==================== Baseline Comparison ====================

    def compare_to_baseline(
        self,
        system_scores: List[float],
        baseline_scores: List[float],
        baseline_name: str = "Traditional Learning"
    ) -> Dict[str, Any]:
        """
        Compare system performance to a baseline (e.g., traditional learning).

        Args:
            system_scores: Scores from your system
            baseline_scores: Scores from baseline system
            baseline_name: Name of the baseline for reporting

        Returns:
            Comparison analysis
        """
        if len(system_scores) < 2 or len(baseline_scores) < 2:
            return {"error": "Insufficient data for comparison"}

        # Statistical comparison
        t_stat, p_value = stats.ttest_ind(system_scores, baseline_scores)

        system_mean = np.mean(system_scores)
        baseline_mean = np.mean(baseline_scores)

        improvement = (system_mean - baseline_mean) / baseline_mean * 100 if baseline_mean > 0 else 0.0

        # Effect size (Cohen's d with weighted pooled standard deviation)
        n_sys = len(system_scores)
        n_base = len(baseline_scores)
        sd_sys = np.std(system_scores, ddof=1)
        sd_base = np.std(baseline_scores, ddof=1)
        pooled_std = np.sqrt(((n_sys - 1) * sd_sys**2 + (n_base - 1) * sd_base**2) / (n_sys + n_base - 2))
        cohens_d = (system_mean - baseline_mean) / pooled_std if pooled_std > 0 else 0.0

        return {
            "baseline": baseline_name,
            "system_mean": system_mean,
            "baseline_mean": baseline_mean,
            "improvement_percentage": improvement,
            "p_value": p_value,
            "statistically_significant": p_value < 0.05,
            "effect_size_cohens_d": cohens_d,
            "interpretation": self._interpret_baseline_comparison(improvement, p_value, cohens_d),
        }

    @staticmethod
    def _interpret_baseline_comparison(improvement: float, p_value: float, cohens_d: float) -> str:
        """Interpret baseline comparison results."""
        if p_value < 0.05 and cohens_d > 0.5 and improvement > 10:
            return f"✅ System significantly OUTPERFORMS baseline by {improvement:.1f}% with medium-to-large effect"
        elif p_value < 0.05 and improvement > 0:
            return f"⚠️ System shows SOME improvement over baseline ({improvement:.1f}%) but effect is small"
        elif p_value >= 0.05:
            return "❌ No significant difference from baseline - system needs improvement"
        else:
            return f"❌ System UNDERPERFORMS baseline by {abs(improvement):.1f}%"

    # ==================== Helper Methods ====================

    def _save_metrics(self, metric_type: str, metrics: Any) -> None:
        """Save metrics to disk for later analysis with schema versioning."""
        metrics_dir = self.data_dir / metric_type
        metrics_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{metric_type}_{timestamp}.json"
        filepath = metrics_dir / filename

        # Convert dataclass to dict
        if hasattr(metrics, "__dict__"):
            data = metrics.__dict__.copy()
        else:
            data = metrics.copy() if isinstance(metrics, dict) else metrics

        # FIX #8: Add schema version and metric type for ETL safety
        wrapped_data = {
            "schema_version": "1.0",
            "metric_type": metric_type,
            "saved_at": datetime.now().isoformat(),
            "data": data
        }

        with open(filepath, "w") as f:
            json.dump(wrapped_data, f, indent=2)

    def load_metrics(self, metric_type: str) -> List[Dict[str, Any]]:
        """Load all metrics of a given type from disk, handling both old and new formats."""
        metrics_dir = self.data_dir / metric_type
        if not metrics_dir.exists():
            return []

        all_metrics = []
        for filepath in metrics_dir.glob("*.json"):
            with open(filepath, "r") as f:
                loaded = json.load(f)

                # Handle new wrapped format (with schema_version)
                if isinstance(loaded, dict) and "schema_version" in loaded:
                    all_metrics.append(loaded["data"])
                else:
                    # Old format: direct data
                    all_metrics.append(loaded)

        return all_metrics

    # ==================== Comprehensive Report ====================

    def generate_evaluation_report(
        self,
        learner_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive evaluation report.

        Args:
            learner_ids: Optional list of learner IDs to include (None = all)

        Returns:
            Complete evaluation report with all metrics
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "learner_ids": learner_ids or "all",
            "metrics": {},
        }

        # Load and analyze all metric types
        metric_types = ["learning_gain", "retention", "engagement", "ab_test", "content_quality"]

        for metric_type in metric_types:
            metrics_data = self.load_metrics(metric_type)

            if learner_ids:
                # Filter by learner IDs
                metrics_data = [m for m in metrics_data if m.get("learner_id") in learner_ids]

            report["metrics"][metric_type] = {
                "count": len(metrics_data),
                "data": metrics_data,
            }

        return report
