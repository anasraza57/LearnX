"""
Guards the numbers quoted in the write-up against the analysis they come from.

Every figure in the handoff and the draft sections was recomputed several times
as measurement errors were found, and a stale number in prose is exactly the
failure this revision exists to correct. These tests re-derive the headline
figures from the stored analysis and assert that the documents still say them.

They skip when the analysis output is absent, so a fresh clone still passes.
"""

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

    def test_no_document_still_quotes_a_superseded_figure(self):
        superseded = ["-0.365", "p = 0.021", "0.365", "100% schema-valid"]
        for name in DOCUMENTS:
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
        assert _pooled(runs, "A1", "citation_markers") == 16474
        assert _pooled(runs, "A1", "invalid_markers") == 5
        assert _pooled(runs, "A3", "citation_markers") == 0
        assert _pooled(runs, "A5", "citation_markers") == 0
        for name in ("handoff", "results", "methods"):
            assert "16,474" in _text(name)


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


class TestDocumentHygiene:
    @pytest.mark.parametrize("name", list(DOCUMENTS))
    def test_no_em_dashes(self, name):
        assert "—" not in _text(name), f"{name} contains an em dash"
