"""
Unit tests for the E3 annotation preparation and agreement scoring.
"""

import csv
import json

import pytest

from src.experiment import annotation


RESPONSE = """## Tuples

A tuple is an immutable sequence of values.[1] Tuples are often used for heterogeneous data.[2]

```python
t = 1, 2, 3
t[0] = 9  # TypeError
```

- Lists, by contrast, are mutable and usually hold homogeneous data.[1]
- `t[0]`

What do you think happens next?

Short.
"""


def _response(response_id, condition, text=RESPONSE, retrieved=True):
    return {
        "response_id": response_id,
        "condition": condition,
        "model": "gpt-5.4-mini",
        "scenario_id": "S01",
        "module_id": "m03-data",
        "module_title": "Data structures",
        "topic": "Tuples",
        "text": text,
        "retrieved": ([{"passage_index": 1, "source": "5. Data Structures", "url": "http://x",
                        "content": "Tuples are immutable."}] if retrieved else []),
    }


class TestSegmentation:
    def test_prose_is_split_into_claims_and_code_dropped(self):
        claims = annotation.segment_claims(RESPONSE)
        texts = [c["text"] for c in claims]
        assert "A tuple is an immutable sequence of values.[1]" in texts
        assert "Tuples are often used for heterogeneous data.[2]" in texts
        assert any(t.startswith("Lists, by contrast") for t in texts)
        assert not any("TypeError" in t or t.startswith("##") for t in texts)
        assert not any(t.endswith("?") for t in texts)   # questions are not claims
        assert not any(t == "Short." for t in texts)      # too short to judge

    def test_citation_markers_are_kept_with_their_claim(self):
        claims = {c["text"]: c["cited_passages"] for c in annotation.segment_claims(RESPONSE)}
        assert claims["A tuple is an immutable sequence of values.[1]"] == [1]
        assert claims["Tuples are often used for heterogeneous data.[2]"] == [2]

    def test_segmentation_is_deterministic(self):
        assert annotation.segment_claims(RESPONSE) == annotation.segment_claims(RESPONSE)

    @pytest.mark.parametrize("text", [
        "If you want, I can still help in one of these ways:",          # the tutor offering
        "Here are some of the most useful dictionary methods for you:",  # a lead-in to a list
        "Here\u2019s a clear explanation of loops based only on the provided material.",
        "This connects directly to what you already learned about parameters here.",
        "I am sorry, but the provided context does not include information on sets.",
        "explain the general idea of abstraction using only the provided sources, or",  # a fragment
    ])
    def test_meta_discourse_and_fragments_are_not_claims(self, text):
        assert annotation.segment_claims(text) == []

    @pytest.mark.parametrize("text", [
        "`get()` is safer than direct lookup when a key might be missing.",
        "**Default parameter:** a parameter with a built-in value used when none is passed.",
        "> The else clause does not run if the loop ended because of a break.",
        "In Python, parameters with default values must come after those without.",
    ])
    def test_real_claims_survive_including_code_and_markup(self, text):
        assert len(annotation.segment_claims(text)) == 1

    def test_abbreviations_do_not_split_a_sentence(self):
        text = "Lists are mutable, e.g. you can append to them, which tuples do not allow at all."
        assert len(annotation.segment_claims(text)) == 1


class TestSampling:
    def _responses(self):
        return [_response(f"R{i:03d}", condition)
                for condition in ("A1", "A2", "A3", "A5")
                for i in range(10 * ord(condition[1]), 10 * ord(condition[1]) + 10)]

    def test_stratified_and_reproducible(self):
        first = annotation.sample_claims(self._responses(), claims_total=20, claims_per_response=2)
        second = annotation.sample_claims(self._responses(), claims_total=20, claims_per_response=2)
        assert [c["claim_id"] for c in first] == [c["claim_id"] for c in second]
        counts = {c: sum(1 for x in first if x["condition"] == c) for c in ("A1", "A2", "A3", "A5")}
        assert set(counts.values()) == {5}

    def test_claim_ids_are_unique_and_seed_changes_the_draw(self):
        sample = annotation.sample_claims(self._responses(), claims_total=20, claims_per_response=2)
        other = annotation.sample_claims(self._responses(), claims_total=20, claims_per_response=2, seed=1)
        assert len({c["claim_id"] for c in sample}) == len(sample)
        assert [c["claim_id"] for c in sample] != [c["claim_id"] for c in other]


