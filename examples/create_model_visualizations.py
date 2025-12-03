"""
Generate comprehensive visualizations comparing all three models:
- GPT-3.5-Turbo
- GPT-4o-mini
- Mistral 7B
"""

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# Set style for publication-quality figures
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10

# Data from the comparison results
models = ['GPT-3.5-Turbo', 'GPT-4o-mini', 'Mistral 7B']
model_types = ['Commercial', 'Commercial', 'Open-Source']
scores = [69.04, 74.85, 64.74]
learning_gains = [0.553, 0.631, 0.471]
costs_per_student = [0.0157, 0.0034, 0.0]
citations = [4.0, 5.87, 2.9]
source_diversity = [2.47, 4.43, 2.0]
confidence = [0.795, 0.907, 0.738]

# Annual costs for 10,000 students
annual_costs = [cost * 10000 for cost in costs_per_student]

# Create output directory
output_dir = Path('results/three_model_comparison')
output_dir.mkdir(parents=True, exist_ok=True)

# Color scheme
colors = ['#FF6B6B', '#4ECDC4', '#95E1D3']  # Red, Teal, Mint

print("Creating visualizations for all 3 models...")

# 1. Performance Comparison (Scores)
print("1. Performance comparison...")
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(models, scores, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

# Add value labels on bars
for i, (bar, score) in enumerate(zip(bars, scores)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{score:.2f}%',
            ha='center', va='bottom', fontweight='bold', fontsize=11)

    # Add model type below
    ax.text(bar.get_x() + bar.get_width()/2., -5,
            f'({model_types[i]})',
            ha='center', va='top', fontsize=9, style='italic')

ax.set_ylabel('Average Score (%)', fontweight='bold')
ax.set_title('Model Performance Comparison\nPython Programming Fundamentals (4 weeks, 30 students/model)',
             fontweight='bold', pad=20)
ax.set_ylim(0, max(scores) + 10)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '1_performance_comparison.png', bbox_inches='tight')
plt.close()

# 2. Learning Gains Comparison
print("2. Learning gains comparison...")
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(models, learning_gains, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, (bar, gain) in enumerate(zip(bars, learning_gains)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
            f'{gain:.3f}',
            ha='center', va='bottom', fontweight='bold', fontsize=11)

ax.set_ylabel('Normalized Learning Gain', fontweight='bold')
ax.set_title('Learning Gain Comparison\n(Hake\'s Normalized Gain)',
             fontweight='bold', pad=20)
ax.set_ylim(0, max(learning_gains) + 0.1)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '2_learning_gains.png', bbox_inches='tight')
plt.close()

# 3. Cost Comparison (Per Student)
print("3. Cost per student comparison...")
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(models, costs_per_student, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, (bar, cost) in enumerate(zip(bars, costs_per_student)):
    height = bar.get_height()
    if cost == 0:
        label = 'FREE ✓'
        y_pos = 0.0005
    else:
        label = f'${cost:.4f}'
        y_pos = height + 0.001
    ax.text(bar.get_x() + bar.get_width()/2., y_pos,
            label,
            ha='center', va='bottom', fontweight='bold', fontsize=11,
            color='green' if cost == 0 else 'black')

ax.set_ylabel('Cost per Student (USD)', fontweight='bold')
ax.set_title('Cost Comparison per Student',
             fontweight='bold', pad=20)
ax.set_ylim(0, max(costs_per_student) + 0.005)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '3_cost_per_student.png', bbox_inches='tight')
plt.close()

# 4. Annual Cost for 10,000 Students
print("4. Annual cost comparison...")
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(models, annual_costs, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, (bar, cost) in enumerate(zip(bars, annual_costs)):
    height = bar.get_height()
    if cost == 0:
        label = 'FREE\n$0/year'
        y_pos = 2000
    else:
        label = f'${cost:,.0f}'
        y_pos = height + 2000
    ax.text(bar.get_x() + bar.get_width()/2., y_pos,
            label,
            ha='center', va='bottom', fontweight='bold', fontsize=11,
            color='green' if cost == 0 else 'black')

ax.set_ylabel('Annual Cost (USD)', fontweight='bold')
ax.set_title('Annual Cost Comparison\n(10,000 students)',
             fontweight='bold', pad=20)
ax.set_ylim(0, max(annual_costs) + 20000)
ax.ticklabel_format(style='plain', axis='y')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '4_annual_cost_10k_students.png', bbox_inches='tight')
plt.close()

