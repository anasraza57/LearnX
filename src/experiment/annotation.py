"""
Preparation and scoring for the citation faithfulness study (E3).

Three things have to be true for the study to produce a defensible kappa:

- both raters label the *same* units, so segmentation into atomic claims happens
  once, here, by a deterministic rule (B9);
- raters cannot tell which model backend produced a response, so the pack they
  receive carries no backend or condition field and the key is kept separately
  (B6; the condition is still visible in the text itself, which the paper states);
- claim support is judged against the module corpus, not the passages a
  condition happened to retrieve (D26), so the pack ships the corpus reference
  and the retrieved passages are a separate, secondary question.

Sampling is stratified by condition and drawn with a fixed seed. Note that
responses carry about 13 claims each, so a sample of 200 responses would be some
2,600 claims per rater. The sample is therefore drawn at claim level: responses
are sampled per condition, then a fixed number of claims per response.

Usage:
    python -m src.experiment.annotation pilot  --experiment e1 --model gpt-5.4-mini
    python -m src.experiment.annotation main   --experiment e1 --model gpt-5.4-mini --claims 240
    python -m src.experiment.annotation score  --pack data/annotation/main --raters anas baidaa
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..config import config
from .runner import EXPERIMENT_DIRS, RESULTS_DIR, model_slug

ANNOTATION_DIR = config.paths.data_dir / "annotation"
SEGMENTER_VERSION = "rule-v1"
DEFAULT_SEED = 20260917

# Conditions that emit citations, so the citation dimension applies (handoff 4.4).
CITING_CONDITIONS = {"A1", "A2", "A5"}

SUPPORT_LABELS = ["supported", "partial", "unsupported", "contradicted", "not_applicable"]
CITATION_LABELS = ["correct", "misattributed", "missing", "not_applicable"]

CODE_BLOCK = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
CITATION_MARKER = re.compile(r"\[(?:Sources?\s+)?\d+(?:\s*[-–,;]\s*(?:Sources?\s+)?\d+)*(?:\s*:[^\]\n]*)?\]")
# A sentence ends at .!? plus any citation markers that trail it, when the next
# thing looks like the start of a new sentence. The markers stay with the claim
# they support.
SENTENCE_END = re.compile(r"[.!?](?:\s*\[[^\]\n]*\])*(?=\s+[A-Z`*\"'(\[])")
MIN_CLAIM_CHARS = 40


def _split_sentences(line: str) -> List[str]:
    """Split a line of prose into sentences, keeping trailing citation markers."""
    sentences, start = [], 0
    for match in SENTENCE_END.finditer(line):
        sentences.append(line[start:match.end()])
        start = match.end()
    sentences.append(line[start:])
    return [s for s in (part.strip() for part in sentences) if s]


def segment_claims(response_text: str) -> List[Dict[str, Any]]:
    """
    Split one response into atomic claims, deterministically.

    The rule: drop code blocks, headings, list scaffolding and questions; split
    the remaining prose on sentence boundaries; keep sentences of at least
    MIN_CLAIM_CHARS. Citation markers are kept with the claim they sit on, since
    the citation dimension needs them, and are also recorded separately.
    """
    claims: List[Dict[str, Any]] = []
    text = CODE_BLOCK.sub(" ", response_text or "")
    for block in text.split("\n"):
        line = block.strip()
        if not line or line.startswith("#") or line.startswith("|") or set(line) <= set("-*_ "):
            continue
        line = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)  # list markers
        for sentence in _split_sentences(line):
            sentence = sentence.strip()
            if len(sentence) < MIN_CLAIM_CHARS or sentence.endswith("?"):
                continue
            plain = INLINE_CODE.sub(" ", CITATION_MARKER.sub("", sentence)).strip()
            if len(plain) < MIN_CLAIM_CHARS:
                continue  # mostly markup or code
            claims.append({
                "text": sentence,
                "cited_passages": sorted({int(n) for marker in CITATION_MARKER.findall(sentence)
                                          for n in re.findall(r"\d+", marker)}),
            })
    return claims


def _response_id(run_label: str, module_id: str, topic: str) -> str:
    digest = hashlib.sha256(f"{run_label}|{module_id}|{topic}".encode()).hexdigest()
    return f"R{digest[:10]}"


def collect_responses(experiment: str, model: str) -> List[Dict[str, Any]]:
    """Every non-refused instructional response of a model's runs, with its context."""
    root = RESULTS_DIR / EXPERIMENT_DIRS[experiment] / model_slug(model)
    responses = []
    for path in sorted(root.glob("*/*.json")):
        if path.name.endswith(".failed.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("failed"):
            continue
        for module in record["modules"]:
            for lesson in module["lessons"]:
                if lesson.get("refused") or not (lesson.get("content") or "").strip():
                    continue
                responses.append({
                    "response_id": _response_id(record["run_label"], module["module_id"], lesson.get("topic", "")),
                    "condition": record["condition"]["id"],
                    "model": record["model"]["requested"],
                    "scenario_id": record["scenario_id"],
                    "module_id": module["module_id"],
                    "module_title": module["title"],
                    "topic": lesson.get("topic"),
                    "text": lesson["content"],
                    "retrieved": lesson.get("retrieved") or [],
                })
    return responses


def sample_claims(
    responses: Sequence[Dict[str, Any]],
    claims_total: int,
    claims_per_response: int = 4,
    seed: int = DEFAULT_SEED,
    conditions: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    A stratified claim sample: equal share per condition, responses drawn at
    random within a condition, then claims drawn within a response.
    """
    rng = random.Random(seed)
    conditions = sorted(conditions or {r["condition"] for r in responses})
    per_condition = max(1, claims_total // len(conditions))
    sample: List[Dict[str, Any]] = []

    for condition in conditions:
        pool = [r for r in responses if r["condition"] == condition]
        rng.shuffle(pool)
        taken = 0
        for response in pool:
            if taken >= per_condition:
                break
            claims = segment_claims(response["text"])
            if not claims:
                continue
            wanted = min(claims_per_response, len(claims), per_condition - taken)
            for index in sorted(rng.sample(range(len(claims)), wanted)):
                claim = claims[index]
                sample.append({
                    "claim_id": f"{response['response_id']}-C{index:02d}",
                    "response_id": response["response_id"],
                    "condition": response["condition"],
                    "model": response["model"],
                    "scenario_id": response["scenario_id"],
                    "module_title": response["module_title"],
                    "topic": response["topic"],
                    "claim_text": claim["text"],
                    "cited_passages": claim["cited_passages"],
                    "response_text": response["text"],
                    "retrieved": response["retrieved"],
                })
            taken += wanted
    rng.shuffle(sample)  # so raters do not see conditions in blocks
    return sample


def write_pack(sample: List[Dict[str, Any]], out_dir: Path, raters: Sequence[str], purpose: str) -> Dict[str, Any]:
    """
    Write one rating sheet per rater (no backend or condition columns), the
    shared claim and context files, and the key, kept separately.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    citation_applies = {c["claim_id"]: c["condition"] in CITING_CONDITIONS for c in sample}

    for rater in raters:
        path = out_dir / f"ratings_{rater}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["claim_id", "response_id", "module_title", "topic", "claim_text",
                             "claim_support", "citation_correctness", "supported_by_retrieved",
                             "rater_note"])
            for claim in sample:
                writer.writerow([
                    claim["claim_id"], claim["response_id"], claim["module_title"], claim["topic"],
                    claim["claim_text"], "", "" if citation_applies[claim["claim_id"]] else "not_applicable",
                    "", "",
                ])

    # What a rater reads to judge a claim: the response it came from and, where
    # one exists, the passages that response was given.
    context = {}
    for claim in sample:
        context.setdefault(claim["response_id"], {
            "response_id": claim["response_id"],
            "module_title": claim["module_title"],
            "topic": claim["topic"],
            "response_text": claim["response_text"],
            "retrieved_passages": [
                {"passage_index": p.get("passage_index"), "source": p.get("source"),
                 "url": p.get("url"), "content": p.get("content")}
                for p in claim["retrieved"]
            ],
        })
    (out_dir / "contexts.json").write_text(
        json.dumps(sorted(context.values(), key=lambda c: c["response_id"]), indent=2, ensure_ascii=False),
        encoding="utf-8")

    (out_dir / "key.json").write_text(json.dumps({
        "purpose": purpose,
        "segmenter": SEGMENTER_VERSION,
        "claims": [{k: claim[k] for k in ("claim_id", "response_id", "condition", "model",
                                          "scenario_id", "topic", "cited_passages")}
                   for claim in sample],
    }, indent=2), encoding="utf-8")

    manifest = {
        "purpose": purpose,
        "claims": len(sample),
        "responses": len({c["response_id"] for c in sample}),
        "by_condition": dict(Counter(c["condition"] for c in sample)),
        "citation_dimension_applies": sum(citation_applies.values()),
        "raters": list(raters),
        "segmenter": SEGMENTER_VERSION,
        "label_sets": {"claim_support": SUPPORT_LABELS, "citation_correctness": CITATION_LABELS},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def cohens_kappa(first: Sequence[str], second: Sequence[str]) -> Optional[float]:
    """Cohen's kappa for two raters over the same units."""
    pairs = [(a, b) for a, b in zip(first, second) if a and b]
    if not pairs:
        return None
    labels = sorted({label for pair in pairs for label in pair})
    if len(labels) < 2:
        return 1.0 if all(a == b for a, b in pairs) else 0.0
    observed = sum(a == b for a, b in pairs) / len(pairs)
    first_counts = Counter(a for a, _ in pairs)
    second_counts = Counter(b for _, b in pairs)
    expected = sum(first_counts[label] * second_counts[label] for label in labels) / len(pairs) ** 2
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def confusion_matrix(first: Sequence[str], second: Sequence[str], labels: Sequence[str]) -> Dict[str, Dict[str, int]]:
    matrix = {a: {b: 0 for b in labels} for a in labels}
    for a, b in zip(first, second):
        if a in matrix and b in matrix[a]:
            matrix[a][b] += 1
    return matrix


def _read_ratings(path: Path) -> Dict[str, Dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return {row["claim_id"]: row for row in csv.DictReader(handle)}


def score_pack(pack_dir: Path, raters: Sequence[str]) -> Dict[str, Any]:
    """Agreement per dimension, with the confusion matrices and the disagreeing claims."""
    if len(raters) != 2:
        raise ValueError("Cohen's kappa is defined for exactly two raters")
    ratings = [_read_ratings(pack_dir / f"ratings_{rater}.csv") for rater in raters]
    shared = sorted(set(ratings[0]) & set(ratings[1]))
    key = {c["claim_id"]: c for c in json.loads((pack_dir / "key.json").read_text(encoding="utf-8"))["claims"]}

    report: Dict[str, Any] = {"raters": list(raters), "claims_rated": len(shared), "dimensions": {}}
    for dimension, labels in (("claim_support", SUPPORT_LABELS),
                              ("citation_correctness", CITATION_LABELS),
                              ("supported_by_retrieved", ["yes", "no", "not_applicable"])):
        first = [ratings[0][c].get(dimension, "").strip() for c in shared]
        second = [ratings[1][c].get(dimension, "").strip() for c in shared]
        both = [(a, b, c) for a, b, c in zip(first, second, shared) if a and b]
        if not both:
            report["dimensions"][dimension] = {"status": "not rated"}
            continue
        agree = sum(a == b for a, b, _ in both)
        report["dimensions"][dimension] = {
            "n": len(both),
            "raw_agreement": agree / len(both),
            "cohens_kappa": cohens_kappa([a for a, _, _ in both], [b for _, b, _ in both]),
            "confusion_matrix": confusion_matrix([a for a, _, _ in both], [b for _, b, _ in both], labels),
            "disagreements": [{"claim_id": c, "condition": key.get(c, {}).get("condition"),
                               raters[0]: a, raters[1]: b} for a, b, c in both if a != b],
        }
    return report


def _load_or_exit(experiment: str, model: str) -> List[Dict[str, Any]]:
    responses = collect_responses(experiment, model)
    if not responses:
        raise SystemExit(f"No responses found for {model} under {experiment}")
    return responses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["pilot", "main", "score"])
    parser.add_argument("--experiment", choices=sorted(EXPERIMENT_DIRS), default="e1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--claims", type=int, help="claims to sample (default: 20 pilot, 240 main)")
    parser.add_argument("--claims-per-response", type=int, default=4)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--raters", nargs="+", default=["anas", "baidaa"])
    parser.add_argument("--pack", type=Path, help="pack directory (for score)")
    args = parser.parse_args()

    if args.command == "score":
        pack = args.pack or ANNOTATION_DIR / "main"
        report = score_pack(pack, args.raters)
        (pack / "agreement.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "dimensions"}, indent=2))
        for dimension, result in report["dimensions"].items():
            if result.get("status") == "not rated":
                print(f"{dimension}: not rated")
                continue
            print(f"{dimension}: n={result['n']} raw agreement={result['raw_agreement']:.3f} "
                  f"kappa={result['cohens_kappa']:.3f} disagreements={len(result['disagreements'])}")
        print(f"\nWritten: {pack / 'agreement.json'}")
        return

    claims_total = args.claims or (20 if args.command == "pilot" else 240)
    # The pilot is deliberately drawn with a different seed, so its claims are
    # discarded without biasing the main sample (handoff 4.4).
    seed = args.seed + (1 if args.command == "pilot" else 0)
    sample = sample_claims(_load_or_exit(args.experiment, args.model), claims_total,
                           args.claims_per_response, seed)
    out_dir = ANNOTATION_DIR / args.command
    manifest = write_pack(sample, out_dir, args.raters, purpose=args.command)
    print(json.dumps(manifest, indent=2))
    print(f"\nWritten to {out_dir}: rating sheets for {', '.join(args.raters)}, contexts.json, key.json")


if __name__ == "__main__":
    main()