class TestPack:
    def _pack(self, tmp_path, conditions=("A1", "A3")):
        responses = [_response(f"R{i:03d}", condition, retrieved=condition != "A3")
                     for condition in conditions for i in range(5)]
        sample = annotation.sample_claims(responses, claims_total=8, claims_per_response=2)
        manifest = annotation.write_pack(sample, tmp_path, ["anas", "baidaa"], purpose="pilot")
        return sample, manifest

    def test_rating_sheets_hide_the_backend_and_condition(self, tmp_path):
        self._pack(tmp_path)
        with (tmp_path / "ratings_anas.csv").open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert "condition" not in reader.fieldnames and "model" not in reader.fieldnames
            rows = list(reader)
        assert rows and all(row["claim_support"] == "" for row in rows)
        text = (tmp_path / "ratings_anas.csv").read_text(encoding="utf-8")
        assert "gpt-5.4-mini" not in text

    def test_both_raters_get_identical_units(self, tmp_path):
        self._pack(tmp_path)
        ids = []
        for rater in ("anas", "baidaa"):
            with (tmp_path / f"ratings_{rater}.csv").open(encoding="utf-8") as handle:
                ids.append([row["claim_id"] for row in csv.DictReader(handle)])
        assert ids[0] == ids[1]

    def test_key_is_written_separately(self, tmp_path):
        sample, manifest = self._pack(tmp_path)
        key = json.loads((tmp_path / "key.json").read_text(encoding="utf-8"))
        assert {c["claim_id"] for c in key["claims"]} == {c["claim_id"] for c in sample}
        assert all("condition" in c and "model" in c for c in key["claims"])
        assert manifest["segmenter"] == annotation.SEGMENTER_VERSION

    def test_citation_dimension_preset_to_not_applicable_for_non_citing_conditions(self, tmp_path):
        sample, manifest = self._pack(tmp_path)
        key = {c["claim_id"]: c for c in json.loads((tmp_path / "key.json").read_text())["claims"]}
        with (tmp_path / "ratings_anas.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                expected = "" if key[row["claim_id"]]["condition"] in annotation.CITING_CONDITIONS else "not_applicable"
                assert row["citation_correctness"] == expected
        assert manifest["citation_dimension_applies"] == sum(
            1 for c in sample if c["condition"] in annotation.CITING_CONDITIONS)

    def test_contexts_carry_the_response_and_its_passages(self, tmp_path):
        self._pack(tmp_path)
        contexts = json.loads((tmp_path / "contexts.json").read_text(encoding="utf-8"))
        assert contexts and all("response_text" in c for c in contexts)
        assert any(c["retrieved_passages"] for c in contexts)


class TestAgreement:
    def test_cohens_kappa(self):
        assert annotation.cohens_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
        assert annotation.cohens_kappa(["a", "a", "b", "b"], ["b", "b", "a", "a"]) == -1.0
        # Confusion table 20/20/15/45: observed 0.65, expected 0.53, kappa 0.12/0.47.
        # Checked against sklearn.metrics.cohen_kappa_score.
        first = ["yes"] * 40 + ["no"] * 60
        second = ["yes"] * 20 + ["no"] * 20 + ["yes"] * 15 + ["no"] * 45
        assert annotation.cohens_kappa(first, second) == pytest.approx(0.12 / 0.47, abs=1e-9)
        assert annotation.cohens_kappa(["a", "b", "a", "c", "b"], ["a", "b", "c", "c", "b"]) == \
            pytest.approx(0.705882352941, abs=1e-9)

    def test_blank_labels_are_ignored(self):
        assert annotation.cohens_kappa(["a", "", "b"], ["a", "b", "b"]) == 1.0

    def test_score_pack_reports_per_dimension(self, tmp_path):
        responses = [_response(f"R{i:03d}", "A1") for i in range(5)]
        sample = annotation.sample_claims(responses, claims_total=4, claims_per_response=2)
        annotation.write_pack(sample, tmp_path, ["anas", "baidaa"], purpose="pilot")

        labels = ["supported", "unsupported", "supported", "partial"]
        for rater, flipped in (("anas", False), ("baidaa", True)):
            path = tmp_path / f"ratings_{rater}.csv"
            rows = list(csv.DictReader(path.open(encoding="utf-8")))
            for row, label in zip(rows, labels):
                row["claim_support"] = "partial" if flipped and label == "supported" else label
                row["citation_correctness"] = "correct"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

        report = annotation.score_pack(tmp_path, ["anas", "baidaa"])
        support = report["dimensions"]["claim_support"]
        assert support["n"] == 4
        assert support["raw_agreement"] == 0.5
        assert len(support["disagreements"]) == 2
        assert report["dimensions"]["citation_correctness"]["raw_agreement"] == 1.0
        assert report["dimensions"]["supported_by_retrieved"]["status"] == "not rated"

    def test_score_pack_requires_two_raters(self, tmp_path):
        with pytest.raises(ValueError):
            annotation.score_pack(tmp_path, ["anas"])
