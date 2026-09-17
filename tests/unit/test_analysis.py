"""
Unit tests for the automatic failure checkers and the statistical treatment.
"""

import pytest

from src.experiment import analysis
from src.experiment.checks import (
    _code_parses,
    module_strand,
    negotiation_checks,
    planning_checks,
    run_metrics,
)


def _module(module_id, title, topics, hours, prerequisites=None):
    return {"id": module_id, "title": title, "topics": topics, "estimated_hours": hours,
            "outcomes": ["Do the thing"], "prerequisites": prerequisites or []}


def _record(modules, *, goal="broad", budget=20.0, lessons=None, condition="A1", scenario="S01",
            planning_extra=None):
    syllabus = {"topic": "Python", "duration_weeks": 4, "weekly_time_hours": 5.0, "modules": modules}
    return {
        "scenario_id": scenario,
        "condition": {"id": condition},
        "repeat": 1,
        "model": {"requested": "m"},
        "corpus": {"similarity_threshold": 0.35},
        "scenario": {"total_hours": budget, "factors": {"goal_profile": goal}},
        "planning": {
            "extracted_syllabus": syllabus,
            "final_syllabus": syllabus,
            "schema_valid_as_extracted": True,
            "extraction_fallback": False,
            "max_negotiation_rounds": 3,
            "rounds_completed": 2,
            "approved": True,
            "negotiation_history": [{"role": "advocate", "content": "brief"},
                                    {"role": "designer", "content": "proposal"},
                                    {"role": "advocate", "content": "CONTINUE"},
                                    {"role": "designer", "content": "revised"}],
            "verdicts": ["CONTINUE", "APPROVED"],
            **(planning_extra or {}),
        },
        "modules": [{"module_id": m["id"], "title": m["title"], "topics": m["topics"],
                     "lessons": (lessons or {}).get(m["id"], []), "items": [], "errors": []}
                    for m in modules],
        "usage": {"calls": [], "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
                  "cost_usd": 0.0, "llm_errors": 0},
        "wall_clock_s": 1.0,
        "errors": [],
        "failed": False,
    }


def _lesson(passages, content="Lists are mutable.[1]", **kwargs):
    return {"topic": "Lists", "content": content, "mode": "grounded", "refused": False,
            "retrieved": [{"chunk_id": f"c{i}", "strand": s, "similarity": sim}
                          for i, (s, sim) in enumerate(passages)],
            "inline_citations": [{"passage_index": 1, "valid": True}], "call_id": None,
            "retrieval_s": 0.01, **kwargs}


class TestPlanningChecks:
    def test_budget_tolerance_follows_the_planner_thresholds(self):
        inside = planning_checks(_record([_module("m01-a", "Lists", ["Lists"], 16.0)]))
        below = planning_checks(_record([_module("m01-a", "Lists", ["Lists"], 15.9)]))
        above = planning_checks(_record([_module("m01-a", "Lists", ["Lists"], 22.1)]))
        assert inside["time_budget_satisfied"] and not below["time_budget_satisfied"]
        assert not above["time_budget_satisfied"]

    def test_prerequisite_cycle_is_detected(self):
        modules = [_module("m01-a", "A", ["x"], 10.0, ["m02-b"]), _module("m02-b", "B", ["y"], 10.0, ["m01-a"])]
        checks = planning_checks(_record(modules))
        assert checks["prerequisites_present"] and not checks["prerequisites_acyclic"]

    def test_unresolvable_prerequisite(self):
        checks = planning_checks(_record([_module("m01-a", "A", ["x"], 20.0, ["m09-missing"])]))
        assert checks["prerequisites_resolvable"] is False
        assert checks["unresolved_prerequisites"] == ["m09-missing"]

    def test_broad_goal_needs_every_strand(self):
        modules = [_module(f"m0{i}-x", t, [t], 5.0) for i, t in enumerate(
            ["Variables and data types", "Loops and conditionals", "Lists and dictionaries",
             "Classes and inheritance"], start=1)]
        assert planning_checks(_record(modules, goal="broad"))["goal_covered"] is True
        assert planning_checks(_record(modules[:3], goal="broad"))["goal_covered"] is False

    def test_narrow_goal_needs_half_the_modules_on_its_strand(self):
        data = _module("m01-a", "Lists and dictionaries", ["Lists", "Dictionaries"], 10.0)
        other = _module("m02-b", "Classes and inheritance", ["Classes"], 10.0)
        assert planning_checks(_record([data, other], goal="narrow"))["goal_covered"] is True
        assert planning_checks(_record([data, other, other], goal="narrow"))["goal_covered"] is False

    def test_constraint_rate_is_a_fraction_of_the_checks(self):
        checks = planning_checks(_record([_module("m01-a", "Lists", ["Lists"], 16.0)]))
        assert 0.0 <= checks["constraint_satisfaction_rate"] <= 1.0
        assert checks["all_constraints_satisfied"] is False  # only one module
        assert checks["module_count_in_range"] is False

    def test_module_strand_prefers_retrieved_passages_over_keywords(self):
        module = {"title": "Classes and objects", "topics": ["Inheritance"],
                  "lessons": [_lesson([("py03-data-structures", 0.6), ("py03-data-structures", 0.5)])]}
        assert module_strand(module) == "py03-data-structures"
        assert module_strand({"title": "Classes and objects", "topics": ["Inheritance"], "lessons": []}) == "py04-oop"


