"""
Run Model Comparison: GPT-3.5-Turbo vs GPT-4o-Mini

This script runs a comprehensive comparison experiment and generates
a publication-ready report with metrics and visualizations.

Usage:
    python examples/run_model_comparison.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.evaluation.model_comparison import ModelComparison


def main():
    """Run comprehensive model comparison."""
    print("="*80)
    print("EDUGPT MODEL COMPARISON EXPERIMENT")
    print("GPT-3.5-Turbo vs GPT-4o-Mini")
    print("="*80)
    print()

    # Initialize comparison framework
    comparison = ModelComparison(
        data_dir=project_root / "data" / "model_comparison",
        results_dir=project_root / "results" / "model_comparison"
    )

    # Configuration
    config = {
        "num_students": 30,  # 30 synthetic students per model (60 total)
        "topic": "Python Programming Fundamentals",
        "duration_weeks": 4,
        "weekly_hours": 5.0,
    }

    print("Experiment Configuration:")
    print(f"  Topic: {config['topic']}")
    print(f"  Students per model: {config['num_students']}")
    print(f"  Duration: {config['duration_weeks']} weeks × {config['weekly_hours']} hrs/week")
    print(f"  Total students: {config['num_students'] * 2}")
    print()

    # Auto-start without waiting for input
    print("Starting comparison experiment...\n")

    # Run experiment
    report = comparison.run_comparison_experiment(
        num_students=config["num_students"],
        topic=config["topic"],
        duration_weeks=config["duration_weeks"],
        weekly_hours=config["weekly_hours"],
    )

    # Print formatted report
    print("\n" + "="*80)
    print("FINAL REPORT")
    print("="*80)
    print()
    print(comparison._format_text_report(report))

    # Print file locations
    print("\n" + "="*80)
    print("RESULTS SAVED")
    print("="*80)
    print(f"\nResults directory: {comparison.results_dir}")
    print("\nFiles generated:")
    print("  - model_comparison_report_[timestamp].json (machine-readable)")
    print("  - model_comparison_report_[timestamp].txt (human-readable)")
    print()

    # Extract key findings for publication
    print("="*80)
    print("KEY FINDINGS FOR PUBLICATION")
    print("="*80)
    print()

    summary = report["comparison_summary"]
    rec = report["recommendation"]
    stats = report["statistical_analysis"]

    print("1. LEARNING OUTCOMES")
    print(f"   - GPT-3.5-Turbo: {summary['average_score']['gpt-3.5-turbo']:.2f}% average score")
    print(f"   - GPT-4o-Mini: {summary['average_score']['gpt-4o-mini']:.2f}% average score")
    print(f"   - Improvement: {summary['average_score']['improvement_percentage']:+.2f}%")
    print()

    print("2. LEARNING GAIN (Hake's Normalized Gain)")
    print(f"   - GPT-3.5-Turbo: {summary['learning_gain']['gpt-3.5-turbo']:.3f}")
    print(f"   - GPT-4o-Mini: {summary['learning_gain']['gpt-4o-mini']:.3f}")
    print(f"   - Improvement: {summary['learning_gain']['improvement_percentage']:+.2f}%")
    print()

    print("3. COST EFFICIENCY")
    print(f"   - GPT-3.5-Turbo: ${summary['cost_per_student']['gpt-3.5-turbo']:.4f} per student")
    print(f"   - GPT-4o-Mini: ${summary['cost_per_student']['gpt-4o-mini']:.4f} per student")
    print(f"   - Change: {summary['cost_per_student']['change_percentage']:+.2f}%")
    print()

    print("4. COST-EFFECTIVENESS (Performance per Dollar)")
    print(f"   - GPT-3.5-Turbo: {summary['cost_effectiveness']['gpt-3.5-turbo_perf_per_dollar']:.2f}")
    print(f"   - GPT-4o-Mini: {summary['cost_effectiveness']['gpt-4o-mini_perf_per_dollar']:.2f}")
    print(f"   - Improvement: {summary['cost_effectiveness']['improvement_percentage']:+.2f}%")
    print()

    print("5. CITATION QUALITY")
    print(f"   - GPT-3.5-Turbo: {summary['citation_quality']['gpt-3.5-turbo_avg_citations']:.1f} citations/session")
    print(f"   - GPT-4o-Mini: {summary['citation_quality']['gpt-4o-mini_avg_citations']:.1f} citations/session")
    print()

    comparisons = stats.get("statistical_comparisons", [])
    if comparisons:
        comp = comparisons[0]
        print("6. STATISTICAL SIGNIFICANCE")
        print(f"   - p-value: {comp.get('p_value', 0):.4f}")
        print(f"   - Significant (α=0.05): {'Yes' if comp.get('statistically_significant', False) else 'No'}")
        print(f"   - Effect Size (Cohen's d): {comp.get('effect_size_cohens_d', 0):.3f}")
        print(f"   - Interpretation: {comp.get('interpretation', 'N/A')}")
        print()

    print("7. RECOMMENDATION")
    print(f"   - Decision: {rec['decision']}")
    print(f"   - Action: {rec['action']}")
    print()

    print("="*80)
    print("EXPERIMENT COMPLETE")
    print("="*80)
    print()
    print("✅ All results saved and ready for publication!")
    print()


if __name__ == "__main__":
    main()
