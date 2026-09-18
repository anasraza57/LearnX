"""
Aggregates run records into scenario-level rates and applies the pre-registered
statistical treatment.

The unit of analysis is the scenario (D28): for each scenario and condition one
rate is computed, giving paired observations per contrast. Comparisons use the
Wilcoxon signed-rank test, with the median paired difference and a bootstrap
confidence interval, Cliff's delta as a second effect size, and Wilson intervals
for descriptive proportions. Binary per-scenario outcomes use an exact McNemar
test instead, which is the documented exception.

A contrast counts as supported only if the 95% interval on the paired difference
excludes zero in the direction predicted before running (D29). Outcomes that
depend on human annotation are listed as pending rather than approximated.

Usage:
    python -m src.experiment.analysis --experiment e1 --model gpt-5.4-mini
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from scipy import stats

from .checks import run_metrics
from .runner import EXPERIMENT_DIRS, RESULTS_DIR, model_slug

BOOTSTRAP_SAMPLES = 10000
BOOTSTRAP_SEED = 20260917
CONFIDENCE = 0.95

# Pre-registered primary outcomes (handoff section 4.7.1, D29). "higher"/"lower"
# is the direction predicted for the first condition of the pair.
PRIMARY_CONTRASTS = [
    {"contrast": "A1 vs A2", "isolates": "agent decomposition", "conditions": ("A1", "A2"),
     "outcome": "constraint_satisfaction_rate", "direction": "higher", "kind": "rate"},
    {"contrast": "A1 vs A3", "isolates": "retrieval grounding", "conditions": ("A1", "A3"),
     "outcome": "unsupported_claim_rate", "direction": "lower", "kind": "annotated"},
    {"contrast": "A1 vs A4", "isolates": "the negotiation protocol", "conditions": ("A1", "A4"),
     "outcome": "time_budget_satisfied", "direction": "higher", "kind": "binary"},
    {"contrast": "A1 vs A5", "isolates": "the citation instruction", "conditions": ("A1", "A5"),
     "outcome": "misattribution_rate", "direction": "lower", "kind": "annotated"},
    {"contrast": "A1 vs A5", "isolates": "the citation instruction", "conditions": ("A1", "A5"),
     "outcome": "missing_citation_rate", "direction": "lower", "kind": "annotated"},
]

# Automatic measures reported alongside, for every contrast against A1. These are
# descriptive: they were not pre-registered as primary outcomes.
SECONDARY_OUTCOMES = [
    "no_passage_above_threshold", "low_confidence_retrieval", "off_strand_passage_rate",
    "model_written_refusal", "response_without_citation", "invalid_citation_marker_rate",
    "citations_per_response", "code_blocks_per_response", "code_block_parse_failure",
    "response_with_broken_code", "item_valid", "item_placeholder",
    "item_retrieval_failed",
]


# The E4 failure taxonomy (handoff section 4.5), as (stage, failure mode, where
# the value comes from, unit). Instruction-stage and assessment-stage retrieval
# failures are separate rows, per B12. Grounding and citation failures come from
# the annotation study and are listed as pending rather than approximated.
FAILURE_TAXONOMY = [
    ("Retrieval (instruction)", "No passage above threshold", ("rates", "no_passage_above_threshold"), "response"),
    ("Retrieval (instruction)", "All passages near threshold", ("rates", "low_confidence_retrieval"), "response"),
    ("Retrieval (instruction)", "Passage from another strand", ("rates", "off_strand_passage_rate"), "passage"),
    ("Retrieval (assessment)", "No passage retrieved for the item", ("rates", "item_retrieval_failed"), "item"),
    ("Planning", "Schema invalid as extracted", ("planning", "schema_valid_as_extracted"), "scenario-inverted"),
    ("Planning", "Reply was not parseable JSON", ("planning", "extraction_parsed"), "scenario-inverted"),
    ("Planning", "Time budget not satisfied", ("planning", "time_budget_satisfied"), "scenario-inverted"),
    ("Planning", "Prerequisites unresolvable", ("planning", "prerequisites_resolvable"), "scenario-inverted"),
    ("Planning", "Prerequisite graph cyclic", ("planning", "prerequisites_acyclic"), "scenario-inverted"),
    ("Planning", "Stated goal uncovered", ("planning", "goal_covered"), "scenario-inverted"),
    ("Planning", "Final syllabus over budget after repair", ("planning", "final_hours_over_budget"), "scenario"),
    ("Negotiation", "No revision occurred", ("negotiation", "no_revision_occurred"), "scenario"),
    ("Negotiation", "Round limit without approval", ("negotiation", "max_rounds_without_approval"), "scenario"),
    ("Negotiation", "Role inversion suspected", ("negotiation", "roles_inverted_suspected"), "scenario"),
    ("Response", "Canned refusal (nothing retrieved)", ("rates", "no_passage_above_threshold"), "response"),
    ("Response", "Refusal written by the model", ("rates", "model_written_refusal"), "response"),
    ("Response", "Truncated at the token limit", ("rates", "truncated_response"), "response"),
    ("Response", "Code block that does not parse", ("rates", "code_block_parse_failure"), "code block"),
    ("Assessment", "Item fails its schema", ("rates", "item_valid"), "item-inverted"),
    ("Assessment", "Placeholder item (reply unparseable)", ("rates", "item_placeholder"), "item"),
]


def _taxonomy_value(metrics: Dict[str, Any], source: Tuple[str, str], unit: str) -> Optional[float]:
    section, key = source
    value = metrics[section].get(key)
    if value is None:
        return None
    value = float(value)
    return 1.0 - value if unit.endswith("-inverted") else value


def wilson_interval(successes: int, total: int, confidence: float = CONFIDENCE) -> Optional[Tuple[float, float]]:
    """Wilson score interval for a proportion (better than the normal approximation at the extremes)."""
    if total == 0:
        return None
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    phat = successes / total
    denominator = 1 + z**2 / total
    centre = (phat + z**2 / (2 * total)) / denominator
    half = z * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Cliff's delta: how often a exceeds b, minus how often b exceeds a."""
    if not a or not b:
        return None
    greater = sum((x > y) - (x < y) for x in a for y in b)
    return greater / (len(a) * len(b))


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = statistics.median,
    samples: int = BOOTSTRAP_SAMPLES,
    confidence: float = CONFIDENCE,
) -> Optional[Tuple[float, float]]:
    """Percentile bootstrap interval, with a fixed seed so the result is reproducible."""
    values = list(values)
    if len(values) < 2:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    draws = sorted(
        statistic([values[rng.randrange(len(values))] for _ in values]) for _ in range(samples)
    )
    low = draws[int((1 - confidence) / 2 * samples)]
    high = draws[min(samples - 1, int((1 + confidence) / 2 * samples))]
    return low, high


