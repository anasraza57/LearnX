"""
Guards the numbers quoted in the write-up against the analysis they come from.

Every figure in the handoff and the draft sections was recomputed several times
as measurement errors were found, and a stale number in prose is exactly the
failure this revision exists to correct. These tests re-derive the headline
figures from the stored analysis and assert that the documents still say them.

They skip when the analysis output is absent, so a fresh clone still passes.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "results" / "e1_ablation" / "gpt-5.4-mini" / "analysis.json"
DOCUMENTS = {
    "handoff": ROOT / "LearnX Revision Handoff.md",
    "results": ROOT / "docs" / "results_draft.md",
    "methods": ROOT / "docs" / "methods_draft.md",
    "discussion": ROOT / "docs" / "discussion_draft.md",
}


@pytest.fixture(scope="module")
def summary():
    if not ANALYSIS.exists():
        pytest.skip("no analysis output in this checkout")
    return json.loads(ANALYSIS.read_text(encoding="utf-8"))["summary"]


@pytest.fixture(scope="module")
def runs():
    if not ANALYSIS.exists():
        pytest.skip("no analysis output in this checkout")
    return json.loads(ANALYSIS.read_text(encoding="utf-8"))["runs"]


def _text(name):
    path = DOCUMENTS[name]
    if not path.exists():
        pytest.skip(f"{path.name} is not in this checkout")
    return path.read_text(encoding="utf-8")


def _pooled(runs, condition, field):
    return sum(r["pooled"][field] for r in runs if r["condition"] == condition)


class TestHeadlineContrast:
    def test_the_documents_quote_the_current_effect_size_and_p(self, summary):
        contrast = summary["primary"][0]
        assert contrast["outcome"] == "constraint_satisfaction_rate"
        # Either rounding of the effect size is acceptable; a superseded value is not
        renderings = {f"{contrast['cliffs_delta_unpaired']:.2f}".lstrip("-"),
                      f"{contrast['cliffs_delta_unpaired']:.3f}".lstrip("-")}
        p_value = f"{contrast['p_value']:.3f}"
        for name in ("handoff", "results"):
            text = _text(name)
            assert any(r in text for r in renderings), \
                f"{name} quotes no current rendering of Cliff's delta {renderings}"
            assert p_value in text, f"{name} does not quote p = {p_value}"

    def test_no_draft_still_quotes_a_superseded_figure(self):
        """
        The manuscript drafts must carry only current figures. The handoff is
        exempt because it is the change log: recording what a number used to be,
        and why it changed, is its job.
        """
        superseded = ["-0.365", "p = 0.021", "0.365", "100% schema-valid",
                      "16,474", "10,244", "17,224"]
        for name in ("results", "methods", "discussion"):
            text = _text(name)
            for stale in superseded:
                assert stale not in text, f"{name} still quotes the superseded {stale!r}"

    def test_neither_measurable_contrast_is_reported_as_supported(self, summary):
        for contrast in summary["primary"]:
            if contrast.get("status") == "computed":
                assert contrast["supported"] is False


class TestPooledRates:
    def test_code_block_failure_rates_are_quoted_pooled(self, runs):
        for condition, expected in [("A1", "0.19%"), ("A3", "2.18%")]:
            blocks = _pooled(runs, condition, "code_blocks")
            failing = _pooled(runs, condition, "code_blocks_failing")
            assert f"{failing / blocks:.2%}" == expected
        assert "2.18%" in _text("handoff") and "0.19%" in _text("handoff")

    def test_item_validity_is_not_claimed_to_be_perfect(self, runs):
        invalid = _pooled(runs, "A1", "items_invalid")
        assert invalid > 0, "A1 did produce invalid items; the guard below is only useful if it did"
        assert "4 invalid items of 946" in _text("handoff")

    def test_refusal_rate_is_quoted_pooled_not_as_a_median(self, runs):
        refused = _pooled(runs, "A1", "responses_refused")
        responses = _pooled(runs, "A1", "responses")
        assert f"{refused / responses:.1%}" == "12.2%"
        assert "12.2%" in _text("handoff")
        assert "12.2%" in _text("methods")

    def test_citation_marker_totals_match(self, runs):
        assert _pooled(runs, "A1", "citation_markers") == 15261
        assert _pooled(runs, "A1", "invalid_markers") == 5
        # Without the citation instruction the model emits no marker at all; without
        # retrieval it emits a handful that cannot refer to anything
        assert _pooled(runs, "A5", "citation_markers") == 0
        assert _pooled(runs, "A3", "citation_markers") == 8
        assert _pooled(runs, "A3", "invalid_markers") == 8
        for name in ("handoff", "results", "methods"):
            assert "15,261" in _text(name)


class TestPlanningClaims:
    def test_schema_validity_with_and_without_prerequisites(self, summary):
        with_prereqs = summary["planning"]["schema_valid_as_extracted"]
        without = summary["planning"]["schema_valid_ignoring_prerequisites"]
        assert round(with_prereqs["A1"]["rate"], 2) == 0.54
        assert round(with_prereqs["A2"]["rate"], 2) == 0.96
        # The claim the write-up rests on: the gap closes once prerequisites go
        assert round(without["A1"]["rate"], 2) == round(without["A2"]["rate"], 2) == 0.96
        assert "0.96" in _text("results")

    def test_every_condition_ends_over_budget(self, summary):
        over = summary["planning"]["final_hours_over_budget"]
        assert over["A1"]["rate"] == 1.0
        # The write-up must carry the consequence, however it is worded
        text = _text("results")
        assert "exceeded the budget in every run" in text
        assert "61 to 83 hours" in text


@pytest.fixture(scope="module")
def backends():
    path = ROOT / "results" / "e2_backends" / "backends.json"
    if not path.exists():
        pytest.skip("no backend comparison in this checkout")
    return json.loads(path.read_text(encoding="utf-8"))


class TestBackendComparison:
    """The E2 numbers in the results draft, checked against backends.json."""

    def test_every_arm_ran_the_same_scenarios_without_failures(self, backends):
        for name, arm in backends["arms"].items():
            assert arm["scenarios"] == 24, f"{name} did not run all 24 scenarios"

    def test_the_draft_quotes_the_measured_costs(self, backends):
        text = _text("results")
        for name, expected in (("gpt-4o-mini", "0.57"), ("gpt-3.5-turbo", "1.21")):
            cost = backends["arms"][name]["cost_usd"]
            assert f"{cost:.2f}" == expected, f"{name} cost moved to {cost:.2f}"
            assert f"${expected}" in text, f"the results draft does not quote ${expected}"

    def test_local_arms_report_no_api_cost(self, backends):
        for name in ("mistral-7b-32k", "gemma3-4b-32k"):
            assert backends["arms"][name]["cost_usd"] is None, \
                f"{name} is local and must not carry an API cost"

    def test_the_draft_quotes_the_current_planning_rates(self, backends):
        text = _text("results")
        for measure in ("schema_valid_as_extracted", "time_budget_satisfied"):
            for name, entry in backends["measures"][measure].items():
                rendered = f"{entry['rate']:.2f}"
                assert rendered in text, \
                    f"the results draft does not quote {measure} {rendered} for {name}"

    def test_the_proprietary_composite_difference_is_reported_as_null(self, backends):
        """The headline E2 claim: the composite does not separate the API models."""
        against = backends["against_first"]["constraint_satisfaction_rate"]
        for name in ("gpt-4o-mini", "gpt-3.5-turbo"):
            low, high = against[name]["difference_ci"]
            assert low <= 0 <= high, \
                f"the interval against {name} no longer includes zero; the draft says it does"


class TestRunProvenance:
    """
    Every arm must have run against the same corpus and scenario set, or the
    comparisons between them mean nothing. Each manifest records the hash of both,
    so drift is detectable rather than assumed absent.
    """

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_recorded_inputs_still_match_the_files_on_disk(self):
        manifests = sorted(ROOT.glob("results/*/*/run_manifest_*.json"))
        if not manifests:
            pytest.skip("no runs in this checkout")
        checked = 0
        for manifest in manifests:
            record = json.loads(manifest.read_text(encoding="utf-8"))
            report = ROOT / "data" / "corpus" / "python_v1" / "index_report.json"
            recorded = (record.get("corpus") or {}).get("index_report_sha256")
            if recorded and report.exists():
                assert recorded == self._sha(report), \
                    f"{manifest.name} ran against a different corpus index than the one on disk"
                checked += 1
            scenario_set = record.get("scenario_set") or {}
            path = ROOT / scenario_set.get("path", "data/scenarios/scenarios_v1.json")
            if scenario_set.get("sha256") and path.exists():
                assert scenario_set["sha256"] == self._sha(path), \
                    f"{manifest.name} ran against a different scenario set than the one on disk"
                checked += 1
        if not checked:
            pytest.skip("no manifest recorded a hash that could be checked")


class TestDocumentHygiene:
    @pytest.mark.parametrize("name", list(DOCUMENTS))
    def test_no_em_dashes(self, name):
        assert "—" not in _text(name), f"{name} contains an em dash"
