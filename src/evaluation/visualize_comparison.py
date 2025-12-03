"""
Visualization Module for Model Comparison Results

Generates publication-ready charts and figures for comparing
GPT-3.5-Turbo vs GPT-4o-Mini performance.

Requires:
    - matplotlib
    - seaborn
    - pandas (optional, for better data handling)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ComparisonVisualizer:
    """Generate visualizations for model comparison results."""

    def __init__(self, style: str = "seaborn-v0_8-darkgrid"):
        """
        Initialize visualizer.

        Args:
            style: Matplotlib style to use
        """
        # Set publication-quality style
        plt.style.use(style)
        sns.set_palette("husl")

        # Set font sizes for publication
        plt.rcParams.update({
            'font.size': 12,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 11,
            'ytick.labelsize': 11,
            'legend.fontsize': 11,
            'figure.titlesize': 16
        })

    def visualize_report(
        self,
        report_path: Path,
        output_dir: Optional[Path] = None
    ) -> List[Path]:
        """
        Generate all visualizations from a comparison report.

        Args:
            report_path: Path to JSON comparison report
            output_dir: Directory to save figures (default: same as report)

        Returns:
            List of paths to generated figures
        """
        # Load report
        with open(report_path, 'r') as f:
            report = json.load(f)

        # Set output directory
        if output_dir is None:
            output_dir = report_path.parent / "figures"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        generated_figures = []

        # 1. Average Scores Comparison (Bar Chart)
        fig_path = output_dir / f"scores_comparison_{timestamp}.png"
        self.plot_scores_comparison(report, fig_path)
        generated_figures.append(fig_path)

        # 2. Learning Gains Comparison
        fig_path = output_dir / f"learning_gains_{timestamp}.png"
        self.plot_learning_gains(report, fig_path)
        generated_figures.append(fig_path)

        # 3. Cost Comparison
        fig_path = output_dir / f"cost_comparison_{timestamp}.png"
        self.plot_cost_comparison(report, fig_path)
        generated_figures.append(fig_path)

        # 4. Cost-Effectiveness
        fig_path = output_dir / f"cost_effectiveness_{timestamp}.png"
        self.plot_cost_effectiveness(report, fig_path)
        generated_figures.append(fig_path)

        # 5. Citation Quality
        fig_path = output_dir / f"citation_quality_{timestamp}.png"
        self.plot_citation_quality(report, fig_path)
        generated_figures.append(fig_path)

        # 6. Summary Dashboard (all metrics)
        fig_path = output_dir / f"summary_dashboard_{timestamp}.png"
        self.plot_summary_dashboard(report, fig_path)
        generated_figures.append(fig_path)

        print(f"Generated {len(generated_figures)} figures in: {output_dir}")
        return generated_figures

    def plot_scores_comparison(self, report: Dict[str, Any], output_path: Path):
        """Bar chart comparing average scores."""
        summary = report["comparison_summary"]

        models = ["GPT-3.5-Turbo", "GPT-4o-Mini"]
        scores = [
            summary["average_score"]["gpt-3.5-turbo"],
            summary["average_score"]["gpt-4o-mini"]
        ]

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(models, scores, color=['#3498db', '#e74c3c'], alpha=0.8, edgecolor='black')

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}%',
                   ha='center', va='bottom', fontweight='bold')

        # Add improvement annotation
        improvement = summary["average_score"]["improvement_percentage"]
        ax.text(0.5, max(scores) * 0.95, f'Improvement: {improvement:+.2f}%',
               ha='center', fontsize=12, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        ax.set_ylabel('Average Score (%)', fontweight='bold')
        ax.set_title('Model Performance: Average Scores', fontweight='bold', pad=20)
        ax.set_ylim(0, 100)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

    def plot_learning_gains(self, report: Dict[str, Any], output_path: Path):
        """Bar chart comparing learning gains."""
        summary = report["comparison_summary"]

        models = ["GPT-3.5-Turbo", "GPT-4o-Mini"]
        gains = [
            summary["learning_gain"]["gpt-3.5-turbo"],
            summary["learning_gain"]["gpt-4o-mini"]
        ]

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(models, gains, color=['#3498db', '#e74c3c'], alpha=0.8, edgecolor='black')

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.3f}',
                   ha='center', va='bottom', fontweight='bold')

        # Add interpretation thresholds
        ax.axhline(y=0.7, color='green', linestyle='--', alpha=0.5, label='High Gain (>0.7)')
        ax.axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='Medium Gain (0.3-0.7)')

        ax.set_ylabel("Hake's Normalized Learning Gain", fontweight='bold')
        ax.set_title('Learning Effectiveness: Normalized Gains', fontweight='bold', pad=20)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

    def plot_cost_comparison(self, report: Dict[str, Any], output_path: Path):
        """Bar chart comparing costs per student."""
        summary = report["comparison_summary"]

        models = ["GPT-3.5-Turbo", "GPT-4o-Mini"]
        costs = [
            summary["cost_per_student"]["gpt-3.5-turbo"],
            summary["cost_per_student"]["gpt-4o-mini"]
        ]

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(models, costs, color=['#3498db', '#e74c3c'], alpha=0.8, edgecolor='black')

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'${height:.4f}',
                   ha='center', va='bottom', fontweight='bold')

        # Add cost change annotation
        cost_change = summary["cost_per_student"]["change_percentage"]
        ax.text(0.5, max(costs) * 0.95,
               f'Cost Change: {cost_change:+.1f}%',
               ha='center', fontsize=12,
               bbox=dict(boxstyle='round',
                        facecolor='lightgreen' if cost_change < 0 else 'lightcoral',
                        alpha=0.5))

        ax.set_ylabel('Cost per Student (USD)', fontweight='bold')
        ax.set_title('Cost Efficiency: Per-Student API Costs', fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

    def plot_cost_effectiveness(self, report: Dict[str, Any], output_path: Path):
        """Bar chart comparing performance per dollar."""
        summary = report["comparison_summary"]

        models = ["GPT-3.5-Turbo", "GPT-4o-Mini"]
        perf_per_dollar = [
            summary["cost_effectiveness"]["gpt-3.5-turbo_perf_per_dollar"],
            summary["cost_effectiveness"]["gpt-4o-mini_perf_per_dollar"]
        ]

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(models, perf_per_dollar, color=['#3498db', '#e74c3c'], alpha=0.8, edgecolor='black')

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}',
                   ha='center', va='bottom', fontweight='bold')

        # Add improvement annotation
        improvement = summary["cost_effectiveness"]["improvement_percentage"]
        ax.text(0.5, max(perf_per_dollar) * 0.95,
               f'Improvement: {improvement:+.1f}%',
               ha='center', fontsize=12,
               bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

        ax.set_ylabel('Performance per Dollar (Score/$)', fontweight='bold')
        ax.set_title('Cost-Effectiveness: Performance per Dollar', fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

    def plot_citation_quality(self, report: Dict[str, Any], output_path: Path):
        """Bar chart comparing citation counts."""
        summary = report["comparison_summary"]

        models = ["GPT-3.5-Turbo", "GPT-4o-Mini"]
        citations = [
            summary["citation_quality"]["gpt-3.5-turbo_avg_citations"],
            summary["citation_quality"]["gpt-4o-mini_avg_citations"]
        ]

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(models, citations, color=['#3498db', '#e74c3c'], alpha=0.8, edgecolor='black')

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}',
                   ha='center', va='bottom', fontweight='bold')

        ax.set_ylabel('Average Citations per Session', fontweight='bold')
        ax.set_title('Response Quality: Citation Counts', fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

    def plot_summary_dashboard(self, report: Dict[str, Any], output_path: Path):
        """Multi-panel dashboard with all key metrics."""
        summary = report["comparison_summary"]

        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        fig.suptitle('Model Comparison Dashboard: GPT-3.5-Turbo vs GPT-4o-Mini',
                    fontsize=18, fontweight='bold', y=0.98)

        models = ["GPT-3.5", "GPT-4o"]
        colors = ['#3498db', '#e74c3c']

        # 1. Average Scores
        ax = axes[0, 0]
        scores = [
            summary["average_score"]["gpt-3.5-turbo"],
            summary["average_score"]["gpt-4o-mini"]
        ]
        ax.bar(models, scores, color=colors, alpha=0.8, edgecolor='black')
        ax.set_ylabel('Score (%)')
        ax.set_title('Average Scores', fontweight='bold')
        ax.set_ylim(0, 100)
        for i, v in enumerate(scores):
            ax.text(i, v + 1, f'{v:.1f}%', ha='center', fontweight='bold')

        # 2. Learning Gains
        ax = axes[0, 1]
        gains = [
            summary["learning_gain"]["gpt-3.5-turbo"],
            summary["learning_gain"]["gpt-4o-mini"]
        ]
        ax.bar(models, gains, color=colors, alpha=0.8, edgecolor='black')
        ax.set_ylabel('Normalized Gain')
        ax.set_title('Learning Gains', fontweight='bold')
        ax.axhline(y=0.7, color='green', linestyle='--', alpha=0.3)
        ax.axhline(y=0.3, color='orange', linestyle='--', alpha=0.3)
        for i, v in enumerate(gains):
            ax.text(i, v + 0.02, f'{v:.3f}', ha='center', fontweight='bold')

        # 3. Cost per Student
        ax = axes[0, 2]
        costs = [
            summary["cost_per_student"]["gpt-3.5-turbo"],
            summary["cost_per_student"]["gpt-4o-mini"]
        ]
        ax.bar(models, costs, color=colors, alpha=0.8, edgecolor='black')
        ax.set_ylabel('Cost (USD)')
        ax.set_title('Cost per Student', fontweight='bold')
        for i, v in enumerate(costs):
            ax.text(i, v + max(costs)*0.02, f'${v:.4f}', ha='center', fontweight='bold')

        # 4. Cost-Effectiveness
        ax = axes[1, 0]
        perf_per_dollar = [
            summary["cost_effectiveness"]["gpt-3.5-turbo_perf_per_dollar"],
            summary["cost_effectiveness"]["gpt-4o-mini_perf_per_dollar"]
        ]
        ax.bar(models, perf_per_dollar, color=colors, alpha=0.8, edgecolor='black')
        ax.set_ylabel('Score / $')
        ax.set_title('Cost-Effectiveness', fontweight='bold')
        for i, v in enumerate(perf_per_dollar):
            ax.text(i, v + max(perf_per_dollar)*0.02, f'{v:.1f}', ha='center', fontweight='bold')

        # 5. Citations
        ax = axes[1, 1]
        citations = [
            summary["citation_quality"]["gpt-3.5-turbo_avg_citations"],
            summary["citation_quality"]["gpt-4o-mini_avg_citations"]
        ]
        ax.bar(models, citations, color=colors, alpha=0.8, edgecolor='black')
        ax.set_ylabel('Citations')
        ax.set_title('Avg Citations per Session', fontweight='bold')
        for i, v in enumerate(citations):
            ax.text(i, v + 0.1, f'{v:.1f}', ha='center', fontweight='bold')

        # 6. Statistical Summary
        ax = axes[1, 2]
        ax.axis('off')

        # Get statistical info
        stats = report.get("statistical_analysis", {})
        comparisons = stats.get("statistical_comparisons", [])

        if comparisons:
            comp = comparisons[0]
            summary_text = f"""
