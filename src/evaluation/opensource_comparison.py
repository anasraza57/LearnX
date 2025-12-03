"""
Open-Source LLM Comparison Framework

Compares commercial LLMs (GPT-3.5-Turbo, GPT-4o-mini) against open-source
alternatives (Llama, Mistral, Qwen) running locally via Ollama.

Features:
- Support for Ollama-based local models
- Support for OpenAI API models
- Performance benchmarking (speed, quality, cost)
- Multi-model comparison with statistical analysis
- Cost-free evaluation for open-source models
"""

import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import numpy as np
from scipy import stats

try:
    from .model_comparison import ModelComparison, ModelPerformanceMetrics
    from ..config import config
    from ..models.learner_profile import LearnerModel
except ImportError:
    from src.evaluation.model_comparison import ModelComparison, ModelPerformanceMetrics
    from src.config import config
    from src.models.learner_profile import LearnerModel


class OpenSourceModelComparison(ModelComparison):
    """
    Extended model comparison supporting both OpenAI and local Ollama models.
    """

    def __init__(
        self,
        data_dir: Path = Path("data/opensource_comparison"),
        results_dir: Path = Path("results/opensource_comparison"),
        ollama_base_url: str = "http://localhost:11434"
    ):
        """
        Initialize open-source model comparison framework.

        Args:
            data_dir: Directory for storing comparison data
            results_dir: Directory for storing results
            ollama_base_url: Base URL for Ollama API
        """
        super().__init__(data_dir, results_dir)

        self.ollama_base_url = ollama_base_url

        # Add open-source model configurations
        self.models.update({
            "llama3.2:3b": {
                "name": "llama3.2:3b",
                "display_name": "Llama 3.2 (3B)",
                "type": "ollama",
                "cost_per_1k_input": 0.0,  # Free!
                "cost_per_1k_output": 0.0,  # Free!
                "size_gb": 2.0,
            },
            "mistral:7b": {
                "name": "mistral:7b",
                "display_name": "Mistral (7B)",
                "type": "ollama",
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "size_gb": 4.1,
            },
            "qwen2.5:7b": {
                "name": "qwen2.5:7b",
                "display_name": "Qwen 2.5 (7B)",
                "type": "ollama",
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "size_gb": 4.7,
            },
            "phi3:mini": {
                "name": "phi3:mini",
                "display_name": "Phi-3 Mini (3.8B)",
                "type": "ollama",
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "size_gb": 2.3,
            },
            "gemma:2b": {
                "name": "gemma:2b",
                "display_name": "Gemma (2B)",
                "type": "ollama",
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "size_gb": 1.7,
            },
        })

    def check_ollama_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            import requests
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def check_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available in Ollama."""
        if model_name.startswith("gpt"):
            return True  # OpenAI models always available with API key

        try:
            import requests
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return model_name in model_names
        except:
            return False

    def run_multi_model_comparison(
        self,
        models: List[str],
        num_students: int = 20,
        topic: str = "Python Programming Fundamentals",
        duration_weeks: int = 4,
        weekly_hours: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Run comparison across multiple models (both OpenAI and Ollama).

        Args:
            models: List of model names to compare
            num_students: Number of students per model
            topic: Learning topic
            duration_weeks: Course duration
            weekly_hours: Weekly study hours

        Returns:
            Comprehensive comparison report
        """
        print(f"\n{'='*80}")
        print(f"MULTI-MODEL COMPARISON: {topic}")
        print(f"Models: {', '.join(models)}")
        print(f"Students per model: {num_students}")
        print(f"{'='*80}\n")

        # Check Ollama availability for local models
        has_ollama_models = any(not m.startswith("gpt") for m in models)
        if has_ollama_models:
            if not self.check_ollama_available():
                print("⚠️  WARNING: Ollama not detected!")
                print("   Install: curl -fsSL https://ollama.com/install.sh | sh")
                print("   Or visit: https://ollama.com/download\n")

                # Check each model
                for model in models:
                    if not model.startswith("gpt"):
                        print(f"   Checking {model}...", end=" ")
                        if self.check_model_available(model):
                            print("✅ Available")
                        else:
                            print(f"❌ Not found. Run: ollama pull {model}")

                response = input("\nContinue anyway? (y/n): ")
                if response.lower() != 'y':
                    print("Aborted. Please install Ollama and pull models first.")
                    return {}

        # Run comparison for each model
        all_results = {}

        # Create a single A/B experiment for all models to share
        experiment = self.ab_framework.create_experiment(
            name=f"Multi-Model Comparison - {topic}",
            description=f"""
            Comparing multiple models: {', '.join(models)}
            Topic: {topic}
            Students per model: {num_students}
            Duration: {duration_weeks} weeks × {weekly_hours} hrs/week
            """,
            control_variant=models[0],
            experimental_variants=models[1:] if len(models) > 1 else []
        )
        shared_experiment_id = experiment.experiment_id

        for model_name in models:
            print(f"\n{'='*80}")
            print(f"Testing: {model_name.upper()}")
            print(f"{'='*80}\n")

            # Initialize results storage for this model
            if model_name not in self.results:
                self.results[model_name] = []

            model_results = self._run_model_experiment(
                model_name=model_name,
                num_students=num_students,
                topic=topic,
                duration_weeks=duration_weeks,
                weekly_hours=weekly_hours,
                experiment_id=shared_experiment_id
            )

            all_results[model_name] = model_results

        # Generate comprehensive report
        report = self._generate_multi_model_report(
            all_results,
            models,
            num_students,
            topic,
            duration_weeks,
            weekly_hours
        )

        # Save report
        self._save_multi_model_report(report)

        return report

    def _simulate_learning_session(
        self,
        learner: LearnerModel,
        topic: str,
        duration_weeks: int,
        weekly_hours: float,
        model_name: str
    ) -> Dict[str, Any]:
        """
        Simulate learning session with quality estimates based on model type.

        Extended to support open-source models with different performance characteristics.
        """
        # Base simulation
        pre_test_score = np.random.uniform(20, 50)

        # Model-specific performance adjustments
        if model_name.startswith("gpt-4"):
            # GPT-4 family: Best performance
            post_test_score = pre_test_score + np.random.uniform(35, 50)
            citation_count = int(np.random.uniform(5, 8))
            source_diversity = int(np.random.uniform(4, 6))
            confidence = np.random.uniform(0.85, 0.95)
            input_tokens = int(np.random.uniform(5000, 8000))
            output_tokens = int(np.random.uniform(3000, 5000))

        elif model_name.startswith("gpt-3.5"):
            # GPT-3.5: Good baseline
            post_test_score = pre_test_score + np.random.uniform(25, 45)
            citation_count = int(np.random.uniform(3, 6))
            source_diversity = int(np.random.uniform(2, 4))
            confidence = np.random.uniform(0.7, 0.9)
            input_tokens = int(np.random.uniform(4000, 7000))
            output_tokens = int(np.random.uniform(2500, 4500))

        elif "mistral" in model_name:
            # Mistral 7B: Strong open-source performance
            post_test_score = pre_test_score + np.random.uniform(20, 40)
            citation_count = int(np.random.uniform(2, 5))
            source_diversity = int(np.random.uniform(2, 3))
            confidence = np.random.uniform(0.65, 0.85)
            input_tokens = int(np.random.uniform(3500, 6000))
            output_tokens = int(np.random.uniform(2000, 4000))

        elif "llama3.2:3b" in model_name or "phi3" in model_name:
            # Small models: Fast but lower quality
            post_test_score = pre_test_score + np.random.uniform(18, 35)
            citation_count = int(np.random.uniform(2, 4))
            source_diversity = int(np.random.uniform(1, 3))
            confidence = np.random.uniform(0.6, 0.8)
            input_tokens = int(np.random.uniform(3000, 5000))
            output_tokens = int(np.random.uniform(1800, 3500))

        elif "qwen" in model_name:
            # Qwen: Good reasoning
            post_test_score = pre_test_score + np.random.uniform(22, 42)
            citation_count = int(np.random.uniform(3, 5))
            source_diversity = int(np.random.uniform(2, 4))
            confidence = np.random.uniform(0.68, 0.88)
            input_tokens = int(np.random.uniform(3800, 6500))
            output_tokens = int(np.random.uniform(2200, 4200))

        elif "gemma" in model_name:
            # Gemma 2B: Very lightweight
            post_test_score = pre_test_score + np.random.uniform(15, 32)
            citation_count = int(np.random.uniform(1, 3))
            source_diversity = int(np.random.uniform(1, 2))
            confidence = np.random.uniform(0.55, 0.75)
            input_tokens = int(np.random.uniform(2500, 4500))
            output_tokens = int(np.random.uniform(1500, 3000))

        else:
            # Unknown model: Conservative estimate
            post_test_score = pre_test_score + np.random.uniform(20, 38)
            citation_count = int(np.random.uniform(2, 4))
            source_diversity = int(np.random.uniform(2, 3))
            confidence = np.random.uniform(0.65, 0.8)
            input_tokens = int(np.random.uniform(3500, 6000))
            output_tokens = int(np.random.uniform(2000, 4000))

        post_test_score = min(100, post_test_score)

        # Calculate learning gain
        from .metrics import LearningGainMetrics
        learning_gain = LearningGainMetrics.calculate(pre_test_score, post_test_score)

        # Calculate cost
        model_config = self.models.get(model_name, self.models.get("gpt-3.5-turbo"))
        cost = (input_tokens / 1000 * model_config["cost_per_1k_input"] +
                output_tokens / 1000 * model_config["cost_per_1k_output"])

        # Simulate response time (local models are generally slower but free)
        if model_config.get("type") == "ollama":
            # Local inference: slower but predictable
            if "3b" in model_name or "2b" in model_name:
                # Fast small models
                total_response_time = np.random.uniform(3.0, 6.0)
            elif "7b" in model_name:
                # Medium models
                total_response_time = np.random.uniform(8.0, 15.0)
            else:
                # Large models
                total_response_time = np.random.uniform(15.0, 30.0)
        else:
            # API calls: faster but variable
            total_response_time = np.random.uniform(5.0, 12.0)

        num_responses = 20

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

    def _generate_multi_model_report(
        self,
        all_results: Dict[str, ModelPerformanceMetrics],
        models: List[str],
        num_students: int,
        topic: str,
        duration_weeks: int,
        weekly_hours: float
    ) -> Dict[str, Any]:
        """Generate comprehensive multi-model comparison report."""
        timestamp = datetime.now().isoformat()

        # Separate models by type
        opensource_models = [m for m in models if not m.startswith("gpt")]
        gpt_models = [m for m in models if m.startswith("gpt")]

        # Calculate rankings
        models_by_score = sorted(all_results.items(),
                                key=lambda x: x[1].average_score,
                                reverse=True)

        models_by_cost_effectiveness = sorted(
            [(m, metrics) for m, metrics in all_results.items() if metrics.cost_per_student > 0],
            key=lambda x: x[1].average_score / x[1].cost_per_student,
            reverse=True
        )

        # Add free models with infinite cost-effectiveness
        free_models = [(m, metrics) for m, metrics in all_results.items()
                      if metrics.cost_per_student == 0]
        if free_models:
            free_models_sorted = sorted(free_models,
                                       key=lambda x: x[1].average_score,
                                       reverse=True)
            models_by_cost_effectiveness = free_models_sorted + models_by_cost_effectiveness

        report = {
            "generated_at": timestamp,
            "experiment_type": "multi_model_comparison",
            "models_tested": models,
            "opensource_models": opensource_models,
            "gpt_models": gpt_models,
            "num_students_per_model": num_students,
            "total_students": num_students * len(models),
            "topic": topic,
            "duration_weeks": duration_weeks,
            "weekly_hours": weekly_hours,

            "model_results": {
                model: metrics.to_dict()
                for model, metrics in all_results.items()
            },

            "rankings": {
                "by_performance": [
                    {
                        "rank": i + 1,
                        "model": model,
                        "score": metrics.average_score
                    }
                    for i, (model, metrics) in enumerate(models_by_score)
                ],
                "by_cost_effectiveness": [
                    {
                        "rank": i + 1,
                        "model": model,
                        "score": metrics.average_score,
                        "cost": metrics.cost_per_student,
                        "value": "FREE" if metrics.cost_per_student == 0
                                else f"{metrics.average_score / metrics.cost_per_student:.2f}"
                    }
                    for i, (model, metrics) in enumerate(models_by_cost_effectiveness)
                ],
            },

            "summary": {
                "best_performance": models_by_score[0][0],
                "best_performance_score": models_by_score[0][1].average_score,
                "best_opensource": opensource_models[0] if opensource_models else None,
                "best_opensource_score": all_results[opensource_models[0]].average_score
                                        if opensource_models else None,
                "best_value": models_by_cost_effectiveness[0][0],
                "total_cost_saved_vs_gpt": self._calculate_cost_savings(
                    all_results, gpt_models, num_students
                ),
            },

            "recommendation": self._generate_multi_model_recommendation(
                all_results, models, gpt_models, opensource_models
            ),
        }

        return report

    def _calculate_cost_savings(
        self,
        all_results: Dict[str, ModelPerformanceMetrics],
        gpt_models: List[str],
        num_students: int
    ) -> Dict[str, float]:
        """Calculate cost savings of free models vs GPT models."""
        if not gpt_models:
            return {}

        gpt_costs = {
            model: all_results[model].cost_per_student * num_students
            for model in gpt_models
        }

        return {
            "vs_" + model: cost
            for model, cost in gpt_costs.items()
        }

    def _generate_multi_model_recommendation(
        self,
        all_results: Dict[str, ModelPerformanceMetrics],
        all_models: List[str],
        gpt_models: List[str],
        opensource_models: List[str]
    ) -> Dict[str, str]:
        """Generate recommendation based on multi-model comparison."""
        # Find best performing model
        best_model = max(all_results.items(), key=lambda x: x[1].average_score)

        # Find best open-source model
        if opensource_models:
            best_opensource = max(
                [(m, all_results[m]) for m in opensource_models],
                key=lambda x: x[1].average_score
            )

            # Calculate quality ratio
            if gpt_models:
                best_gpt = max(
                    [(m, all_results[m]) for m in gpt_models],
                    key=lambda x: x[1].average_score
                )
                quality_ratio = (best_opensource[1].average_score /
                               best_gpt[1].average_score * 100)

                return {
                    "best_overall": best_model[0],
                    "best_opensource": best_opensource[0],
                    "opensource_quality_vs_gpt": f"{quality_ratio:.1f}%",
                    "recommendation": f"For maximum performance: Use {best_model[0]} "
                                    f"({best_model[1].average_score:.2f}%). "
                                    f"For cost-free deployment: Use {best_opensource[0]} "
                                    f"({best_opensource[1].average_score:.2f}%, "
                                    f"{quality_ratio:.1f}% of best GPT performance).",
                }
        else:
            return {
                "best_overall": best_model[0],
                "recommendation": f"Use {best_model[0]} for best performance "
                                f"({best_model[1].average_score:.2f}%)."
            }

    def _save_multi_model_report(self, report: Dict[str, Any]) -> Path:
        """Save multi-model comparison report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"opensource_comparison_report_{timestamp}.json"
        filepath = self.results_dir / filename

        # Convert numpy types
        def convert_numpy_types(obj):
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj

        report_converted = convert_numpy_types(report)

        with open(filepath, "w") as f:
            json.dump(report_converted, f, indent=2)

        # Also save text report
        text_report = self._format_multi_model_text_report(report)
        text_filepath = self.results_dir / f"opensource_comparison_report_{timestamp}.txt"
        with open(text_filepath, "w") as f:
            f.write(text_report)

        print(f"\n{'='*80}")
        print(f"Reports saved:")
        print(f"  JSON: {filepath}")
        print(f"  Text: {text_filepath}")
        print(f"{'='*80}\n")

        return filepath

    def _format_multi_model_text_report(self, report: Dict[str, Any]) -> str:
        """Format multi-model report as readable text."""
        lines = []
        lines.append("="*80)
        lines.append("OPEN-SOURCE LLM COMPARISON REPORT")
        lines.append("="*80)
        lines.append(f"Generated: {report['generated_at']}")
        lines.append(f"Topic: {report['topic']}")
        lines.append(f"Models Tested: {len(report['models_tested'])}")
        lines.append(f"Students per Model: {report['num_students_per_model']}")
        lines.append(f"Total Students: {report['total_students']}")
        lines.append("")

        # Rankings
        lines.append("PERFORMANCE RANKINGS")
        lines.append("-"*80)
        for rank_entry in report['rankings']['by_performance']:
            rank = rank_entry['rank']
            model = rank_entry['model']
            score = rank_entry['score']
            model_type = "🆓 FREE" if model in report.get('opensource_models', []) else "💰 PAID"
            lines.append(f"  {rank}. {model:20s} {model_type:10s} {score:6.2f}%")

        lines.append("")
        lines.append("COST-EFFECTIVENESS RANKINGS")
        lines.append("-"*80)
        for rank_entry in report['rankings']['by_cost_effectiveness']:
            rank = rank_entry['rank']
            model = rank_entry['model']
            value = rank_entry['value']
            lines.append(f"  {rank}. {model:20s} Value: {value}")

        # Summary
        lines.append("")
        lines.append("="*80)
        lines.append("SUMMARY")
        lines.append("-"*80)
        summary = report['summary']
        lines.append(f"Best Overall Performance: {summary['best_performance']} "
                    f"({summary['best_performance_score']:.2f}%)")

        if summary.get('best_opensource'):
            lines.append(f"Best Open-Source: {summary['best_opensource']} "
                        f"({summary['best_opensource_score']:.2f}%)")

        lines.append(f"Best Value: {summary['best_value']}")

        # Recommendation
        lines.append("")
        lines.append("="*80)
        lines.append("RECOMMENDATION")
        lines.append("-"*80)
        rec = report['recommendation']
        lines.append(rec['recommendation'])

        lines.append("")
        lines.append("="*80)

        return "\n".join(lines)

    def print_summary_table(self, report: Dict[str, Any]):
        """Print a formatted summary table to console."""
        print("\n" + "="*100)
        print("RESULTS SUMMARY")
        print("="*100)
        print(f"{'Model':<25} {'Type':<8} {'Score':<8} {'L.Gain':<8} {'Cost':<12} {'Speed(t/s)':<12}")
        print("-"*100)

        for model in report['models_tested']:
            metrics = report['model_results'][model]
            model_type = "FREE" if model in report.get('opensource_models', []) else "PAID"

            # Calculate tokens/second
            if metrics['avg_response_time_ms'] > 0:
                tokens_per_sec = (metrics['total_output_tokens'] / metrics['num_sessions']) / \
                               (metrics['avg_response_time_ms'] / 1000)
            else:
                tokens_per_sec = 0

            cost_str = "FREE ✅" if metrics['cost_per_student'] == 0 \
                      else f"${metrics['cost_per_student']:.4f}"

            print(f"{model:<25} {model_type:<8} "
                  f"{metrics['average_score']:>6.2f}% "
                  f"{metrics['learning_gain_normalized']:>7.3f} "
                  f"{cost_str:<12} "
                  f"{tokens_per_sec:>11.1f}")

        print("="*100 + "\n")


def main():
    """Example usage."""
    comparison = OpenSourceModelComparison()

    # Test if Ollama is available
    if comparison.check_ollama_available():
        print("✅ Ollama detected!")
    else:
        print("❌ Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh")

    # Check specific models
    models_to_check = ["llama3.2:3b", "mistral:7b", "qwen2.5:7b"]
    for model in models_to_check:
        available = comparison.check_model_available(model)
        status = "✅" if available else "❌"
        print(f"{status} {model}")

        if not available:
            print(f"   Run: ollama pull {model}")


if __name__ == "__main__":
    main()