# 5. Cost-Effectiveness (Performance per Dollar)
print("5. Cost-effectiveness comparison...")
fig, ax = plt.subplots(figsize=(10, 6))

# Calculate performance per dollar (avoid division by zero)
cost_effectiveness = []
labels = []
for i, (score, cost) in enumerate(zip(scores, costs_per_student)):
    if cost == 0:
        cost_effectiveness.append(0)  # We'll handle this specially
        labels.append('∞\n(FREE)')
    else:
        ce = score / cost
        cost_effectiveness.append(ce)
        labels.append(f'{ce:,.0f}')

# Create bars (set Mistral to max value for visualization)
plot_values = cost_effectiveness.copy()
plot_values[2] = max([v for v in cost_effectiveness if v > 0]) * 1.5  # Mistral

bars = ax.bar(models, plot_values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, (bar, label) in enumerate(zip(bars, labels)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1000,
            label,
            ha='center', va='bottom', fontweight='bold', fontsize=11,
            color='green' if i == 2 else 'black')

ax.set_ylabel('Performance / Dollar\n(Score per USD)', fontweight='bold')
ax.set_title('Cost-Effectiveness Comparison\n(Higher is Better)',
             fontweight='bold', pad=20)
ax.grid(axis='y', alpha=0.3)

# Add note for Mistral
ax.text(0.98, 0.02, 'Note: Mistral 7B is FREE (infinite value)',
        transform=ax.transAxes, ha='right', va='bottom',
        fontsize=9, style='italic', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig(output_dir / '5_cost_effectiveness.png', bbox_inches='tight')
plt.close()

# 6. Citation Quality Comparison
print("6. Citation quality comparison...")
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(models, citations, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, (bar, cit) in enumerate(zip(bars, citations)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.2,
            f'{cit:.1f}',
            ha='center', va='bottom', fontweight='bold', fontsize=11)

ax.set_ylabel('Average Citations per Student', fontweight='bold')
ax.set_title('Citation Quality Comparison',
             fontweight='bold', pad=20)
ax.set_ylim(0, max(citations) + 1)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '6_citation_quality.png', bbox_inches='tight')
plt.close()

# 7. Comprehensive Dashboard
print("7. Creating comprehensive dashboard...")
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# Performance
ax1 = fig.add_subplot(gs[0, 0])
ax1.bar(models, scores, color=colors, alpha=0.8, edgecolor='black')
ax1.set_title('Average Score (%)', fontweight='bold')
ax1.set_ylim(0, max(scores) + 10)
ax1.tick_params(axis='x', rotation=15)
for i, v in enumerate(scores):
    ax1.text(i, v + 1, f'{v:.1f}%', ha='center', fontsize=9, fontweight='bold')

# Learning Gain
ax2 = fig.add_subplot(gs[0, 1])
ax2.bar(models, learning_gains, color=colors, alpha=0.8, edgecolor='black')
ax2.set_title('Learning Gain', fontweight='bold')
ax2.set_ylim(0, max(learning_gains) + 0.1)
ax2.tick_params(axis='x', rotation=15)
for i, v in enumerate(learning_gains):
    ax2.text(i, v + 0.02, f'{v:.3f}', ha='center', fontsize=9, fontweight='bold')

# Cost per Student
ax3 = fig.add_subplot(gs[0, 2])
ax3.bar(models, costs_per_student, color=colors, alpha=0.8, edgecolor='black')
ax3.set_title('Cost/Student (USD)', fontweight='bold')
ax3.set_ylim(0, max(costs_per_student) + 0.005)
ax3.tick_params(axis='x', rotation=15)
for i, v in enumerate(costs_per_student):
    label = 'FREE' if v == 0 else f'${v:.4f}'
    ax3.text(i, v + 0.0005, label, ha='center', fontsize=8, fontweight='bold')

# Citations
ax4 = fig.add_subplot(gs[1, 0])
ax4.bar(models, citations, color=colors, alpha=0.8, edgecolor='black')
ax4.set_title('Avg Citations', fontweight='bold')
ax4.set_ylim(0, max(citations) + 1)
ax4.tick_params(axis='x', rotation=15)
for i, v in enumerate(citations):
    ax4.text(i, v + 0.15, f'{v:.1f}', ha='center', fontsize=9, fontweight='bold')

# Source Diversity
ax5 = fig.add_subplot(gs[1, 1])
ax5.bar(models, source_diversity, color=colors, alpha=0.8, edgecolor='black')
ax5.set_title('Source Diversity', fontweight='bold')
ax5.set_ylim(0, max(source_diversity) + 1)
ax5.tick_params(axis='x', rotation=15)
for i, v in enumerate(source_diversity):
    ax5.text(i, v + 0.15, f'{v:.2f}', ha='center', fontsize=9, fontweight='bold')

# Confidence
ax6 = fig.add_subplot(gs[1, 2])
ax6.bar(models, confidence, color=colors, alpha=0.8, edgecolor='black')
ax6.set_title('Avg Confidence', fontweight='bold')
ax6.set_ylim(0, 1.0)
ax6.tick_params(axis='x', rotation=15)
for i, v in enumerate(confidence):
    ax6.text(i, v + 0.03, f'{v:.3f}', ha='center', fontsize=9, fontweight='bold')

# Annual Cost
ax7 = fig.add_subplot(gs[2, :2])
bars = ax7.bar(models, annual_costs, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax7.set_title('Annual Cost for 10,000 Students', fontweight='bold')
ax7.set_ylabel('Cost (USD)', fontweight='bold')
ax7.ticklabel_format(style='plain', axis='y')
for i, v in enumerate(annual_costs):
    label = 'FREE\n($0)' if v == 0 else f'${v:,.0f}'
    ax7.text(i, v + 1500, label, ha='center', fontsize=10, fontweight='bold',
            color='green' if v == 0 else 'black')

# Summary text
ax8 = fig.add_subplot(gs[2, 2])
ax8.axis('off')
summary_text = """
KEY FINDINGS

Performance:
• GPT-4o-mini: 74.85%
• GPT-3.5-Turbo: 69.04%
• Mistral 7B: 64.74%

Cost Savings:
• Mistral vs GPT-4o: $34K/yr
• GPT-4o vs GPT-3.5: $123K/yr

Trade-off:
• Mistral achieves 86.5%
  of GPT-4o performance
  at ZERO cost
"""
ax8.text(0.1, 0.9, summary_text, transform=ax8.transAxes,
         fontsize=9, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

fig.suptitle('Comprehensive Model Comparison: Commercial vs Open-Source LLMs\n' +
             'Python Programming Fundamentals (30 students/model, 4 weeks)',
             fontsize=14, fontweight='bold', y=0.98)

plt.savefig(output_dir / '7_comprehensive_dashboard.png', bbox_inches='tight')
plt.close()

# 8. Performance vs Cost Scatter Plot
print("8. Performance vs cost scatter...")
fig, ax = plt.subplots(figsize=(10, 8))

# For better visualization, use log scale for cost (handling 0)
plot_costs = [max(c, 0.0001) for c in costs_per_student]  # Avoid log(0)

scatter = ax.scatter(plot_costs, scores, s=500, c=colors, alpha=0.7,
                     edgecolor='black', linewidth=2)

# Add labels for each point
for i, model in enumerate(models):
    # Offset labels
    x_offset = 0.0001 if i == 2 else 0
    y_offset = 3 if i == 1 else -3

    ax.annotate(model,
                (plot_costs[i], scores[i]),
                xytext=(5 + x_offset*10000, y_offset),
                textcoords='offset points',
                fontsize=11,
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor=colors[i], alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', lw=1.5))

ax.set_xlabel('Cost per Student (USD, log scale)', fontweight='bold', fontsize=12)
ax.set_ylabel('Average Score (%)', fontweight='bold', fontsize=12)
ax.set_title('Performance vs Cost Trade-off\n(Closer to top-left is better)',
             fontweight='bold', fontsize=13, pad=20)
ax.set_xscale('log')
ax.grid(True, alpha=0.3)

# Add ideal region annotation
ax.axhspan(70, 80, alpha=0.1, color='green', label='Target Performance Range')
ax.axvspan(0.00005, 0.001, alpha=0.1, color='blue', label='Low Cost Range')

# Add legend
ax.legend(loc='lower right', fontsize=10)

plt.tight_layout()
plt.savefig(output_dir / '8_performance_vs_cost.png', bbox_inches='tight')
plt.close()

print(f"\n✅ All visualizations created successfully!")
print(f"📁 Saved to: {output_dir.absolute()}\n")
print("Files created:")
print("  1. 1_performance_comparison.png")
print("  2. 2_learning_gains.png")
print("  3. 3_cost_per_student.png")
print("  4. 4_annual_cost_10k_students.png")
print("  5. 5_cost_effectiveness.png")
print("  6. 6_citation_quality.png")
print("  7. 7_comprehensive_dashboard.png")
print("  8. 8_performance_vs_cost.png")