Statistical Analysis

p-value: {comp.get('p_value', 0):.4f}
Significant: {'Yes' if comp.get('statistically_significant', False) else 'No'}

Effect Size (Cohen's d): {comp.get('effect_size_cohens_d', 0):.3f}

95% CI:
[{comp.get('confidence_interval_95', [0,0])[0]:.2f},
 {comp.get('confidence_interval_95', [0,0])[1]:.2f}]

Improvement:
{comp.get('improvement_percentage', 0):+.1f}%
            """

            ax.text(0.1, 0.5, summary_text, fontsize=11, family='monospace',
                   verticalalignment='center', bbox=dict(boxstyle='round',
                   facecolor='wheat', alpha=0.5))

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()


def main():
    """Example usage: visualize most recent report."""
    from pathlib import Path

    results_dir = Path("results/model_comparison")

    if not results_dir.exists():
        print(f"No results directory found at {results_dir}")
        print("Run the comparison experiment first:")
        print("  make compare-models")
        return

    # Find most recent JSON report
    json_reports = sorted(results_dir.glob("model_comparison_report_*.json"))

    if not json_reports:
        print("No comparison reports found!")
        print("Run: make compare-models")
        return

    latest_report = json_reports[-1]
    print(f"Visualizing: {latest_report.name}")

    # Generate visualizations
    visualizer = ComparisonVisualizer()
    figures = visualizer.visualize_report(latest_report)

    print(f"\n✅ Generated {len(figures)} figures:")
    for fig in figures:
        print(f"  - {fig.name}")


if __name__ == "__main__":
    main()