def mcnemar_exact(both: int, only_a: int, only_b: int, neither: int) -> Dict[str, Any]:
    """Exact McNemar test on the discordant pairs."""
    discordant = only_a + only_b
    p_value = 1.0 if discordant == 0 else float(stats.binomtest(only_a, discordant, 0.5).pvalue)
    return {
        "both": both, "only_first": only_a, "only_second": only_b, "neither": neither,
        "discordant": discordant, "p_value": p_value,
    }


def paired_comparison(pairs: List[Tuple[str, float, float]], direction: str,
                      statistic: Callable[[Sequence[float]], float] = statistics.median) -> Dict[str, Any]:
    """
    Wilcoxon signed-rank plus effect sizes on paired scenario-level rates.

    `statistic` summarises the paired differences and is what the confidence
    interval is built on. Binary outcomes pass the mean, because the median of
    differences drawn from {-1, 0, +1} is zero unless more than half the pairs
    are discordant in one direction, which would make the decision rule
    unreachable regardless of the size of the effect.
    """
    first = [a for _, a, _ in pairs]
    second = [b for _, _, b in pairs]
    differences = [a - b for a, b in zip(first, second)]
    non_zero = [d for d in differences if d != 0]

    result: Dict[str, Any] = {
        "n_pairs": len(pairs),
        "median_first": statistics.median(first) if first else None,
        "median_second": statistics.median(second) if second else None,
        "median_difference": statistics.median(differences) if differences else None,
        "mean_difference": statistics.fmean(differences) if differences else None,
        "summary_statistic": "mean" if statistic is statistics.fmean else "median",
        "ties": len(differences) - len(non_zero),
        # Cliff's delta compares all pairs across the two groups, so it ignores
        # the pairing; reported as the unpaired effect size
        "cliffs_delta_unpaired": cliffs_delta(first, second),
        "difference_ci": bootstrap_ci(differences, statistic=statistic),
        "direction_predicted": direction,
    }
    if non_zero:
        wilcoxon_statistic, p_value = stats.wilcoxon(first, second, zero_method="wilcox")
        result["wilcoxon_statistic"], result["p_value"] = float(wilcoxon_statistic), float(p_value)
    else:
        result["wilcoxon_statistic"], result["p_value"] = None, 1.0

    result["point_estimate"] = statistic(differences) if differences else None
    ci = result["difference_ci"]
    if ci is None:
        result["supported"] = None
    elif direction == "higher":
        result["supported"] = ci[0] > 0
    else:
        result["supported"] = ci[1] < 0
    return result


