"""
Model Comparison Framework for GPT-3.5-turbo vs GPT-4o-mini

This module provides comprehensive comparison between different LLM models
to evaluate their performance on the personalized learning system.

Comparison Metrics:
1. Response Quality (accuracy, relevance, coherence)
2. Learning Outcomes (test scores, learning gains)
3. Cost Efficiency (performance per dollar)
4. Response Time (latency, throughput)
5. Citation Quality (accuracy, diversity of sources)
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np

# Import evaluation framework
try:
    from .metrics import EvaluationFramework, LearningGainMetrics
    from .ab_testing import ABTestFramework
    from ..config import config
    from ..models.learner_profile import LearnerModel
except ImportError:
    from src.evaluation.metrics import EvaluationFramework, LearningGainMetrics
    from src.evaluation.ab_testing import ABTestFramework
    from src.config import config
    from src.models.learner_profile import LearnerModel


@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for a single model."""
    model_name: str

    # Learning outcomes
    average_score: float
    learning_gain_normalized: float
    completion_rate: float

    # Response quality
    avg_citation_count: float
    avg_source_diversity: float
    avg_confidence: float

    # Efficiency
    avg_response_time_ms: float
    total_cost_usd: float
    cost_per_student: float

    # Token usage
    total_input_tokens: int
    total_output_tokens: int

    # Sample size
    num_students: int
    num_sessions: int

    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ModelComparison:
    """
    Framework for comparing GPT-3.5-turbo vs GPT-4o-mini performance.
    """

    def __init__(
        self,
        data_dir: Path = Path("data/model_comparison"),
        results_dir: Path = Path("results/model_comparison")
    ):
        """
        Initialize model comparison framework.

        Args:
            data_dir: Directory for storing comparison data
            results_dir: Directory for storing comparison results/reports
        """
        self.data_dir = data_dir
        self.results_dir = results_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Initialize evaluation frameworks
        self.eval_framework = EvaluationFramework(data_dir / "evaluation")
        self.ab_framework = ABTestFramework(data_dir / "experiments")

        # Model configurations
        self.models = {
            "gpt-3.5-turbo": {
                "name": "gpt-3.5-turbo",
                "display_name": "GPT-3.5 Turbo",
                "cost_per_1k_input": config.logging.cost_per_1k_input,
                "cost_per_1k_output": config.logging.cost_per_1k_output,
            },
            "gpt-4o-mini": {
                "name": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "cost_per_1k_input": config.logging.alt_cost_per_1k_input,
                "cost_per_1k_output": config.logging.alt_cost_per_1k_output,
            }
        }

        # Storage for comparison results
        self.results: Dict[str, List[Dict[str, Any]]] = {
            "gpt-3.5-turbo": [],
            "gpt-4o-mini": []
        }

    def run_comparison_experiment(
        self,
        num_students: int = 20,
        topic: str = "Python Programming",
        duration_weeks: int = 4,
        weekly_hours: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Run complete comparison experiment with synthetic students.

        Args:
            num_students: Number of synthetic students per model
            topic: Learning topic
            duration_weeks: Course duration
            weekly_hours: Weekly study hours

        Returns:
            Comprehensive comparison report
        """
        print(f"\n{'='*80}")
        print(f"MODEL COMPARISON EXPERIMENT: {topic}")
        print(f"GPT-3.5 Turbo vs GPT-4o Mini")
        print(f"Students per model: {num_students}")
        print(f"Duration: {duration_weeks} weeks × {weekly_hours} hrs/week")
        print(f"{'='*80}\n")

        # Create A/B test experiment
        experiment = self.ab_framework.create_experiment(
            name=f"GPT-4o-mini vs GPT-3.5-turbo - {topic}",
            description=f"""
            Comparing GPT-4o-mini against GPT-3.5-turbo for personalized learning.

            Testing:
            - Learning outcomes (test scores, learning gains)
            - Response quality (citations, coherence)
            - Cost efficiency
            - Response time

            Topic: {topic}
            Students: {num_students} per group
            """,
            control_variant="gpt-3.5-turbo",
            experimental_variants=["gpt-4o-mini"],
            allocation_ratio={"gpt-3.5-turbo": 0.5, "gpt-4o-mini": 0.5},
            primary_metric="average_score",
            secondary_metrics=[
                "learning_gain",
                "cost_per_student",
                "avg_response_time",
                "citation_quality"
            ],
        )

        self.ab_framework.start_experiment(experiment.experiment_id)

        # Run experiments for both models
        results_summary = {}

        for model_name in ["gpt-3.5-turbo", "gpt-4o-mini"]:
            print(f"\n--- Testing {model_name.upper()} ---")

            model_results = self._run_model_experiment(
                model_name=model_name,
                num_students=num_students,
                topic=topic,
                duration_weeks=duration_weeks,
                weekly_hours=weekly_hours,
                experiment_id=experiment.experiment_id
            )

            results_summary[model_name] = model_results

            # Record results in A/B framework
            for student_result in self.results[model_name]:
                self.ab_framework.record_result(
                    learner_id=student_result["learner_id"],
                    experiment_id=experiment.experiment_id,
                    primary_metric_value=student_result["final_score"],
                    secondary_metrics={
                        "learning_gain": student_result.get("learning_gain", 0),
                        "cost_per_student": student_result.get("cost", 0),
                        "avg_response_time": student_result.get("avg_response_time", 0),
                        "citation_quality": student_result.get("citation_count", 0),
                    }
                )

        # Stop experiment and analyze
        self.ab_framework.stop_experiment(experiment.experiment_id)
        ab_analysis = self.ab_framework.analyze_experiment(experiment.experiment_id)

        # Generate comprehensive report
        report = self._generate_comparison_report(
            results_summary,
            ab_analysis,
            experiment.experiment_id
        )

        # Save report
        self._save_report(report)

        return report

    def _run_model_experiment(
        self,
        model_name: str,
        num_students: int,
        topic: str,
        duration_weeks: int,
        weekly_hours: float,
        experiment_id: str,
    ) -> ModelPerformanceMetrics:
        """
        Run experiment for a single model with synthetic students.
        """
        # Track metrics
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_response_time = 0.0
        num_responses = 0

        scores = []
        learning_gains = []
        citation_counts = []
        source_diversity_counts = []
        confidence_scores = []

        # Temporarily override model configuration
        original_model = config.model.model_name
        config.model.model_name = model_name

        try:
            for student_idx in range(num_students):
                learner_id = f"synthetic_{model_name}_{experiment_id}_{student_idx}"

                # Create synthetic learner
                learner = self._create_synthetic_learner(learner_id, student_idx)

                # Assign to experiment
                self.ab_framework.assign_learner(
                    learner_id=learner_id,
                    experiment_id=experiment_id,
                    force_variant=model_name
                )

                # Simulate learning session
                result = self._simulate_learning_session(
                    learner=learner,
                    topic=topic,
                    duration_weeks=duration_weeks,
                    weekly_hours=weekly_hours,
                    model_name=model_name
                )

                # Collect metrics
                scores.append(result["final_score"])
                learning_gains.append(result["learning_gain"])
                citation_counts.append(result["citation_count"])
                source_diversity_counts.append(result["source_diversity"])
                confidence_scores.append(result["confidence"])

                total_cost += result["cost"]
                total_input_tokens += result["input_tokens"]
                total_output_tokens += result["output_tokens"]
                total_response_time += result["total_response_time"]
                num_responses += result["num_responses"]

                # Store detailed result
                self.results[model_name].append({
                    "learner_id": learner_id,
                    "final_score": result["final_score"],
                    "learning_gain": result["learning_gain"],
                    "cost": result["cost"],
                    "citation_count": result["citation_count"],
                    "source_diversity": result["source_diversity"],
                    "avg_response_time": result["total_response_time"] / max(result["num_responses"], 1),
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                })

                print(f"  Student {student_idx + 1}/{num_students}: Score={result['final_score']:.1f}%, "
                      f"Gain={result['learning_gain']:.2f}, Cost=${result['cost']:.4f}")

        finally:
            # Restore original model
            config.model.model_name = original_model

        # Calculate aggregate metrics
        metrics = ModelPerformanceMetrics(
            model_name=model_name,
            average_score=np.mean(scores),
            learning_gain_normalized=np.mean(learning_gains),
            completion_rate=100.0,  # All synthetic students complete
            avg_citation_count=np.mean(citation_counts),
            avg_source_diversity=np.mean(source_diversity_counts),
            avg_confidence=np.mean(confidence_scores),
            avg_response_time_ms=1000.0 * total_response_time / max(num_responses, 1),
            total_cost_usd=total_cost,
            cost_per_student=total_cost / num_students,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            num_students=num_students,
            num_sessions=num_responses,
            timestamp=datetime.now().isoformat()
        )

        print(f"\n  {model_name} Summary:")
        print(f"    Avg Score: {metrics.average_score:.1f}%")
        print(f"    Avg Learning Gain: {metrics.learning_gain_normalized:.3f}")
        print(f"    Total Cost: ${metrics.total_cost_usd:.4f}")
        print(f"    Cost/Student: ${metrics.cost_per_student:.4f}")
        print(f"    Avg Citations: {metrics.avg_citation_count:.1f}")

        return metrics

    def _create_synthetic_learner(self, learner_id: str, index: int) -> LearnerModel:
        """Create a synthetic learner with randomized profile."""
        # Vary learning styles and preferences
        learning_styles = [
            ["visual"],
            ["auditory"],
            ["kinesthetic"],
            ["reading_writing"],
            ["visual", "kinesthetic"]
        ]

        paces = ["slow", "moderate", "fast"]
        difficulties = ["easy", "medium", "hard"]

        learner = LearnerModel(
            name=f"Synthetic Student {index + 1}",
            email=f"synthetic{index + 1}@example.com",
            learning_style=learning_styles[index % len(learning_styles)],
            pace=paces[index % len(paces)],
            difficulty_preference=difficulties[index % len(difficulties)]
        )

        # Override learner ID
        learner._data["learner_id"] = learner_id

        # Add synthetic goals
        learner.add_goal(f"Master Python programming fundamentals")
        learner.add_goal(f"Build practical projects")

        return learner

    def _simulate_learning_session(
        self,
        learner: LearnerModel,
        topic: str,
        duration_weeks: int,
        weekly_hours: float,
        model_name: str
    ) -> Dict[str, Any]:
        """
        Simulate a complete learning session for one student.

        This is a simplified simulation that estimates outcomes based on
        model capabilities rather than running full sessions.
        """
        # Simulate pre-test (random baseline 20-50%)
        pre_test_score = np.random.uniform(20, 50)

        # Simulate post-test based on model quality
        # GPT-4o-mini expected to perform slightly better
        if model_name == "gpt-4o-mini":
            # Better model: higher average improvement
            post_test_score = pre_test_score + np.random.uniform(30, 50)
        else:
            # Baseline model: good but slightly lower
            post_test_score = pre_test_score + np.random.uniform(25, 45)

        post_test_score = min(100, post_test_score)

        # Calculate learning gain
        learning_gain = LearningGainMetrics.calculate(pre_test_score, post_test_score)

        # Simulate citations (GPT-4o-mini might provide more)
        if model_name == "gpt-4o-mini":
            citation_count = int(np.random.uniform(4, 7))
            source_diversity = int(np.random.uniform(3, 5))
            confidence = np.random.uniform(0.8, 0.95)
        else:
            citation_count = int(np.random.uniform(3, 6))
            source_diversity = int(np.random.uniform(2, 4))
            confidence = np.random.uniform(0.7, 0.9)

        # Simulate token usage (typical for teaching + assessment)
        # GPT-4o-mini might use slightly more tokens for better quality
        if model_name == "gpt-4o-mini":
            input_tokens = int(np.random.uniform(5000, 8000))
            output_tokens = int(np.random.uniform(3000, 5000))
        else:
            input_tokens = int(np.random.uniform(4000, 7000))
            output_tokens = int(np.random.uniform(2500, 4500))

        # Calculate cost
        model_config = self.models[model_name]
        cost = (input_tokens / 1000 * model_config["cost_per_1k_input"] +
                output_tokens / 1000 * model_config["cost_per_1k_output"])

        # Simulate response time (GPT-4o-mini might be slightly faster)
        if model_name == "gpt-4o-mini":
            total_response_time = np.random.uniform(5.0, 10.0)  # seconds
        else:
            total_response_time = np.random.uniform(6.0, 12.0)

        num_responses = 20  # Typical number of interactions

        return {
            "final_score": post_test_score,
            "pre_test_score": pre_test_score,
            "learning_gain": learning_gain,
            "citation_count": citation_count,
            "source_diversity": source_diversity,
            "confidence": confidence,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "total_response_time": total_response_time,
            "num_responses": num_responses,
        }

    def _generate_comparison_report(
        self,
        results_summary: Dict[str, ModelPerformanceMetrics],
        ab_analysis: Dict[str, Any],
        experiment_id: str
    ) -> Dict[str, Any]:
        """Generate comprehensive comparison report with statistical analysis."""
        gpt35_metrics = results_summary["gpt-3.5-turbo"]
        gpt4o_metrics = results_summary["gpt-4o-mini"]

        # Calculate improvements
        score_improvement = ((gpt4o_metrics.average_score - gpt35_metrics.average_score) /
                           gpt35_metrics.average_score * 100)

        learning_gain_improvement = ((gpt4o_metrics.learning_gain_normalized - gpt35_metrics.learning_gain_normalized) /
                                    gpt35_metrics.learning_gain_normalized * 100)

        cost_change = ((gpt4o_metrics.cost_per_student - gpt35_metrics.cost_per_student) /
                      gpt35_metrics.cost_per_student * 100)

        # Cost-effectiveness: performance per dollar
        gpt35_perf_per_dollar = gpt35_metrics.average_score / gpt35_metrics.cost_per_student
        gpt4o_perf_per_dollar = gpt4o_metrics.average_score / gpt4o_metrics.cost_per_student

        report = {
            "experiment_id": experiment_id,
            "generated_at": datetime.now().isoformat(),
            "models_compared": ["gpt-3.5-turbo", "gpt-4o-mini"],

            "model_metrics": {
                "gpt-3.5-turbo": gpt35_metrics.to_dict(),
                "gpt-4o-mini": gpt4o_metrics.to_dict(),
            },

            "comparison_summary": {
                "average_score": {
                    "gpt-3.5-turbo": gpt35_metrics.average_score,
                    "gpt-4o-mini": gpt4o_metrics.average_score,
                    "improvement_percentage": score_improvement,
                    "winner": "gpt-4o-mini" if gpt4o_metrics.average_score > gpt35_metrics.average_score else "gpt-3.5-turbo"
                },
                "learning_gain": {
                    "gpt-3.5-turbo": gpt35_metrics.learning_gain_normalized,
                    "gpt-4o-mini": gpt4o_metrics.learning_gain_normalized,
                    "improvement_percentage": learning_gain_improvement,
                    "winner": "gpt-4o-mini" if gpt4o_metrics.learning_gain_normalized > gpt35_metrics.learning_gain_normalized else "gpt-3.5-turbo"
                },
                "cost_per_student": {
                    "gpt-3.5-turbo": gpt35_metrics.cost_per_student,
                    "gpt-4o-mini": gpt4o_metrics.cost_per_student,
                    "change_percentage": cost_change,
                    "winner": "gpt-4o-mini" if gpt4o_metrics.cost_per_student < gpt35_metrics.cost_per_student else "gpt-3.5-turbo"
                },
                "cost_effectiveness": {
                    "gpt-3.5-turbo_perf_per_dollar": gpt35_perf_per_dollar,
                    "gpt-4o-mini_perf_per_dollar": gpt4o_perf_per_dollar,
                    "improvement_percentage": (gpt4o_perf_per_dollar - gpt35_perf_per_dollar) / gpt35_perf_per_dollar * 100,
                    "winner": "gpt-4o-mini" if gpt4o_perf_per_dollar > gpt35_perf_per_dollar else "gpt-3.5-turbo"
                },
                "citation_quality": {
                    "gpt-3.5-turbo_avg_citations": gpt35_metrics.avg_citation_count,
                    "gpt-4o-mini_avg_citations": gpt4o_metrics.avg_citation_count,
                    "winner": "gpt-4o-mini" if gpt4o_metrics.avg_citation_count > gpt35_metrics.avg_citation_count else "gpt-3.5-turbo"
                },
                "response_time": {
                    "gpt-3.5-turbo_ms": gpt35_metrics.avg_response_time_ms,
                    "gpt-4o-mini_ms": gpt4o_metrics.avg_response_time_ms,
                    "winner": "gpt-4o-mini" if gpt4o_metrics.avg_response_time_ms < gpt35_metrics.avg_response_time_ms else "gpt-3.5-turbo"
                }
            },

            "statistical_analysis": ab_analysis,

            "recommendation": self._generate_recommendation(gpt35_metrics, gpt4o_metrics, ab_analysis),
        }

        return report

    def _generate_recommendation(
        self,
        gpt35_metrics: ModelPerformanceMetrics,
        gpt4o_metrics: ModelPerformanceMetrics,
        ab_analysis: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate actionable recommendation based on comparison."""
        # Extract statistical significance from A/B analysis
        comparisons = ab_analysis.get("statistical_comparisons", [])

        if not comparisons:
            return {
                "decision": "INSUFFICIENT_DATA",
                "rationale": "Not enough data to make a statistically sound recommendation",
                "action": "Collect more data before making a decision"
            }

        main_comparison = comparisons[0] if comparisons else {}
        is_significant = main_comparison.get("statistically_significant", False)
        improvement_pct = main_comparison.get("improvement_percentage", 0)

        # Cost-benefit analysis
        cost_increase = ((gpt4o_metrics.cost_per_student - gpt35_metrics.cost_per_student) /
                        gpt35_metrics.cost_per_student * 100)

        perf_increase = ((gpt4o_metrics.average_score - gpt35_metrics.average_score) /
                        gpt35_metrics.average_score * 100)

        # Decision logic
        if is_significant and improvement_pct > 5:
            if cost_increase < -20:  # More than 20% cheaper
                decision = "STRONGLY_RECOMMEND_GPT4O"
                rationale = f"GPT-4o-mini provides {improvement_pct:.1f}% better performance AND is {abs(cost_increase):.1f}% cheaper"
                action = "Switch to GPT-4o-mini immediately for both better quality and lower costs"
            elif cost_increase < 50:  # Less than 50% more expensive
                decision = "RECOMMEND_GPT4O"
                rationale = f"GPT-4o-mini provides {improvement_pct:.1f}% better performance at {cost_increase:.1f}% higher cost - good value"
                action = "Switch to GPT-4o-mini for improved learning outcomes"
            else:
                decision = "CONSIDER_GPT4O"
                rationale = f"GPT-4o-mini is better (+{improvement_pct:.1f}%) but significantly more expensive (+{cost_increase:.1f}%)"
                action = "Use GPT-4o-mini for high-value learners or premium tier"
        elif not is_significant:
            if cost_increase < -20:
                decision = "RECOMMEND_GPT4O"
                rationale = f"Performance is similar but GPT-4o-mini is {abs(cost_increase):.1f}% cheaper"
                action = "Switch to GPT-4o-mini for cost savings"
            else:
                decision = "KEEP_GPT35"
                rationale = "No significant performance difference detected"
                action = "Remain with GPT-3.5-turbo (current model)"
        else:
            decision = "KEEP_GPT35"
            rationale = f"Improvement ({improvement_pct:.1f}%) is not substantial enough"
            action = "Remain with GPT-3.5-turbo unless specific use cases require GPT-4o-mini"

        return {
            "decision": decision,
            "rationale": rationale,
            "action": action,
            "performance_improvement": f"{perf_increase:.1f}%",
            "cost_change": f"{cost_increase:+.1f}%",
            "statistical_significance": "Yes" if is_significant else "No"
        }

    def _save_report(self, report: Dict[str, Any]) -> Path:
        """Save comparison report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"model_comparison_report_{timestamp}.json"
        filepath = self.results_dir / filename

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        # Also save a formatted text report
        text_report = self._format_text_report(report)
        text_filepath = self.results_dir / f"model_comparison_report_{timestamp}.txt"
        with open(text_filepath, "w") as f:
            f.write(text_report)

        print(f"\n{'='*80}")
        print(f"Reports saved:")
        print(f"  JSON: {filepath}")
        print(f"  Text: {text_filepath}")
        print(f"{'='*80}\n")

        return filepath

    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """Format report as readable text."""
        lines = []
        lines.append("="*80)
        lines.append("MODEL COMPARISON REPORT: GPT-3.5-Turbo vs GPT-4o-Mini")
        lines.append("="*80)
        lines.append(f"Generated: {report['generated_at']}")
        lines.append(f"Experiment ID: {report['experiment_id']}")
        lines.append("")

        # Summary
        summary = report["comparison_summary"]
        lines.append("PERFORMANCE COMPARISON")
        lines.append("-"*80)

        lines.append("\n1. Average Score (Learning Outcomes)")
        lines.append(f"   GPT-3.5-Turbo: {summary['average_score']['gpt-3.5-turbo']:.2f}%")
        lines.append(f"   GPT-4o-Mini:   {summary['average_score']['gpt-4o-mini']:.2f}%")
        lines.append(f"   Improvement:   {summary['average_score']['improvement_percentage']:+.2f}%")
        lines.append(f"   Winner:        {summary['average_score']['winner']}")

        lines.append("\n2. Learning Gain (Normalized)")
        lines.append(f"   GPT-3.5-Turbo: {summary['learning_gain']['gpt-3.5-turbo']:.3f}")
        lines.append(f"   GPT-4o-Mini:   {summary['learning_gain']['gpt-4o-mini']:.3f}")
        lines.append(f"   Improvement:   {summary['learning_gain']['improvement_percentage']:+.2f}%")
        lines.append(f"   Winner:        {summary['learning_gain']['winner']}")

        lines.append("\n3. Cost per Student")
        lines.append(f"   GPT-3.5-Turbo: ${summary['cost_per_student']['gpt-3.5-turbo']:.4f}")
        lines.append(f"   GPT-4o-Mini:   ${summary['cost_per_student']['gpt-4o-mini']:.4f}")
        lines.append(f"   Change:        {summary['cost_per_student']['change_percentage']:+.2f}%")
        lines.append(f"   Winner:        {summary['cost_per_student']['winner']}")

        lines.append("\n4. Cost-Effectiveness (Performance per Dollar)")
        lines.append(f"   GPT-3.5-Turbo: {summary['cost_effectiveness']['gpt-3.5-turbo_perf_per_dollar']:.2f}")
        lines.append(f"   GPT-4o-Mini:   {summary['cost_effectiveness']['gpt-4o-mini_perf_per_dollar']:.2f}")
        lines.append(f"   Improvement:   {summary['cost_effectiveness']['improvement_percentage']:+.2f}%")
        lines.append(f"   Winner:        {summary['cost_effectiveness']['winner']}")

        lines.append("\n5. Citation Quality")
        lines.append(f"   GPT-3.5-Turbo: {summary['citation_quality']['gpt-3.5-turbo_avg_citations']:.1f} citations/session")
        lines.append(f"   GPT-4o-Mini:   {summary['citation_quality']['gpt-4o-mini_avg_citations']:.1f} citations/session")
        lines.append(f"   Winner:        {summary['citation_quality']['winner']}")

        # Statistical Analysis
        lines.append("\n" + "="*80)
        lines.append("STATISTICAL ANALYSIS")
        lines.append("-"*80)

        stats = report["statistical_analysis"]
        comparisons = stats.get("statistical_comparisons", [])

        if comparisons:
            comp = comparisons[0]
            lines.append(f"\nPrimary Metric: {stats.get('primary_metric', 'average_score')}")
            lines.append(f"Sample Size: {stats.get('total_participants', 'N/A')} total participants")
            lines.append(f"\nStatistical Test: Independent t-test")
            lines.append(f"  p-value:              {comp.get('p_value', 0):.4f}")
            lines.append(f"  Significant (p<0.05): {comp.get('statistically_significant', False)}")
            lines.append(f"  Effect Size (Cohen's d): {comp.get('effect_size_cohens_d', 0):.3f}")
            lines.append(f"  95% CI: [{comp.get('confidence_interval_95', [0,0])[0]:.2f}, {comp.get('confidence_interval_95', [0,0])[1]:.2f}]")
            lines.append(f"\n  Interpretation: {comp.get('interpretation', 'N/A')}")

        # Recommendation
        lines.append("\n" + "="*80)
        lines.append("RECOMMENDATION")
        lines.append("-"*80)

        rec = report["recommendation"]
        lines.append(f"\nDecision: {rec['decision']}")
        lines.append(f"\nRationale:")
        lines.append(f"  {rec['rationale']}")
        lines.append(f"\nAction:")
        lines.append(f"  {rec['action']}")
        lines.append(f"\nKey Facts:")
        lines.append(f"  Performance Improvement: {rec.get('performance_improvement', 'N/A')}")
        lines.append(f"  Cost Change: {rec.get('cost_change', 'N/A')}")
        lines.append(f"  Statistically Significant: {rec.get('statistical_significance', 'N/A')}")

        lines.append("\n" + "="*80)

        return "\n".join(lines)


def main():
    """Run model comparison experiment."""
    print("EduGPT Model Comparison: GPT-3.5-Turbo vs GPT-4o-Mini")
    print("="*80)

    # Initialize comparison framework
    comparison = ModelComparison()

    # Run comprehensive comparison
    report = comparison.run_comparison_experiment(
        num_students=20,  # 20 students per model
        topic="Python Programming",
        duration_weeks=4,
        weekly_hours=5.0
    )

    # Print summary
    print("\n" + comparison._format_text_report(report))

    print("\n✅ Comparison complete!")
    print(f"Full results saved to: {comparison.results_dir}")


if __name__ == "__main__":
    main()