class TestResponseChecks:
    def test_low_confidence_and_off_strand_passages(self):
        module = _module("m01-a", "Lists and dictionaries", ["Lists"], 16.0)
        lessons = {"m01-a": [_lesson([("py03-data-structures", 0.36), ("py01-basics", 0.36)])]}
        metrics = run_metrics(_record([module], lessons=lessons))
        assert metrics["rates"]["low_confidence_retrieval"] == 1.0
        assert metrics["rates"]["off_strand_passage_rate"] == 0.5

    def test_model_written_refusal_is_separate_from_the_canned_one(self):
        module = _module("m01-a", "Lists", ["Lists"], 16.0)
        lessons = {"m01-a": [
            _lesson([("py03-data-structures", 0.6)], content="The context does not contain information on this."),
            _lesson([], content="I don't have enough information in my knowledge base.", refused=True),
        ]}
        metrics = run_metrics(_record([module], lessons=lessons))
        assert metrics["rates"]["model_written_refusal"] == 0.5
        assert metrics["rates"]["no_passage_above_threshold"] == 0.5

    @pytest.mark.parametrize("text,expected", [
        ("```python\nx = [1, 2]\n```", True),
        ("```python\nx = [1, 2\n```", False),
        ("```python\n>>> print('hi')\nhi\n```", True),          # transcript with output
        ("```python\nHello, world!\n```", None),                 # output fenced as code
        ("```python\nif x:\n    # do something\n```", True),     # teaching skeleton
        ("no code at all", None),
        ("```python\nprint 'py2'\n```", False),
    ])
    def test_code_parse_rules(self, text, expected):
        assert _code_parses(text) is expected


class TestNegotiationChecks:
    def test_reaching_the_limit_without_approval(self):
        record = _record([_module("m01-a", "A", ["x"], 20.0)],
                         planning_extra={"approved": False, "rounds_completed": 3})
        checks = negotiation_checks(record)
        assert checks["max_rounds_without_approval"] is True
        assert checks["no_revision_occurred"] is False

    def test_no_revision_when_the_designer_proposed_once(self):
        record = _record([_module("m01-a", "A", ["x"], 20.0)], planning_extra={
            "negotiation_history": [{"role": "advocate", "content": "brief"},
                                    {"role": "designer", "content": "proposal"},
                                    {"role": "advocate", "content": "APPROVED"}]})
        assert negotiation_checks(record)["no_revision_occurred"] is True

    def test_role_inversion_suspected_when_the_advocate_writes_the_syllabus(self):
        record = _record([_module("m01-a", "A", ["x"], 20.0)], planning_extra={
            "negotiation_history": [
                {"role": "advocate", "content": "brief"},
                {"role": "designer", "content": "READY"},
                {"role": "advocate", "content": "m01-intro m02-loops m03-data estimated_hours 5"}]})
        assert negotiation_checks(record)["roles_inverted_suspected"] is True