def _outcome_value(metrics: Dict[str, Any], outcome: str) -> Optional[float]:
    if outcome in metrics["rates"]:
        return metrics["rates"][outcome]
    planning = metrics["planning"]
    if outcome in planning:
        value = planning[outcome]
        return float(value) if isinstance(value, (int, float, bool)) else None
    return None


def load_runs(experiment: str, model: str, results_dir: Path = RESULTS_DIR) -> List[Dict[str, Any]]:
    """Every completed run record for a model, as metrics. Failed runs are excluded."""
    root = results_dir / EXPERIMENT_DIRS[experiment] / model_slug(model)
    runs = []
    for path in sorted(root.glob("*/*.json")):
        if path.name.endswith(".failed.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("failed"):
            continue
        runs.append(run_metrics(record))
    return runs


def compare(runs: List[Dict[str, Any]], first: str, second: str, outcome: str, direction: str,
            kind: str = "rate") -> Dict[str, Any]:
    """One contrast on one outcome, paired by scenario."""
    by_condition = {c: {r["scenario_id"]: r for r in runs if r["condition"] == c} for c in (first, second)}
    shared = sorted(set(by_condition[first]) & set(by_condition[second]))
    pairs = []
    for scenario in shared:
        a = _outcome_value(by_condition[first][scenario], outcome)
        b = _outcome_value(by_condition[second][scenario], outcome)
        if a is not None and b is not None:
            pairs.append((scenario, float(a), float(b)))

    header = {"conditions": [first, second], "outcome": outcome, "kind": kind,
              "scenarios_compared": len(pairs)}
    if not pairs:
        return {**header, "status": "no data"}

    if kind == "binary":
        both = sum(1 for _, a, b in pairs if a and b)
        only_a = sum(1 for _, a, b in pairs if a and not b)
        only_b = sum(1 for _, a, b in pairs if b and not a)
        neither = sum(1 for _, a, b in pairs if not a and not b)
        first_successes, second_successes = both + only_a, both + only_b
        comparison = paired_comparison(pairs, direction, statistic=statistics.fmean)
        mcnemar = mcnemar_exact(both, only_a, only_b, neither)
        # The pre-registered test for a binary per-scenario outcome is exact
        # McNemar; the signed-rank statistic on 0/1 data is not meaningful here
        comparison.update({"p_value": mcnemar["p_value"], "wilcoxon_statistic": None,
                           "test": "exact McNemar"})
        return {
            **header,
            "status": "computed",
            "proportion_first": first_successes / len(pairs),
            "proportion_second": second_successes / len(pairs),
            "ci_first": wilson_interval(first_successes, len(pairs)),
            "ci_second": wilson_interval(second_successes, len(pairs)),
            "mcnemar": mcnemar,
            "direction_predicted": direction,
            **comparison,
        }
    return {**header, "status": "computed", "test": "Wilcoxon signed-rank",
            **paired_comparison(pairs, direction)}


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, tuple):
        return f"[{value[0]:+.{digits}f}, {value[1]:+.{digits}f}]"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def report(experiment: str, model: str, runs: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """A markdown report and the same content as data."""
    conditions = sorted({r["condition"] for r in runs})
    lines = [f"# {experiment} results: {model}", "",
             f"Runs: {len(runs)} across conditions {', '.join(conditions)}. "
             f"Unit of analysis: the scenario (D28). Intervals are 95% and the decision rule is D29.", ""]

    lines += ["## Coverage", "", "| Condition | Scenarios | Responses | Items | Cost (USD) | Median response latency (s) |",
              "|---|---|---|---|---|---|"]
    summary: Dict[str, Any] = {"conditions": {}}
    for condition in conditions:
        subset = [r for r in runs if r["condition"] == condition]
        costs = [r["cost"]["cost_usd"] for r in subset if r["cost"]["cost_usd"] is not None]
        latencies = [r["cost"]["median_response_latency_s"] for r in subset
                     if r["cost"]["median_response_latency_s"]]
        summary["conditions"][condition] = {
            "scenarios": len(subset),
            "responses": sum(r["counts"]["responses"] for r in subset),
            "items": sum(r["counts"]["items"] for r in subset),
            "cost_usd": sum(costs) if costs else None,
            "median_latency_s": statistics.median(latencies) if latencies else None,
        }
        row = summary["conditions"][condition]
        lines.append(f"| {condition} | {row['scenarios']} | {row['responses']} | {row['items']} | "
                     f"{_fmt(row['cost_usd'], 2)} | {_fmt(row['median_latency_s'], 1)} |")

    lines += ["", "## Pre-registered contrasts", "",
              "| Contrast | Isolates | Outcome | Median A | Median B | Paired difference | 95% CI | Cliff's delta (unpaired) | p | Supported |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    summary["primary"] = []
    for spec in PRIMARY_CONTRASTS:
        first, second = spec["conditions"]
        if spec["kind"] == "annotated":
            lines.append(f"| {spec['contrast']} | {spec['isolates']} | {spec['outcome']} | "
                         f"pending E3 annotation | | | | | | |")
            summary["primary"].append({**spec, "status": "pending annotation"})
            continue
        result = compare(runs, first, second, spec["outcome"], spec["direction"], spec["kind"])
        summary["primary"].append({**spec, **result})
        if result["status"] != "computed":
            lines.append(f"| {spec['contrast']} | {spec['isolates']} | {spec['outcome']} | no data | | | | | | |")
            continue
        lines.append(
            f"| {spec['contrast']} | {spec['isolates']} | {spec['outcome']} | "
            f"{_fmt(result['median_first'])} | {_fmt(result['median_second'])} | "
            f"{_fmt(result['point_estimate'])} | {_fmt(result['difference_ci'])} | "
            f"{_fmt(result['cliffs_delta_unpaired'])} | {_fmt(result['p_value'])} ({result['test']}) | "
            f"{_fmt(result['supported'])} (predicted {result['direction_predicted']}) |"
        )
        if spec["kind"] == "binary":
            m = result["mcnemar"]
            lines.append(f"| | | proportions | {_fmt(result['proportion_first'])} "
                         f"{_fmt(result['ci_first'])} | {_fmt(result['proportion_second'])} "
                         f"{_fmt(result['ci_second'])} | McNemar exact | discordant {m['discordant']} "
                         f"({m['only_first']} vs {m['only_second']}) | | {_fmt(m['p_value'])} | |")

    lines += ["", "## Automatic measures by condition", "",
              "| Measure | " + " | ".join(conditions) + " |", "|---" * (len(conditions) + 1) + "|"]
    summary["descriptive"] = {}
    for outcome in SECONDARY_OUTCOMES:
        cells = []
        summary["descriptive"][outcome] = {}
        for condition in conditions:
            values = [v for v in (_outcome_value(r, outcome) for r in runs if r["condition"] == condition)
                      if v is not None]
            median = statistics.median(values) if values else None
            summary["descriptive"][outcome][condition] = {
                "median": median, "n": len(values),
                "mean": statistics.fmean(values) if values else None,
            }
            cells.append(_fmt(median))
        lines.append(f"| {outcome} | " + " | ".join(cells) + " |")

    lines += ["", "## Planning checks by condition", "",
              "| Check | " + " | ".join(conditions) + " |", "|---" * (len(conditions) + 1) + "|"]
    checks = ["schema_valid_as_extracted", "extraction_parsed", "time_budget_satisfied",
              "module_count_in_range", "goal_covered", "prerequisites_present",
              "prerequisites_resolvable", "prerequisites_acyclic", "final_hours_over_budget",
              "all_constraints_satisfied"]
    summary["planning"] = {}
    for check in checks:
        cells = []
        summary["planning"][check] = {}
        for condition in conditions:
            values = [bool(r["planning"][check]) for r in runs if r["condition"] == condition]
            rate = sum(values) / len(values) if values else None
            interval = wilson_interval(sum(values), len(values)) if values else None
            summary["planning"][check][condition] = {"rate": rate, "n": len(values), "wilson_ci": interval}
            cells.append(f"{_fmt(rate, 2)} {_fmt(interval, 2)}" if rate is not None else "n/a")
        lines.append(f"| {check} | " + " | ".join(cells) + " |")

    # Each planning check against A1, paired by scenario. The pre-registered
    # outcome is a composite, so this shows which component drives a difference
    # and whether one failure mode is being counted by more than one check.
    others = [c for c in conditions if c != "A1"]
    if "A1" in conditions and others:
        lines += ["", "## Planning checks against A1, paired by scenario (exact McNemar)", "",
                  "| Check | " + " | ".join(f"A1 vs {c}" for c in others) + " |",
                  "|---" * (len(others) + 1) + "|"]
        summary["planning_contrasts"] = {}
        for check in checks:
            cells = []
            summary["planning_contrasts"][check] = {}
            for other in others:
                result = compare(runs, "A1", other, check, "higher", kind="binary")
                summary["planning_contrasts"][check][other] = result
                if result["status"] != "computed":
                    cells.append("n/a")
                    continue
                m = result["mcnemar"]
                cells.append(f"{result['proportion_first']:.2f} vs {result['proportion_second']:.2f}, "
                             f"discordant {m['only_first']}/{m['only_second']}, p={m['p_value']:.3f}")
            lines.append(f"| {check} | " + " | ".join(cells) + " |")

    negotiation = [r for r in runs if r["negotiation"]["negotiation_enabled"]]
    if negotiation:
        lines += ["", "## Negotiation", "",
                  f"Runs with negotiation enabled: {len(negotiation)}. "
                  f"Approved: {sum(1 for r in negotiation if r['negotiation']['approved'])}. "
                  f"Reached the round limit without approval: "
                  f"{sum(1 for r in negotiation if r['negotiation']['max_rounds_without_approval'])}. "
                  f"No revision occurred: {sum(1 for r in negotiation if r['negotiation']['no_revision_occurred'])}. "
                  f"Role inversion suspected (needs confirmation by reading the transcript): "
                  f"{sum(1 for r in negotiation if r['negotiation']['roles_inverted_suspected'])}."]

    # Pooled totals, for measures whose unit is not the scenario. The tables above
    # summarise per-scenario rates, which is right for the paired tests but is not
    # the rate over all items, blocks or markers.
    lines += ["", "## Pooled totals (over every unit, not per scenario)", "",
              "| Quantity | " + " | ".join(conditions) + " |", "|---" * (len(conditions) + 1) + "|"]
    summary["pooled"] = {}
    pooled_rows = [
        ("Responses", lambda rs: sum(r["counts"]["responses"] for r in rs), None),
        ("Responses refused (nothing retrieved)", None, ("no_passage_above_threshold", "responses")),
        ("Assessment items", lambda rs: sum(r["counts"]["items"] for r in rs), None),
    ]
    for label, count, _ in pooled_rows:
        if count is None:
            continue
        cells = []
        for condition in conditions:
            cells.append(str(count([r for r in runs if r["condition"] == condition])))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    for label, key, num, den in [
        ("Items failing their schema", "item", "items_invalid", "items"),
        ("Placeholder items", "item", "items_placeholder", "items"),
        ("Code blocks written", "block", "code_blocks", None),
        ("Code blocks that do not parse", "block", "code_blocks_failing", "code_blocks"),
        ("Citation markers emitted", "marker", "citation_markers", None),
        ("Citation markers pointing outside the passages", "marker", "invalid_markers", "citation_markers"),
    ]:
        cells = []
        summary["pooled"][num] = {}
        for condition in conditions:
            subset = [r for r in runs if r["condition"] == condition]
            total = sum(r["pooled"][num] for r in subset)
            if den:
                base = sum(r["pooled"][den] for r in subset)
                value = f"{total} ({total / base:.2%})" if base else f"{total}"
                summary["pooled"][num][condition] = {"count": total, "of": base}
            else:
                value = f"{total}"
                summary["pooled"][num][condition] = {"count": total}
            cells.append(value)
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += ["", "## E4 failure taxonomy: rates by stage", "",
              "Each row is a failure mode from the taxonomy. Values are the mean of the "
              "per-scenario rates, since the scenario is the unit of analysis (D28), over the unit "
              "named. Claim support and citation correctness come from the annotation study (E3).", "",
              "| Stage | Failure mode | Unit | " + " | ".join(conditions) + " |",
              "|---|---|---|" + "---|" * len(conditions)]
    summary["failure_taxonomy"] = []
    for stage, mode, source, unit in FAILURE_TAXONOMY:
        cells, row = [], {"stage": stage, "mode": mode, "unit": unit.replace("-inverted", ""), "rates": {}}
        for condition in conditions:
            values = [v for v in (_taxonomy_value(r, source, unit) for r in runs if r["condition"] == condition)
                      if v is not None]
            mean = statistics.fmean(values) if values else None
            row["rates"][condition] = {"mean": mean, "n": len(values)}
            cells.append(_fmt(mean, 3))
        summary["failure_taxonomy"].append(row)
        lines.append(f"| {stage} | {mode} | per {unit.replace('-inverted', '')} | " + " | ".join(cells) + " |")
    for stage, mode in [("Grounding and citation", "Unsupported claim"),
                        ("Grounding and citation", "Misattributed citation"),
                        ("Grounding and citation", "Missing citation")]:
        lines.append(f"| {stage} | {mode} | per claim | " + " | ".join(["pending E3"] * len(conditions)) + " |")

    lines += ["", "## Not computed here", "",
              "Claim support, citation correctness and whether an item is answerable from the corpus "
              "come from the E3 annotation study and are not approximated by any measure above.", ""]
    return "\n".join(lines), summary


def backend_report(arms: List[Tuple[str, str]], condition: str = "A1") -> Tuple[str, Dict[str, Any]]:
    """
    E2: the architecture held fixed while the backend varies.

    Each arm contributes its runs of one condition (A1 by default), relabelled by
    backend so the same paired machinery applies. The scenarios are identical
    across backends, so differences are paired by scenario. These comparisons
    were not pre-registered: E2 asks what model capability contributes, and is
    reported descriptively with intervals rather than as hypothesis tests.
    """
    runs: List[Dict[str, Any]] = []
    for experiment, model in arms:
        for metrics in load_runs(experiment, model):
            if metrics["condition"] != condition:
                continue
            metrics = {**metrics, "backend": model, "condition": model}
            runs.append(metrics)
    labels = [model for _, model in arms if any(r["condition"] == model for r in runs)]
    if not labels:
        raise SystemExit("No completed runs found for any of those arms")

    lines = [f"# E2 backends: condition {condition} across models", "",
             "The architecture, corpus, scenarios and prompts are identical across these arms; only "
             "the model differs. Paired by scenario. Not pre-registered: reported descriptively.", "",
             "## Coverage", "",
             "| Backend | Scenarios | Responses | Items | API cost (USD) | Median latency (s) | Runs failed |",
             "|---|---|---|---|---|---|---|"]
    summary: Dict[str, Any] = {"condition": condition, "arms": {}, "measures": {}, "against_first": {}}
    for label in labels:
        subset = [r for r in runs if r["condition"] == label]
        costs = [r["cost"]["cost_usd"] for r in subset if r["cost"]["cost_usd"] is not None]
        latencies = [r["cost"]["median_response_latency_s"] for r in subset
                     if r["cost"]["median_response_latency_s"]]
        entry = {
            "scenarios": len(subset),
            "responses": sum(r["counts"]["responses"] for r in subset),
            "items": sum(r["counts"]["items"] for r in subset),
            "cost_usd": sum(costs) if costs else None,
            "median_latency_s": statistics.median(latencies) if latencies else None,
        }
        summary["arms"][label] = entry
        lines.append(f"| {label} | {entry['scenarios']} | {entry['responses']} | {entry['items']} | "
                     f"{_fmt(entry['cost_usd'], 2)} | {_fmt(entry['median_latency_s'], 1)} | 0 |")

    # Planning checks are pass/fail per scenario, so they are proportions with a
    # Wilson interval. The rest are per-scenario rates, summarised by median.
    planning_keys = ["schema_valid_as_extracted", "extraction_parsed", "time_budget_satisfied",
                     "prerequisites_resolvable", "goal_covered", "all_constraints_satisfied"]
    lines += ["", "## Planning checks by backend (proportion of scenarios, 95% Wilson)", "",
              "| Check | " + " | ".join(labels) + " |", "|---" * (len(labels) + 1) + "|"]
    for key in planning_keys:
        cells = []
        summary["measures"].setdefault(key, {})
        for label in labels:
            values = [bool(_outcome_value(r, key)) for r in runs if r["condition"] == label
                      and _outcome_value(r, key) is not None]
            rate = sum(values) / len(values) if values else None
            interval = wilson_interval(sum(values), len(values)) if values else None
            summary["measures"][key][label] = {"rate": rate, "n": len(values), "wilson_ci": interval}
            cells.append(f"{_fmt(rate, 2)} {_fmt(interval, 2)}" if rate is not None else "n/a")
        lines.append(f"| {key} | " + " | ".join(cells) + " |")

    lines += ["", "## Automatic measures by backend (median of per-scenario rates)", "",
              "| Measure | " + " | ".join(labels) + " |", "|---" * (len(labels) + 1) + "|"]
    for key in SECONDARY_OUTCOMES:
        cells = []
        summary["measures"].setdefault(key, {})
        for label in labels:
            values = [v for v in (_outcome_value(r, key) for r in runs if r["condition"] == label)
                      if v is not None]
            median = statistics.median(values) if values else None
            summary["measures"][key][label] = {"median": median, "n": len(values)}
            cells.append(_fmt(median))
        lines.append(f"| {key} | " + " | ".join(cells) + " |")

    reference = labels[0]
    others = labels[1:]
    if others:
        lines += ["", f"## Paired differences against {reference}", "",
                  "| Measure | " + " | ".join(f"vs {o}" for o in others) + " |",
                  "|---" * (len(others) + 1) + "|"]
        for key in ["constraint_satisfaction_rate", "schema_valid_as_extracted", "time_budget_satisfied",
                    "no_passage_above_threshold", "citations_per_response", "item_valid",
                    "code_block_parse_failure"]:
            cells = []
            summary["against_first"].setdefault(key, {})
            for other in others:
                result = compare(runs, reference, other, key, "higher")
                summary["against_first"][key][other] = result
                if result["status"] != "computed":
                    cells.append("n/a")
                    continue
                cells.append(f"{result['median_difference']:+.3f} "
                             f"[{result['difference_ci'][0]:+.3f}, {result['difference_ci'][1]:+.3f}]"
                             if result["difference_ci"] else f"{result['median_difference']:+.3f}")
            lines.append(f"| {key} | " + " | ".join(cells) + " |")

    lines += ["", "Local backends report no API cost. Their cost of ownership (energy and amortised "
              "hardware) is computed separately by `python -m src.experiment.tco`.", ""]
    return "\n".join(lines), summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", choices=sorted(EXPERIMENT_DIRS), default="e1")
    parser.add_argument("--model")
    parser.add_argument("--arm", nargs=2, action="append", metavar=("EXPERIMENT", "MODEL"),
                        help="an E2 arm to compare, repeatable: --arm e1 gpt-5.4-mini --arm e2 mistral:7b")
    parser.add_argument("--condition", default="A1", help="condition to compare across backends")
    parser.add_argument("--out", type=Path, help="where to write the report (default: alongside the records)")
    args = parser.parse_args()

    if args.arm:
        text, summary = backend_report([(e, m) for e, m in args.arm], args.condition)
        out = args.out or RESULTS_DIR / EXPERIMENT_DIRS["e2"]
        out.mkdir(parents=True, exist_ok=True)
        print(text)
        (out / "backends.md").write_text(text + "\n", encoding="utf-8")
        (out / "backends.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"\nWritten: {out / 'backends.md'} and {out / 'backends.json'}")
        return

    if not args.model:
        parser.error("--model is required unless --arm is used")
    runs = load_runs(args.experiment, args.model)
    if not runs:
        raise SystemExit(f"No completed runs for {args.model} under {args.experiment}")
    text, summary = report(args.experiment, args.model, runs)
    print(text)

    out = args.out or RESULTS_DIR / EXPERIMENT_DIRS[args.experiment] / model_slug(args.model)
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.md").write_text(text + "\n", encoding="utf-8")
    (out / "analysis.json").write_text(json.dumps({"runs": runs, "summary": summary}, indent=2, default=str),
                                       encoding="utf-8")
    print(f"\nWritten: {out / 'analysis.md'} and {out / 'analysis.json'}")


if __name__ == "__main__":
    main()
