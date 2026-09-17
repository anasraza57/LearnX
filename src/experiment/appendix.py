"""
Builds the manuscript appendices that quote the system verbatim:

- Appendix E, the agent prompts, taken from the prompts actually recorded in a
  run rather than retyped from the source, so what is published is what ran;
- Appendix G, sample transcripts: a generated syllabus, a negotiation exchange,
  and an instructional response with its retrieved passages and citations.

Usage:
    python -m src.experiment.appendix prompts    --experiment e1 --model gpt-5.4-mini
    python -m src.experiment.appendix transcripts --experiment e1 --model gpt-5.4-mini --scenario S01
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import config
from .runner import EXPERIMENT_DIRS, RESULTS_DIR, model_slug

DOCS_DIR = config.paths.project_root / "docs"

# Which recorded prompt illustrates which agent, and what the reader needs to know.
PROMPT_SOURCES = [
    ("Learner Advocate, system prompt", "A1", ("planning", "prompts", "advocate_system"),
     "Represents the learner in the negotiation. Filled per scenario with the learner's goals, "
     "prior knowledge, style, pace, difficulty preference and time budget."),
    ("Curriculum Designer, system prompt", "A1", ("planning", "prompts", "designer_system"),
     "Represents pedagogical expertise in the negotiation."),
    ("Curriculum Designer, opening request", "A1", ("planning", "prompts", "designer_initial"),
     "The first turn, carrying the advocate's statement of requirements."),
    ("Syllabus extractor", "A1", ("planning", "prompts", "extraction"),
     "Converts the negotiation transcript into the JSON the schema defines. The negotiation itself "
     "is free text; only this output is schema validated."),
    ("Single-agent baseline, system prompt", "A2", ("planning", "prompts", "single_agent_system"),
     "The A2 baseline: one agent that plans, teaches and assesses, given the same learner profile."),
    ("Single-agent baseline, planning task", "A2", ("planning", "prompts", "plan_task"),
     "Asks for the same syllabus JSON, with the same format specification, as the extractor above."),
]

LESSON_PROMPTS = [
    ("Instructor, grounded with the citation instruction", "A1",
     "The full architecture. The context block holds the retrieved passages, numbered, and the "
     "citation requirements are the last section."),
    ("Instructor, grounded without the citation instruction", "A5",
     "Identical to the prompt above except that the citation requirements are absent. This is the "
     "only difference between conditions A1 and A5."),
    ("Instructor, ungrounded", "A3",
     "No retrieval, so no context block: the model answers from its own knowledge. Everything else, "
     "including the learner personalisation, is unchanged."),
]


def _load_runs(experiment: str, model: str) -> List[Dict[str, Any]]:
    root = RESULTS_DIR / EXPERIMENT_DIRS[experiment] / model_slug(model)
    runs = []
    for path in sorted(root.glob("*/*.json")):
        if path.name.endswith(".failed.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("failed"):
            runs.append(record)
    if not runs:
        raise SystemExit(f"No completed runs for {model} under {experiment}")
    return runs


def _pick(runs: List[Dict[str, Any]], condition: str, scenario: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for record in runs:
        if record["condition"]["id"] == condition and (scenario is None or record["scenario_id"] == scenario):
            return record
    return None


def _nested(record: Dict[str, Any], path) -> Optional[str]:
    value: Any = record
    for key in path:
        value = (value or {}).get(key) if isinstance(value, dict) else None
    return value if isinstance(value, str) else None


# Material a prompt carries per run (a transcript, retrieved passages, a syllabus
# the agent wrote earlier) is elided in the prompt appendix and marked as such,
# so the appendix shows the prompt rather than one run's data. Appendix G quotes
# that material in full.
ELISIONS = [
    (re.compile(r"(Based on this syllabus negotiation:\n\n).*?(\n\nExtract a structured JSON syllabus)", re.DOTALL),
     "[the negotiation transcript, elided here: quoted in full in Appendix G]"),
    # One rule per context block, stopping at whichever section follows it, so
    # that eliding the passages cannot also swallow the instructions
    (re.compile(r"(\*\*Context from (?:educational|teaching) materials:\*\*\n)"
                r".*?(\n\n\*\*(?:Instructions|Citation requirements|Requirements|Format)\b)", re.DOTALL),
     "[the retrieved passages, elided here: quoted in full in Appendix G]"),
    (re.compile(r'(\n)\{\n  "meta": \{.*?\n\}(\n)', re.DOTALL),
     "[the syllabus this agent wrote earlier in the conversation, elided here]"),
    (re.compile(r"(\*\*Recent Conversation:\*\*\n).*?(\n\nTASK|\n\nYou are an expert)", re.DOTALL),
     "[the last three exchanges, elided here]"),
]


def _elide(text: str) -> str:
    for pattern, marker in ELISIONS:
        text = pattern.sub(lambda m: m.group(1) + marker + m.group(2), text)
    return text


def _fence(text: str) -> str:
    """Quote a prompt verbatim, using a fence long enough to survive backticks inside it."""
    fence = "`" * max(4, max((len(run) for run in _backtick_runs(text)), default=3) + 1)
    return f"{fence}text\n{text.rstrip()}\n{fence}"


def _backtick_runs(text: str) -> List[str]:
    runs, current = [], ""
    for character in text:
        if character == "`":
            current += character
        elif current:
            runs.append(current)
            current = ""
    if current:
        runs.append(current)
    return runs


def build_prompts(experiment: str, model: str) -> str:
    """Appendix E: every prompt the system used, quoted from a real run."""
    runs = _load_runs(experiment, model)
    scenario = runs[0]["scenario_id"]
    lines = [
        "# Appendix E: agent prompts", "",
        f"Every prompt below is quoted from a recorded run ({model}, scenario {scenario} unless noted), "
        "not retyped from the source, so these are the prompts that produced the reported results. "
        "Text in braces is filled per scenario.", "",
    ]

    for title, condition, path, note in PROMPT_SOURCES:
        record = _pick(runs, condition)
        prompt = _nested(record, path) if record else None
        if not prompt:
            continue
        lines += [f"## {title}", "", f"*{note}*", "", _fence(_elide(prompt)), ""]

    for title, condition, note in LESSON_PROMPTS:
        record = _pick(runs, condition)
        lesson = next((l for m in record["modules"] for l in m["lessons"] if l.get("prompt")), None) if record else None
        if not lesson:
            continue
        lines += [f"## {title}", "", f"*{note} Shown for the topic \"{lesson['topic']}\".*", "",
                  _fence(_elide(lesson["prompt"])), ""]

    record = _pick(runs, "A1")
    item = next((i for m in record["modules"] for i in m["items"]
                 if (i.get("generation_meta") or {}).get("prompt")), None) if record else None
    if item:
        lines += ["## Assessment generator, multiple-choice item", "",
                  "*Generates one item per syllabus topic, at the learner's preferred difficulty, from "
                  "passages retrieved with the same parameters as instruction.*", "",
                  _fence(_elide(item["generation_meta"]["prompt"])), ""]

    record = _pick(runs, "A2")
    item = next((i for m in record["modules"] for i in m["items"]
                 if (i.get("generation_meta") or {}).get("prompt")), None) if record else None
    if item:
        lines += ["## Single-agent baseline, assessment task", "",
                  "*The same agent that planned and taught also writes the items, in the same "
                  "conversation, with the same format specification.*", "",
                  _fence(_elide(item["generation_meta"]["prompt"])), ""]

    lines += ["## Grading agent", "",
              "*Not exercised by these experiments: grading requires learner answers, and the design "
              "simulates no learners. The prompt is in `src/agents/grading_agent.py`.*", ""]
    return "\n".join(lines)


def build_transcripts(experiment: str, model: str, scenario: Optional[str] = None) -> str:
    """Appendix G: a syllabus, a negotiation, and a response with its sources."""
    runs = _load_runs(experiment, model)
    record = _pick(runs, "A1", scenario) or _pick(runs, "A1")
    scenario_id = record["scenario_id"]
    factors = record["scenario"]["factors"]
    planning = record["planning"]
    syllabus = planning["extracted_syllabus"]

    lines = [
        "# Appendix G: sample transcripts", "",
        f"From one run of the full architecture ({model}, scenario {scenario_id}: "
        f"{factors['prior_knowledge']} prior knowledge, {factors['goal_profile']} goal, "
        f"{record['scenario']['total_hours']:.0f} hours over {record['scenario']['duration_weeks']} weeks, "
        f"preference profile {factors['preference_profile']}).", "",
        "## G.1 The generated syllabus", "",
        "As the agents produced it, before the deterministic post-processing that repairs the schema "
        "and rescales hours.", "",
        "```json", json.dumps(syllabus, indent=2, ensure_ascii=False), "```", "",
        "## G.2 The negotiation", "",
        f"{planning['rounds_completed']} round(s); the advocate's verdicts were "
        f"{', '.join(str(v) for v in planning.get('verdicts') or []) or 'none recorded'}.", "",
    ]
    for turn in planning.get("negotiation_history", []):
        role = "Learner Advocate" if turn["role"] == "advocate" else "Curriculum Designer"
        lines += [f"### {role}", "", _fence(turn["content"]), ""]

    lesson = next((l for m in record["modules"] for l in m["lessons"] if l.get("retrieved")), None)
    if lesson:
        lines += ["## G.3 An instructional response, with its retrieved passages and citations", "",
                  f"**Question put to the instructor:** {lesson['question']}", "",
                  f"The numbers in square brackets refer to the passages below. Retrieval used the "
                  f"pinned settings (top-k {record['corpus']['top_k']}, similarity threshold "
                  f"{record['corpus']['similarity_threshold']}).", "",
                  "### Response", "", _fence(lesson["content"]), "", "### Passages supplied", ""]
        for passage in lesson["retrieved"]:
            source = f"[{passage['passage_index']}] {passage['source']}"
            if passage.get("url"):
                source += f" ({passage['url']})"
            lines += [f"**{source}**, similarity {passage['similarity']:.3f}, strand `{passage.get('strand')}`", "",
                      _fence(passage["content"]), ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["prompts", "transcripts"])
    parser.add_argument("--experiment", choices=sorted(EXPERIMENT_DIRS), default="e1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--scenario", help="scenario to quote (transcripts)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.command == "prompts":
        text = build_prompts(args.experiment, args.model)
        out = args.out or DOCS_DIR / "appendix_e_prompts.md"
    else:
        text = build_transcripts(args.experiment, args.model, args.scenario)
        out = args.out or DOCS_DIR / "appendix_g_transcripts.md"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"Written: {out} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
