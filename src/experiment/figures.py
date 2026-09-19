"""
Figures for the results section, drawn from the analysis output.

Four figures replace the deleted ones (handoff section 6):
- the pre-registered contrasts, as paired differences with their intervals;
- planning checks by condition, which is where the ablation differences live;
- failure rates by pipeline stage (E4);
- cost and latency per scenario.

Every bar carries its value as text: three of the five series colours sit below
3:1 contrast on the chart surface, so identity is never left to colour alone.
Conditions keep a fixed colour throughout, so a figure that drops one does not
repaint the rest.

A fifth replaces figure D10, the model comparison dashboard, which the submitted
version built from hard-coded numbers.

Usage:
    python -m src.experiment.figures --experiment e1 --model gpt-5.4-mini
    python -m src.experiment.figures --backends
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .runner import EXPERIMENT_DIRS, RESULTS_DIR, model_slug  # noqa: E402

# Validated categorical palette, in fixed slot order (see the data-viz palette
# reference; checked with its validator for the light surface).
CONDITION_COLOURS = {
    "A1": "#2a78d6",  # blue
    "A2": "#eb6834",  # orange
    "A3": "#1baf7a",  # aqua
    "A4": "#eda100",  # yellow
    "A5": "#e87ba4",  # magenta
}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e3e2de"

CONDITION_LABELS = {
    "A1": "A1 full",
    "A2": "A2 single agent",
    "A3": "A3 no retrieval",
    "A4": "A4 no negotiation",
    "A5": "A5 no citation instruction",
}

# Backends keep a fixed colour and a fixed order: proprietary by generation, then
# open-weight by generation. Same validated hues as the conditions.
BACKEND_ORDER = ["gpt-5.4-mini", "gpt-4o-mini", "gpt-3.5-turbo", "mistral-7b-32k", "gemma3-4b-32k"]
BACKEND_COLOURS = {
    "gpt-5.4-mini": "#2a78d6",
    "gpt-4o-mini": "#eb6834",
    "gpt-3.5-turbo": "#1baf7a",
    "mistral-7b-32k": "#eda100",
    "gemma3-4b-32k": "#e87ba4",
}
BACKEND_LABELS = {
    "gpt-5.4-mini": "GPT-5.4 mini\n(proprietary, current)",
    "gpt-4o-mini": "GPT-4o mini\n(proprietary, mid)",
    "gpt-3.5-turbo": "GPT-3.5 Turbo\n(proprietary, older)",
    "mistral-7b-32k": "Mistral 7B\n(open weight, older)",
    "gemma3-4b-32k": "Gemma 3 4B\n(open weight, current)",
}

# Panels of the backend figure. Proportions share a 0 to 1 axis; the last two
# carry their own units and so are never plotted on a shared scale with them.
BACKEND_PANELS = [
    ("schema_valid_as_extracted", "Syllabus schema valid", "proportion"),
    ("time_budget_satisfied", "Time budget satisfied", "proportion"),
    ("goal_covered", "Stated goal covered", "proportion"),
    ("all_constraints_satisfied", "All constraints satisfied", "proportion"),
    ("citations_per_response", "Citation markers per response", "count"),
    ("__cost__", "Cost for 24 scenarios", "usd"),
]

PLANNING_CHECKS = [
    ("schema_valid_as_extracted", "Schema valid\n(as extracted)"),
    ("time_budget_satisfied", "Time budget\nsatisfied"),
    ("prerequisites_resolvable", "Prerequisites\nresolvable"),
    ("goal_covered", "Stated goal\ncovered"),
    ("module_count_in_range", "Module count\nin range"),
    ("all_constraints_satisfied", "All constraints\nsatisfied"),
]

FAILURE_ROWS = [
    ("Retrieval", "No passage above threshold"),
    ("Retrieval", "All passages near threshold"),
    ("Retrieval", "Passage from another strand"),
    ("Retrieval", "No passage retrieved for the item"),
    ("Planning", "Schema invalid as extracted"),
    ("Planning", "Prerequisites unresolvable"),
    ("Planning", "Stated goal uncovered"),
    ("Planning", "Time budget not satisfied"),
    ("Response", "Refusal written by the model"),
    ("Response", "Code block that does not parse"),
]


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.size": 9, "font.family": "sans-serif",
        "text.color": INK, "axes.labelcolor": INK_MUTED, "axes.titlecolor": INK,
        "xtick.color": INK_MUTED, "ytick.color": INK_MUTED,
        "axes.edgecolor": GRID, "axes.linewidth": 0.8,
        "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "figure.dpi": 150,
    })


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")  # vector, for the manuscript
    plt.close(fig)
    return path


def _conditions(summary: Dict[str, Any]) -> List[str]:
    return [c for c in CONDITION_COLOURS if c in summary["conditions"]]


def figure_contrasts(summary: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    """Pre-registered contrasts: paired difference with its 95% interval."""
    rows = [c for c in summary["primary"] if c.get("status") == "computed" and c.get("difference_ci")]
    pending = [c for c in summary["primary"] if c.get("status") == "pending annotation"]
    if not rows:
        return None

    fig, ax = plt.subplots(figsize=(7.6, 1.2 + 0.52 * (len(rows) + len(pending))))
    labels = []
    for i, row in enumerate(reversed(rows)):
        low, high = row["difference_ci"]
        colour = CONDITION_COLOURS[row["conditions"][1]]
        ax.plot([low, high], [i, i], color=colour, linewidth=2, solid_capstyle="round", zorder=2)
        ax.plot([row["point_estimate"]], [i], "o", color=colour, markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
        ax.text(high + 0.012, i,
                f"{row['point_estimate']:+.3f}  [{low:+.3f}, {high:+.3f}]   "
                f"p={row['p_value']:.3f} ({row['test']})",
                va="center", ha="left", fontsize=8, color=INK)
        labels.append(f"{row['contrast']}\n{row['outcome'].replace('_', ' ')}")
    for j, row in enumerate(pending, start=len(rows)):
        ax.text(0.0, j, "  pending the annotation study (E3)", va="center", ha="left",
                fontsize=8, color=INK_MUTED, style="italic")
        labels.append(f"{row['contrast']}\n{row['outcome'].replace('_', ' ')}")

    ax.axvline(0, color=INK_MUTED, linewidth=1, zorder=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Paired difference against A1 (positive favours A1), 95% bootstrap interval")
    ax.set_xlim(-0.32, 0.45)
    ax.set_ylim(-0.65, len(labels) - 0.35)
    ax.grid(axis="x", alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_title("Pre-registered contrasts: no effect detected in the predicted direction",
                 loc="left", fontsize=10, pad=12)
    return _save(fig, out_dir, "e1_contrasts")


def figure_planning_checks(summary: Dict[str, Any], out_dir: Path) -> Path:
    """Where the conditions actually differ: pass rate per planning check."""
    conditions = _conditions(summary)
    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    width = 0.8 / len(conditions)

    for slot, condition in enumerate(conditions):
        xs, heights, errs = [], [], [[], []]
        for i, (key, _) in enumerate(PLANNING_CHECKS):
            entry = summary["planning"][key][condition]
            rate, ci = entry["rate"], entry["wilson_ci"]
            xs.append(i + slot * width - 0.4 + width / 2)
            heights.append(rate)
            errs[0].append(rate - ci[0] if ci else 0)
            errs[1].append(ci[1] - rate if ci else 0)
        bars = ax.bar(xs, heights, width * 0.86, color=CONDITION_COLOURS[condition],
                      label=CONDITION_LABELS[condition], zorder=2)
        ax.errorbar(xs, heights, yerr=errs, fmt="none", ecolor=INK_MUTED, elinewidth=0.9,
                    capsize=2, zorder=3)
        for bar, height in zip(bars, heights):
            ax.text(bar.get_x() + bar.get_width() / 2, -0.035, f"{height:.2f}".lstrip("0"),
                    ha="center", va="top", fontsize=6.5, color=INK, rotation=90)

    ax.set_xticks(range(len(PLANNING_CHECKS)))
    ax.set_xticklabels([label for _, label in PLANNING_CHECKS], fontsize=8)
    ax.tick_params(axis="x", pad=26)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Proportion of scenarios (95% Wilson interval)")
    ax.grid(axis="y", alpha=0.7)
    ax.set_axisbelow(True)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.02), fontsize=8)
    ax.set_title("Planning checks by condition: the single agent differs only on schema validity\n"
                 "and prerequisites", loc="left", fontsize=10, pad=44)
    return _save(fig, out_dir, "e1_planning_checks")


def figure_failures(summary: Dict[str, Any], out_dir: Path) -> Path:
    """E4 failure rates by pipeline stage."""
    conditions = _conditions(summary)
    rows = [row for row in summary["failure_taxonomy"]
            if (row["stage"].split(" (")[0], row["mode"]) in FAILURE_ROWS]
    fig, ax = plt.subplots(figsize=(8.2, 1.8 + 0.62 * len(rows)))
    height = 0.8 / len(conditions)

    for slot, condition in enumerate(conditions):
        ys, values = [], []
        for i, row in enumerate(rows):
            value = row["rates"][condition]["mean"]
            if value is None:
                continue
            ys.append(len(rows) - 1 - i + slot * height - 0.4 + height / 2)
            values.append(value)
        ax.barh(ys, values, height * 0.86, color=CONDITION_COLOURS[condition],
                label=CONDITION_LABELS[condition], zorder=2)
        for y, value in zip(ys, values):
            if value > 0.004:
                ax.text(value + 0.006, y, f"{value:.2f}".lstrip("0"), va="center", ha="left",
                        fontsize=6.5, color=INK)

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{row['stage'].split(' (')[0]}: {row['mode']}" for row in reversed(rows)], fontsize=8)
    ax.set_xlabel("Failure rate (mean of per-scenario rates)")
    ax.set_xlim(0, max(0.55, ax.get_xlim()[1]))
    ax.grid(axis="x", alpha=0.7)
    ax.set_axisbelow(True)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.01), fontsize=8)
    ax.set_title("Failure rates by pipeline stage", loc="left", fontsize=10, pad=52)
    return _save(fig, out_dir, "e1_failures_by_stage")


def figure_cost(runs: List[Dict[str, Any]], out_dir: Path) -> Path:
    """Cost and latency per scenario, one panel each: two measures, never one axis."""
    conditions = [c for c in CONDITION_COLOURS if any(r["condition"] == c for r in runs)]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.4))

    for ax, (key, section, label, unit) in zip(axes, [
        ("cost_usd", "cost", "Cost per scenario", "USD"),
        ("median_response_latency_s", "cost", "Median response latency", "seconds"),
    ]):
        for slot, condition in enumerate(conditions):
            values = [r[section][key] for r in runs if r["condition"] == condition and r[section][key] is not None]
            if not values:
                continue
            colour = CONDITION_COLOURS[condition]
            ax.scatter([slot + (i % 5 - 2) * 0.045 for i in range(len(values))], values,
                       s=14, color=colour, alpha=0.55, linewidths=0, zorder=2)
            mean = sum(values) / len(values)
            ax.plot([slot - 0.28, slot + 0.28], [mean, mean], color=colour, linewidth=2.5,
                    solid_capstyle="round", zorder=3)
            ax.text(slot + 0.33, mean, f"{mean:.2f}" if unit == "USD" else f"{mean:.1f}",
                    ha="left", va="center", fontsize=7.5, color=INK)
        ax.set_xticks(range(len(conditions)))
        ax.set_xticklabels(conditions, fontsize=8)
        ax.set_xlim(-0.55, len(conditions) - 0.25)
        ax.set_ylabel(f"{label} ({unit})")
        ax.grid(axis="y", alpha=0.7)
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)

    fig.suptitle("Cost and latency per scenario: removing retrieval is the most expensive condition",
                 x=0.02, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, out_dir, "e1_cost_latency")


def figure_backends(data: Dict[str, Any], out_dir: Path) -> Path:
    """
    E2 across backends: the figure that replaces D10.

    Six panels rather than one axis, because the quantities do not share units.
    Proportions carry their Wilson intervals; cost and citation counts have their
    own scales and are never plotted against the proportions.
    """
    arms = [b for b in BACKEND_ORDER if b in data["arms"]]
    fig, axes = plt.subplots(2, 3, figsize=(10.4, 6.2))

    for ax, (key, title, kind) in zip(axes.flat, BACKEND_PANELS):
        values, errs = [], [[], []]
        for backend in arms:
            if key == "__cost__":
                value = data["arms"][backend]["cost_usd"] or 0.0
                values.append(value)
                errs[0].append(0); errs[1].append(0)
                continue
            entry = data["measures"][key][backend]
            value = entry.get("rate", entry.get("median"))
            value = 0.0 if value is None else value
            values.append(value)
            ci = entry.get("wilson_ci")
            errs[0].append(value - ci[0] if ci else 0)
            errs[1].append(ci[1] - value if ci else 0)

        ys = list(range(len(arms)))[::-1]
        colours = [BACKEND_COLOURS[b] for b in arms]
        ax.barh(ys, values, 0.66, color=colours, zorder=2)
        if any(errs[0]) or any(errs[1]):
            ax.errorbar(values, ys, xerr=errs, fmt="none", ecolor=INK_MUTED,
                        elinewidth=0.9, capsize=2, zorder=3)

        span = max(values + [0.001])
        # The label sits past the interval, not past the bar, or it lands on the cap
        ends = [v + e for v, e in zip(values, errs[1])]
        for y, value, end in zip(ys, values, ends):
            if kind == "usd":
                text = "no API cost" if value == 0 else f"${value:.2f}"
            elif kind == "count":
                text = f"{value:.1f}"
            else:
                text = f"{value:.2f}".lstrip("0")
            ax.text(end + span * 0.04, y, text, va="center", ha="left",
                    fontsize=7.5, color=INK)

        ax.set_yticks(ys)
        ax.set_yticklabels([BACKEND_LABELS[b] for b in arms], fontsize=6.8)
        ax.set_xlim(0, span * 1.35)
        ax.set_title(title, loc="left", fontsize=9)
        ax.grid(axis="x", alpha=0.7)
        ax.set_axisbelow(True)
        if kind == "proportion":
            ax.set_xlim(0, 1.25)
            ax.set_xticks([0, 0.5, 1.0])

    fig.suptitle("Condition A1 across five backends, 24 scenarios each, no failed run\n"
                 "Proportions carry 95% Wilson intervals; the two right-hand panels have their own units",
                 x=0.005, ha="left", fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _save(fig, out_dir, "e2_backends")


def build_backends() -> List[Path]:
    root = RESULTS_DIR / EXPERIMENT_DIRS["e2"]
    data = json.loads((root / "backends.json").read_text(encoding="utf-8"))
    _style()
    return [figure_backends(data, root / "figures")]


def build(experiment: str, model: str) -> List[Path]:
    root = RESULTS_DIR / EXPERIMENT_DIRS[experiment] / model_slug(model)
    data = json.loads((root / "analysis.json").read_text(encoding="utf-8"))
    out_dir = root / "figures"
    _style()
    written = [figure_contrasts(data["summary"], out_dir),
               figure_planning_checks(data["summary"], out_dir),
               figure_failures(data["summary"], out_dir),
               figure_cost(data["runs"], out_dir)]
    return [p for p in written if p]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", choices=sorted(EXPERIMENT_DIRS), default="e1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--backends", action="store_true",
                        help="draw the cross-backend figure from results/e2_backends/backends.json")
    args = parser.parse_args()
    for path in (build_backends() if args.backends else build(args.experiment, args.model)):
        print(f"Written: {path}")


if __name__ == "__main__":
    main()
