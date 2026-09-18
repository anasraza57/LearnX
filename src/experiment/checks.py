"""
Automatic checkers for the failure taxonomy (E4) and the per-run metrics the
contrasts are computed from.

Everything here is derived from a stored run record, so it can be recomputed at
any time without calling a model. Measures that need human annotation (claim
support, citation correctness, whether an item is answerable from the corpus)
are deliberately absent: they come from the E3 study, and nothing here
substitutes a proxy for them.

Thresholds that the design left open are constants at the top of this file, so
the rules applied are visible and changing one is a single, reviewable edit.
"""

from __future__ import annotations

import ast
import re
import statistics
import textwrap
from typing import Any, Dict, List, Optional

from ..agents.syllabus_planner import _as_hours, _total_hours
from .corpus import STRANDS

# ---- Rules the design left open (proposed defaults, see handoff section 12.2) ----

# A syllabus satisfies the time budget if its total is within these fractions of
# the budget. These are the planner's own thresholds, so the system is judged by
# the rule it applies to itself.
BUDGET_MIN_FRACTION = 0.8
BUDGET_MAX_FRACTION = 1.1

# The curriculum designer prompt asks for 4 to 8 modules.
MIN_MODULES = 4
MAX_MODULES = 8

# Retrieval is "low confidence" when even the best passage is only just above the
# threshold that let it through.
NEAR_THRESHOLD_MARGIN = 0.05

# Goal coverage: a narrow-goal syllabus must devote at least this share of its
# modules to the strand the goal names; a broad-goal syllabus must touch every strand.
NARROW_GOAL_MIN_SHARE = 0.5
NARROW_GOAL_STRAND = "py03-data-structures"

# Keywords used to map a module to a curriculum strand when it has no retrieved
# passages to map it by (the no-retrieval condition).
STRAND_KEYWORDS = {
    "py01-basics": ["variable", "data type", "string", "number", "operator", "input", "output",
                    "syntax", "basics", "setup", "print", "expression"],
    "py02-control-flow": ["control flow", "conditional", "if", "else", "loop", "for", "while",
                          "break", "continue", "function", "parameter", "return", "recursion"],
    "py03-data-structures": ["list", "tuple", "dictionar", "set", "comprehension", "data structure",
                             "slicing", "indexing", "nested"],
    "py04-oop": ["class", "object", "inheritance", "polymorph", "encapsulat", "attribute",
                 "method", "oop", "object-oriented"],
}

# Refusals the model writes itself, as opposed to the system's canned refusal.
REFUSAL_PATTERNS = re.compile(
    r"(context (does not|doesn't) (contain|include|provide)|not enough information|"
    r"no information (in|about)|cannot answer|can't answer|unable to answer|"
    r"the provided (context|materials) (do(es)? not|doesn't))",
    re.IGNORECASE,
)

CODE_BLOCK = re.compile(r"```(?:python|py)\n(.*?)```", re.DOTALL)