class TestStatistics:
    def test_wilson_interval(self):
        low, high = analysis.wilson_interval(5, 10)
        assert low == pytest.approx(0.2365, abs=1e-3) and high == pytest.approx(0.7635, abs=1e-3)
        assert analysis.wilson_interval(10, 10)[1] == pytest.approx(1.0)
        assert analysis.wilson_interval(0, 0) is None

    def test_cliffs_delta(self):
        assert analysis.cliffs_delta([2, 3, 4], [0, 1]) == 1.0
        assert analysis.cliffs_delta([0, 1], [2, 3, 4]) == -1.0
        assert analysis.cliffs_delta([1, 2], [1, 2]) == 0.0

    def test_bootstrap_ci_is_reproducible_and_brackets_the_median(self):
        values = [0.1 * i for i in range(20)]
        first = analysis.bootstrap_ci(values)
        assert first == analysis.bootstrap_ci(values)
        assert first[0] <= 0.95 <= first[1]

    def test_mcnemar_exact(self):
        assert analysis.mcnemar_exact(0, 5, 0, 0)["p_value"] == pytest.approx(0.0625)
        assert analysis.mcnemar_exact(3, 0, 0, 3)["p_value"] == 1.0

    def test_support_requires_the_interval_to_exclude_zero_in_the_predicted_direction(self):
        better = [(f"S{i:02d}", 0.9, 0.5) for i in range(24)]
        result = analysis.paired_comparison(better, "higher")
        assert result["supported"] is True and result["median_difference"] == pytest.approx(0.4)
        assert analysis.paired_comparison(better, "lower")["supported"] is False

        noisy = [(f"S{i:02d}", 0.5 + (i % 2) * 0.2, 0.5 + ((i + 1) % 2) * 0.2) for i in range(24)]
        assert analysis.paired_comparison(noisy, "higher")["supported"] is False

    def test_ties_are_reported_and_do_not_claim_support(self):
        identical = [(f"S{i:02d}", 0.5, 0.5) for i in range(24)]
        result = analysis.paired_comparison(identical, "higher")
        assert result["ties"] == 24 and result["p_value"] == 1.0 and result["supported"] is False


class TestCompare:
    def _runs(self):
        runs = []
        for condition, value in [("A1", 0.9), ("A2", 0.4)]:
            for i in range(1, 25):
                module = _module("m01-a", "Lists", ["Lists"], 16.0)
                record = _record([module], condition=condition, scenario=f"S{i:02d}")
                metrics = run_metrics(record)
                metrics["planning"]["constraint_satisfaction_rate"] = value
                metrics["planning"]["time_budget_satisfied"] = condition == "A1"
                runs.append(metrics)
        return runs

    def test_pairs_by_scenario(self):
        result = analysis.compare(self._runs(), "A1", "A2", "constraint_satisfaction_rate", "higher")
        assert result["scenarios_compared"] == 24
        assert result["median_difference"] == pytest.approx(0.5)
        assert result["supported"] is True

    def test_binary_outcome_uses_mcnemar(self):
        result = analysis.compare(self._runs(), "A1", "A2", "time_budget_satisfied", "higher", kind="binary")
        assert result["proportion_first"] == 1.0 and result["proportion_second"] == 0.0
        assert result["mcnemar"]["discordant"] == 24
        assert result["mcnemar"]["p_value"] < 1e-6

    def test_missing_condition_is_reported_not_guessed(self):
        result = analysis.compare(self._runs(), "A1", "A5", "constraint_satisfaction_rate", "higher")
        assert result["status"] == "no data"

    def test_report_marks_annotated_outcomes_pending(self):
        text, summary = analysis.report("e1", "m", self._runs())
        assert "pending E3 annotation" in text
        assert any(p.get("status") == "pending annotation" for p in summary["primary"])