def _strand_from_keywords(text: str) -> Optional[str]:
    text = text.lower()
    scores = {s: sum(text.count(k) for k in keys) for s, keys in STRAND_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def module_strand_by_wording(module: Dict[str, Any]) -> Optional[str]:
    """
    The strand a module's title and topics describe.

    Used for goal coverage, because it is the only rule available in every
    condition: the no-retrieval condition has no passages to map a module by, and
    scoring one condition by a different rule than the others made it look better
    than them (0.92 against 0.83) purely by the change of rule.
    """
    return _strand_from_keywords(" ".join([module.get("title") or ""] + list(module.get("topics") or [])))


def module_strand(module: Dict[str, Any]) -> Optional[str]:
    """
    The curriculum strand a generated module belongs to: the strand most of its
    retrieved passages came from, or, when it retrieved nothing, the strand its
    title and topics read as. Used for retrieval measures, where what was actually
    retrieved is the point.
    """
    counts: Dict[str, int] = {}
    for lesson in module.get("lessons", []):
        for passage in lesson.get("retrieved", []):
            strand = passage.get("strand")
            if strand:
                counts[strand] = counts.get(strand, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    return _strand_from_keywords(" ".join([module.get("title") or ""] + list(module.get("topics") or [])))


def _prerequisite_check(modules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prerequisites present, resolvable and acyclic (depth-first cycle detection)."""
    ids = {m.get("id") for m in modules if isinstance(m, dict)}
    edges = {m.get("id"): [p for p in (m.get("prerequisites") or []) if isinstance(p, str)]
             for m in modules if isinstance(m, dict)}
    unresolved = sorted({p for deps in edges.values() for p in deps if p not in ids})

    state: Dict[str, int] = {}
    cyclic = False

    def visit(node: str) -> None:
        nonlocal cyclic
        if state.get(node) == 1:
            cyclic = True
            return
        if state.get(node) == 2 or node not in edges:
            return
        state[node] = 1
        for nxt in edges[node]:
            visit(nxt)
        state[node] = 2

    for node in list(edges):
        visit(node)

    return {
        "prerequisites_present": any(edges.values()),
        "prerequisites_resolvable": not unresolved,
        "prerequisites_acyclic": not cyclic,
        "unresolved_prerequisites": unresolved,
    }


def planning_checks(record: Dict[str, Any]) -> Dict[str, Any]:
    """Schema validity, time budget, prerequisites, goal coverage and module count."""
    planning = record.get("planning") or {}
    extracted = planning.get("extracted_syllabus") or {}
    final = planning.get("final_syllabus") or {}
    modules = [m for m in extracted.get("modules", []) if isinstance(m, dict)]
    budget = record["scenario"]["total_hours"]
    hours = _total_hours(extracted)

    # Goal coverage reads the syllabus itself, so every condition is judged the
    # same way whether or not it retrieved anything
    strands = {m.get("id"): module_strand_by_wording(m) for m in modules}
    goal_profile = record["scenario"]["factors"]["goal_profile"]
    covered = {s for s in strands.values() if s}
    if goal_profile == "broad":
        goal_covered = covered >= set(STRANDS)
    else:
        on_goal = [s for s in strands.values() if s == NARROW_GOAL_STRAND]
        goal_covered = bool(modules) and len(on_goal) / len(modules) >= NARROW_GOAL_MIN_SHARE

    # The prerequisites field is where the multi-agent path loses fidelity, so
    # validity with and without it are reported separately: without this the
    # composite counts one failure mode twice (it also fails the resolvable check)
    schema_errors = planning.get("schema_errors_as_extracted") or []
    checks = {
        "schema_valid_as_extracted": bool(planning.get("schema_valid_as_extracted")),
        "schema_valid_ignoring_prerequisites": not [e for e in schema_errors if "prerequisites" not in e],
        "extraction_parsed": not planning.get("extraction_fallback", False),
        "time_budget_satisfied": bool(
            modules and BUDGET_MIN_FRACTION * budget <= hours <= BUDGET_MAX_FRACTION * budget
        ),
        "module_count_in_range": MIN_MODULES <= len(modules) <= MAX_MODULES,
        "goal_covered": bool(goal_covered),
        **_prerequisite_check(modules),
    }
    constraints = [
        "schema_valid_as_extracted", "time_budget_satisfied", "module_count_in_range",
        "goal_covered", "prerequisites_present", "prerequisites_resolvable", "prerequisites_acyclic",
    ]
    satisfied = [checks[name] for name in constraints]
    return {
        **checks,
        "module_count": len(modules),
        "extracted_hours": hours,
        "final_hours": _total_hours(final),
        "budget_hours": budget,
        "final_hours_over_budget": _total_hours(final) > BUDGET_MAX_FRACTION * budget,
        "module_strands": strands,
        "strands_covered": sorted(covered),
        "hours_per_module": [_as_hours(m.get("estimated_hours")) for m in modules],
        # Continuous rate for the paired test, and the all-or-nothing version
        "constraint_satisfaction_rate": sum(satisfied) / len(satisfied),
        "all_constraints_satisfied": all(satisfied),
    }


def negotiation_checks(record: Dict[str, Any]) -> Dict[str, Any]:
    """Whether the protocol ran, revised anything, and ended in approval."""
    planning = record.get("planning") or {}
    history = planning.get("negotiation_history") or []
    designer_turns = [h for h in history if h["role"] == "designer"]
    advocate_turns = [h for h in history if h["role"] == "advocate"][1:]  # the first is the brief
    max_rounds = planning.get("max_negotiation_rounds", 0)
    # Roles are inverted if the advocate writes the syllabus itself, or the
    # designer issues the verdict. Flagged for confirmation, not counted as fact.
    proposal_like = re.compile(r"m0\d-[a-z0-9-]+|estimated[_ ]hours", re.IGNORECASE)
    roles_inverted = any(len(proposal_like.findall(t["content"])) >= 3 for t in advocate_turns) or \
        any(re.search(r"\b(APPROVED|CONTINUE)\b", t["content"].strip().splitlines()[-1] if t["content"].strip() else "")
            for t in designer_turns)
    return {
        "negotiation_enabled": max_rounds > 0,
        "rounds_completed": planning.get("rounds_completed", 0),
        "approved": planning.get("approved"),
        "no_revision_occurred": max_rounds > 0 and len(designer_turns) < 2,
        "max_rounds_without_approval": bool(max_rounds and not planning.get("approved")
                                            and planning.get("rounds_completed") == max_rounds),
        "verdict_unparsed": sum(1 for v in planning.get("verdicts") or [] if v is None),
        "roles_inverted_suspected": bool(roles_inverted),
    }


def _parse_ok(script: str) -> bool:
    """
    Whether a snippet is syntactically valid Python.

    Two allowances, both for how tutorial code is written rather than how it runs:
    the snippet is dedented, because blocks copied from the corpus keep its
    indentation and would otherwise fail as "unexpected indent" (56 of 59 apparent
    failures in one condition), and a comment-only body ("if x:" then
    "# do something") is a teaching skeleton, so a statement stands in for it.
    """
    prepared = re.sub(r"^(\s+)#.*$", r"\1pass", textwrap.dedent(script), flags=re.MULTILINE)
    try:
        ast.parse(prepared)
        return True
    except SyntaxError:
        return False


def _script_from_block(block: str) -> Optional[str]:
    """
    The Python a block claims to contain. An interactive transcript contributes
    the lines after its >>> and ... prompts, with the interpreter's output
    dropped. A block that is only interpreter output contributes nothing.
    """
    lines = block.splitlines()
    if not any(line.lstrip().startswith((">>>", "...")) for line in lines):
        return block
    code = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith((">>> ", "... ")):
            code.append(line[line.index(stripped[:3]) + 4:])
        elif stripped in (">>>", "..."):
            continue  # a prompt with no code on it
    return "\n".join(code) if code else None


# A fenced block is judged only if it looks like code rather than interpreter
# output: printed results are often fenced as python by the model. Note that a
# block deliberately showing wrong code (a Python 2 print, say) counts as a
# parse failure, so this measure is an upper bound on unintended breakage.
LOOKS_LIKE_CODE = re.compile(
    r"(?m)^\s*(def|class|import|from|for|while|if|elif|else|return|print|lambda|with|try|except)\b|[=(\[]"
)


# A block whose comments say the code is wrong on purpose ("# not allowed") is a
# teaching counter-example, not a defect, and is counted separately.
DELIBERATE_ERROR = re.compile(
    r"#[^\n]*\b(not allowed|invalid|error|wrong|fails?|don't|do not|never|bad|incorrect|won't work)\b"
    r"|\b(this (is )?(wrong|invalid)|would (fail|error)|causes? an error)\b",
    re.IGNORECASE,
)


def code_block_stats(text: str) -> Dict[str, int]:
    """
    Count the Python blocks in a response and how many fail to parse.

    Reported per block rather than per response: a response holding twenty
    examples is more likely to contain one broken block than a response holding
    one, so a per-response rate measures how much code was written as much as
    how often it breaks.
    """
    judged = failed = deliberate = 0
    for block in CODE_BLOCK.findall(text or ""):
        script = _script_from_block(block)
        if script is None or not script.strip() or not LOOKS_LIKE_CODE.search(script):
            continue
        judged += 1
        if not _parse_ok(script):
            failed += 1
            if DELIBERATE_ERROR.search(block):
                deliberate += 1
    return {"blocks": judged, "failing": failed, "deliberate": deliberate}


def _code_parses(text: str) -> Optional[bool]:
    """
    False if any Python block in the text fails to parse; None if the text has
    no code to judge. Interactive transcripts are reduced to their input lines.
    """
    judged = False
    for block in CODE_BLOCK.findall(text or ""):
        script = _script_from_block(block)
        if script is None or not script.strip():
            continue
        if not LOOKS_LIKE_CODE.search(script):
            continue  # interpreter output, not a program
        judged = True
        if not _parse_ok(script):
            return False
    return True if judged else None


def response_checks(record: Dict[str, Any]) -> Dict[str, Any]:
    """Per-response retrieval, refusal, truncation and citation-marker counts."""
    calls = {c["call_id"]: c for c in record["usage"]["calls"] if c.get("call_id")}
    threshold = record["corpus"]["similarity_threshold"]
    rows = []
    for module in record["modules"]:
        # Judged against the strand the module is about: measuring it against the
        # modal strand of the module's own passages is circular, since uniformly
        # wrong retrieval would score zero off-strand
        strand = module_strand_by_wording(module)
        for lesson in module["lessons"]:
            passages = lesson.get("retrieved") or []
            sims = [p["similarity"] for p in passages]
            call = calls.get(lesson.get("call_id")) or {}
            markers = lesson.get("inline_citations") or []
            code_ok = _code_parses(lesson.get("content", ""))
            code = code_block_stats(lesson.get("content", ""))
            rows.append({
                "module_id": module["module_id"],
                "topic": lesson.get("topic"),
                "mode": lesson.get("mode"),
                "no_passage_above_threshold": lesson.get("refused", False),
                "low_confidence_retrieval": (max(sims) < threshold + NEAR_THRESHOLD_MARGIN) if sims else None,
                "off_strand_passages": sum(1 for p in passages if strand and p.get("strand") != strand),
                "passages": len(passages),
                "model_written_refusal": (bool(REFUSAL_PATTERNS.search(lesson.get("content", "")))
                                         if not lesson.get("refused") else None),
                "truncated": call.get("finish_reason") == "length",
                "citation_markers": len(markers),
                "invalid_citation_markers": sum(1 for m in markers if not m["valid"]),
                "no_citation": not markers,
                "code_parses": code_ok,
                "code_blocks": code["blocks"],
                "code_blocks_failing": code["failing"],
                "code_blocks_deliberate_errors": code["deliberate"],
                "latency_s": call.get("latency_s"),
                "retrieval_s": lesson.get("retrieval_s"),
                "output_tokens": call.get("output_tokens"),
            })
    return {"responses": rows}


def assessment_checks(record: Dict[str, Any]) -> Dict[str, Any]:
    """Per-item schema validity, retrieval outcome and parse failures."""
    rows = []
    for module in record["modules"]:
        for item in module["items"]:
            meta = item.get("generation_meta") or {}
            rows.append({
                "module_id": module["module_id"],
                "topic": item.get("topic_id"),
                "valid": bool(item.get("valid")),
                "placeholder": bool(item.get("placeholder")),
                "retrieval_attempted": bool(meta.get("rag_attempted")),
                "retrieval_failed": bool(meta.get("retrieval_failed")),
                "passages": meta.get("retrieval_hits", 0),
                "difficulty": item.get("difficulty"),
            })
    return {"items": rows}


def _rate(rows: List[Dict[str, Any]], field: str) -> Optional[float]:
    values = [bool(r[field]) for r in rows if r.get(field) is not None]
    return sum(values) / len(values) if values else None


def run_metrics(record: Dict[str, Any]) -> Dict[str, Any]:
    """Every automatic measure for one run, as scenario-level rates."""
    planning = planning_checks(record)
    negotiation = negotiation_checks(record)
    responses = response_checks(record)["responses"]
    items = assessment_checks(record)["items"]
    grounded = [r for r in responses if r["mode"] == "grounded"]
    answered = [r for r in responses if not r["no_passage_above_threshold"]]
    usage = record["usage"]

    return {
        "scenario_id": record["scenario_id"],
        "condition": record["condition"]["id"],
        "repeat": record.get("repeat", 1),
        "model": record["model"]["requested"],
        "failed": record.get("failed", False),
        "planning": planning,
        "negotiation": negotiation,
        "counts": {"responses": len(responses), "items": len(items)},
        "rates": {
            # Retrieval and grounding
            "no_passage_above_threshold": _rate(grounded, "no_passage_above_threshold"),
            "low_confidence_retrieval": _rate([r for r in grounded if r["low_confidence_retrieval"] is not None],
                                              "low_confidence_retrieval"),
            "off_strand_passage_rate": (
                sum(r["off_strand_passages"] for r in grounded) / sum(r["passages"] for r in grounded)
                if sum(r["passages"] for r in grounded) else None
            ),
            # Instruction
            "model_written_refusal": _rate([r for r in responses if r["model_written_refusal"] is not None],
                                           "model_written_refusal"),
            "truncated_response": _rate(responses, "truncated"),
            # Per block: how often written code fails to parse
            "code_block_parse_failure": (
                sum(r["code_blocks_failing"] for r in responses) / sum(r["code_blocks"] for r in responses)
                if sum(r["code_blocks"] for r in responses) else None
            ),
            "code_block_deliberate_error_share": (
                sum(r["code_blocks_deliberate_errors"] for r in responses)
                / sum(r["code_blocks_failing"] for r in responses)
                if sum(r["code_blocks_failing"] for r in responses) else None
            ),
            # How much code was written at all, which differs sharply by condition
            "code_blocks_per_response": (
                sum(r["code_blocks"] for r in responses) / len(responses) if responses else None
            ),
            "response_with_broken_code": (
                1 - _rate([r for r in responses if r["code_parses"] is not None], "code_parses")
                if any(r["code_parses"] is not None for r in responses) else None
            ),
            # Citation behaviour that is automatic (the annotated measures come from E3)
            "response_without_citation": _rate(answered, "no_citation") if answered else None,
            "invalid_citation_marker_rate": (
                sum(r["invalid_citation_markers"] for r in answered) / sum(r["citation_markers"] for r in answered)
                if sum(r["citation_markers"] for r in answered) else None
            ),
            "citations_per_response": (
                sum(r["citation_markers"] for r in answered) / len(answered) if answered else None
            ),
            # Assessment
            "item_valid": _rate(items, "valid"),
            "item_placeholder": _rate(items, "placeholder"),
            "item_retrieval_failed": _rate([r for r in items if r["retrieval_attempted"]], "retrieval_failed"),
        },
        # Raw counts, so rates over items, blocks and markers can be pooled
        # rather than averaged over scenarios
        "pooled": {
            "responses": len(responses),
            "items": len(items),
            "items_invalid": sum(1 for i in items if not i["valid"]),
            "items_placeholder": sum(1 for i in items if i["placeholder"]),
            "code_blocks": sum(r["code_blocks"] for r in responses),
            "code_blocks_failing": sum(r["code_blocks_failing"] for r in responses),
            "code_blocks_deliberate_errors": sum(r["code_blocks_deliberate_errors"] for r in responses),
            "citation_markers": sum(r["citation_markers"] for r in responses),
            "invalid_markers": sum(r["invalid_citation_markers"] for r in responses),
            "responses_refused": sum(1 for r in responses if r["no_passage_above_threshold"]),
            # Every call, not only instruction: a planning call stopped by the token
            # cap yields a truncated syllabus, which must not be read as the planner
            # failing the schema. Zero on a backend that terminates on its own.
            "calls_truncated": sum(1 for c in record["usage"]["calls"]
                                   if c.get("finish_reason") == "length"),
            "calls_truncated_planning": sum(
                1 for c in record["usage"]["calls"]
                if c.get("finish_reason") == "length"
                and c.get("agent") in ("advocate", "designer", "extractor")),
        },
        "cost": {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cached_input_tokens": usage["cached_input_tokens"],
            "cost_usd": usage["cost_usd"],
            "wall_clock_s": record["wall_clock_s"],
            "llm_errors": usage["llm_errors"],
            "median_response_latency_s": (
                statistics.median([r["latency_s"] for r in responses if r["latency_s"] is not None])
                if any(r["latency_s"] is not None for r in responses) else None
            ),
        },
    }
