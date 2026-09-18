"""
Scenario runner: drives the real system over the controlled learner scenarios.

For every (condition, scenario) it generates a syllabus, one instructional
response per syllabus topic, and one multiple-choice item per syllabus topic,
and writes a single JSON record holding every artefact, the retrieved passages,
the exact prompts, and per-call token usage and latency. Nothing is scored here
and no learner behaviour is simulated: modules are visited in syllabus order
without the enrolment gating that models learner progress.

Usage:
    python -m src.experiment.runner --experiment e1 --model gpt-5.4-mini --conditions A1 A2 A3 A4 A5
    python -m src.experiment.runner --experiment e2 --model mistral:7b --base-url http://localhost:11434/v1
    python -m src.experiment.runner --experiment probe --model gpt-5.4-mini --conditions A1 --scenarios S01 --repeats 3

Existing record files are skipped, so an interrupted run can simply be restarted.
A run that raised an error is written to <scenario>.failed.json instead and is
retried on the next invocation. Experiment runs refuse to start on a working tree
with uncommitted code changes (--allow-dirty overrides, e.g. for smoke tests).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import config
from ..llm import OLLAMA_BASE_URL, current_run, make_chat_model, usage_log
from ..orchestrator import LearningOrchestrator, learner_level_for
from . import corpus, scenarios
from .conditions import CONDITIONS, Condition
from .single_agent import SingleAgentTutor

RECORD_VERSION = 1
RESULTS_DIR = config.paths.project_root / "results"
EXPERIMENT_DIRS = {
    "e1": "e1_ablation",
    "e2": "e2_backends",
    "probe": "e1_determinism_probe",
    "smoke": "smoke",
}

# USD per 1M tokens. Read on 2026-09-17 from https://developers.openai.com/api/docs/pricing
# (openai.com/api/pricing returned 403). Verify against the page before publication (D22).
PRICING_DATE = "2026-09-17"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"
PRICING = {
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "cached_input": None, "output": 1.50},
}

PACKAGES = ["langchain-core", "langchain-openai", "openai", "chromadb", "sentence-transformers", "transformers", "torch"]

# Local servers (Ollama) truncate prompts that exceed their context window without
# any error, and the OpenAI-compatible endpoint cannot set the window per request.
# Planning prompts exceed 9k tokens, so the server must be started with, e.g.,
# OLLAMA_CONTEXT_LENGTH=32768 ollama serve
MIN_LOCAL_CONTEXT = 32768

# If this many runs fail in a row, something is wrong with the backend (no
# credits, an outage, a bad model id) rather than with one scenario. Stop, so a
# dead backend cannot burn through the queue leaving a pile of failed records.
MAX_CONSECUTIVE_FAILURES = 3


def model_slug(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


CODE_PATHS = ["src", "schemas", "requirements.lock.txt"]


def code_state() -> Dict[str, Any]:
    """Commit, dirty flag, and a content hash of the code actually on disk."""
    root = config.paths.project_root
    digest = hashlib.sha256()
    for top in CODE_PATHS:
        path = root / top
        files = [path] if path.is_file() else sorted(
            f for f in path.rglob("*") if f.is_file() and f.suffix in {".py", ".json"}
        )
        for f in files:
            digest.update(str(f.relative_to(root)).encode() + b"\0" + f.read_bytes() + b"\0")
    state: Dict[str, Any] = {"content_sha256": digest.hexdigest(), "commit": None, "dirty": None}
    try:
        state["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain", "--", *CODE_PATHS], cwd=root, text=True)
        state["dirty"] = bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return state


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cost_usd(calls: List[Dict[str, Any]], model: str) -> Optional[float]:
    """API cost of a list of usage records at dated pricing, or None if the model is not priced."""
    price = PRICING.get(model)
    if price is None:
        return None
    total = 0.0
    for call in calls:
        cached = call.get("cached_input_tokens") or 0
        uncached = (call.get("input_tokens") or 0) - cached
        cached_price = price["cached_input"] if price["cached_input"] is not None else price["input"]
        total += uncached * price["input"] + cached * cached_price + (call.get("output_tokens") or 0) * price["output"]
    return total / 1_000_000


def _item_record(question) -> Dict[str, Any]:
    record = question.to_dict()
    record["generation_meta"] = question.generation_meta
    record["placeholder"] = bool(question.generation_meta.get("parse_fallback"))
    try:
        question.validate()
        record["valid"], record["validation_error"] = True, None
    except ValueError as exc:
        record["valid"], record["validation_error"] = False, str(exc)
    if record["placeholder"]:
        # The generator substitutes a template item when the reply cannot be parsed
        record["valid"], record["validation_error"] = False, "unparseable reply replaced by placeholder item"
    return record


def _context_truncated(calls: List[Dict[str, Any]], local: Optional[Dict[str, Any]]) -> Optional[int]:
    """Calls whose prompt plus output reached the local context window (a silent truncation risk)."""
    if not local or not local.get("context_length"):
        return None
    limit = local["context_length"] * 0.98
    return sum(1 for c in calls if (c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) >= limit)


def _error(stage: str, exc: BaseException, **context: Any) -> Dict[str, Any]:
    return {
        "stage": stage,
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(limit=5),
        **context,
    }


def run_multi_agent(condition: Condition, scenario: Dict[str, Any], model: str, store, record: Dict[str, Any]) -> None:
    learner = scenarios.build_learner(scenario)
    with tempfile.TemporaryDirectory() as tmp:
        orch = LearningOrchestrator(
            learner=learner,
            persist_dir=Path(tmp),
            model_name=model,
            vector_store=store if condition.retrieval else None,
            retrieval=condition.retrieval,
            citation_instruction=condition.citation_instruction,
        )
        started = time.perf_counter()
        syllabus = orch.generate_syllabus(
            topic=scenario["topic"],
            duration_weeks=scenario["duration_weeks"],
            weekly_hours=scenario["weekly_hours"],
            max_negotiation_rounds=condition.max_negotiation_rounds,
            save_to_disk=False,
            auto_fetch_content=False,
        )
        record["planning"] = {
            **orch.last_planner_run,
            "final_syllabus": syllabus,
            "wall_clock_s": time.perf_counter() - started,
        }
        record["learner_level"] = orch.learner_level()
        difficulty = learner.recommended_difficulty

        for module in syllabus.get("modules", []):
            module_record = _new_module_record(module, difficulty)
            record["modules"].append(module_record)
            try:
                # Visit modules in syllabus order; enrolment gating models learner progress
                orch.current_module_id = module["id"]
                orch.start_teaching_session(module_id=module["id"])
                teaching = orch.teach_module_content()
                module_record["lessons"] = teaching.get("lessons", [])
            except Exception as exc:  # recorded as a failure, run continues
                module_record["errors"].append(_error("instruction", exc))
            for topic in module.get("topics", []):
                try:
                    question = orch.assessment_generator.generate_question(
                        module_id=module["id"],
                        topic=topic,
                        question_type="multiple_choice",
                        difficulty=difficulty,
                        use_rag=orch._rag_active(),
                    )
                    module_record["items"].append(_item_record(question))
                except Exception as exc:
                    module_record["errors"].append(_error("assessment", exc, topic=topic))


def run_single_agent(condition: Condition, scenario: Dict[str, Any], model: str, store, record: Dict[str, Any]) -> None:
    learner = scenarios.build_learner(scenario)
    level = learner_level_for(learner)
    tutor = SingleAgentTutor(learner=learner, vector_store=store, learner_level=level, model_name=model)
    started = time.perf_counter()
    syllabus = tutor.generate_syllabus(
        topic=scenario["topic"],
        duration_weeks=scenario["duration_weeks"],
        weekly_hours=scenario["weekly_hours"],
    )
    record["planning"] = {**tutor.last_run, "final_syllabus": syllabus, "wall_clock_s": time.perf_counter() - started}
    record["learner_level"] = level
    difficulty = learner.recommended_difficulty

    for module in syllabus.get("modules", []):
        module_record = _new_module_record(module, difficulty)
        record["modules"].append(module_record)
        for number, topic in enumerate(module.get("topics", []), 1):
            try:
                lesson = tutor.teach_topic(topic)
                lesson["topic_number"] = number
                module_record["lessons"].append(lesson)
            except Exception as exc:
                module_record["errors"].append(_error("instruction", exc, topic=topic))
        for topic in module.get("topics", []):
            try:
                question = tutor.generate_question(module_id=module["id"], topic=topic, difficulty=difficulty)
                module_record["items"].append(_item_record(question))
            except Exception as exc:
                module_record["errors"].append(_error("assessment", exc, topic=topic))


def _new_module_record(module: Dict[str, Any], difficulty: str) -> Dict[str, Any]:
    return {
        "module_id": module.get("id"),
        "title": module.get("title"),
        "topics": module.get("topics", []),
        "item_difficulty": difficulty,
        "lessons": [],
        "items": [],
        "errors": [],
    }


def run_one(
    experiment: str,
    condition: Condition,
    scenario: Dict[str, Any],
    repeat: int,
    context: Dict[str, Any],
    store,
    out_path: Path,
) -> Dict[str, Any]:
    run_label = f"{context['model']['requested']}/{condition.id}/{scenario['scenario_id']}/r{repeat}"
    current_run.set(run_label)
    record: Dict[str, Any] = {
        "record_version": RECORD_VERSION,
        "experiment": experiment,
        "run_label": run_label,
        "condition": condition.to_dict(),
        "scenario_id": scenario["scenario_id"],
        "repeat": repeat,
        "scenario": scenario,
        **context,
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "planning": None,
        "modules": [],
        "errors": [],
    }
    started = time.perf_counter()
    try:
        if context["model"].get("base_url"):
            record["model"]["local_at_run"] = verify_local_context(
                context["model"]["base_url"], context["model"]["requested"])
        if condition.single_agent:
            run_single_agent(condition, scenario, context["model"]["requested"], store, record)
        else:
            run_multi_agent(condition, scenario, context["model"]["requested"], store, record)
    except Exception as exc:
        record["errors"].append(_error("run", exc))

    calls = usage_log.pop_run(run_label)
    record["run_finished_at"] = datetime.now(timezone.utc).isoformat()
    record["wall_clock_s"] = time.perf_counter() - started
    record["model"]["resolved"] = sorted({c["resolved_model"] for c in calls if c.get("resolved_model")})
    record["model"]["request_params_seen"] = sorted(
        {json.dumps(c.get("request_params"), sort_keys=True) for c in calls if c.get("request_params")}
    )
    record["model"]["system_fingerprints"] = sorted({c["system_fingerprint"] for c in calls if c.get("system_fingerprint")})
    record["usage"] = {
        "calls": calls,
        "by_agent": usage_log.summary_by_agent(calls),
        "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
        "cached_input_tokens": sum(c.get("cached_input_tokens") or 0 for c in calls),
        "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
        "llm_errors": sum(1 for c in calls if c.get("error")),
        "length_truncated_calls": sum(1 for c in calls if c.get("finish_reason") == "length"),
        "possibly_context_truncated_calls": _context_truncated(calls, context["model"].get("local")),
        "cost_usd": cost_usd(calls, context["model"]["requested"]),
    }

    record["failed"] = bool(record["errors"] or any(m["errors"] for m in record["modules"]))
    if record["failed"]:
        out_path = failed_path(out_path)  # kept for diagnosis, retried next time
    else:
        failed_path(out_path).unlink(missing_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp_path, out_path)
    return record


def failed_path(path: Path) -> Path:
    return path.with_name(path.stem + ".failed.json")


def failure_streak(streak: int, record: Dict[str, Any]) -> int:
    """Consecutive failed runs, reset by any run that completes cleanly."""
    return streak + 1 if record.get("failed") else 0


class LocalContextError(RuntimeError):
    """The local server is offering a smaller context window than the runs need."""


def verify_local_context(base_url: str, model: str) -> Dict[str, Any]:
    """
    Re-check the live context window. Checking once at startup is not enough: a
    server restarted mid-run (by a cleanup step, or by the desktop app) comes back
    with the 4k default, and prompts would then be truncated silently.
    """
    info = local_model_info(base_url, model)
    if (info.get("context_length") or 0) < MIN_LOCAL_CONTEXT:
        raise LocalContextError(
            f"{model} is served with a {info.get('context_length')}-token context, below the "
            f"{MIN_LOCAL_CONTEXT} these prompts need. Restart with "
            f"OLLAMA_CONTEXT_LENGTH={MIN_LOCAL_CONTEXT} ollama serve and rerun; completed runs are skipped."
        )
    return info


def local_model_info(base_url: str, model: str) -> Dict[str, Any]:
    """Loaded-model details from Ollama's native API (context window, digest, quantisation)."""
    import requests

    root = base_url.rstrip("/").removesuffix("/v1")
    names = {model, f"{model}:latest"}

    def loaded_entry():
        for entry in requests.get(f"{root}/api/ps", timeout=10).json().get("models", []):
            if entry.get("name") in names or entry.get("model") in names:
                return entry
        return None

    if loaded_entry() is None:
        # Nothing is loaded yet (a freshly started server), so load it with a
        # one-token request and then read the window it came up with
        requests.post(f"{root}/api/generate",
                      json={"model": model, "prompt": "ok", "stream": False,
                            "options": {"num_predict": 1}}, timeout=600)
    loaded = [e for e in [loaded_entry()] if e]
    for entry in loaded:
        if True:
            return {
                "context_length": entry.get("context_length"),
                "digest": entry.get("digest"),
                "parameter_size": entry.get("details", {}).get("parameter_size"),
                "quantization_level": entry.get("details", {}).get("quantization_level"),
                "size_vram": entry.get("size_vram"),
                "size": entry.get("size"),
            }
    sys.exit(f"{model} is not loaded on {root} after the preflight call; cannot verify its context window.")


def preflight(model: str) -> Dict[str, Any]:
    """One tiny call, to fail fast on a bad key, a missing model or an unsupported temperature."""
    llm = make_chat_model("preflight", temperature=0.0, model_name=model)
    try:
        reply = llm.invoke("Reply with the single word OK.")
    except Exception as exc:
        message = str(exc)
        hint = " Retry with --no-temperature." if "temperature" in message else ""
        sys.exit(f"Preflight call to {model} failed: {message}{hint}")
    return {"ok": True, "reply": reply.content, "resolved_model": (reply.response_metadata or {}).get("model_name")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", choices=sorted(EXPERIMENT_DIRS), required=True)
    parser.add_argument("--model", required=True, help="model identifier as the backend names it")
    parser.add_argument("--conditions", nargs="+", default=["A1"], choices=sorted(CONDITIONS))
    parser.add_argument("--scenarios", nargs="+", help="scenario ids (default: all 24)")
    parser.add_argument("--scenario-set", default=scenarios.SCENARIO_SET_VERSION)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--base-url", help=f"OpenAI-compatible endpoint, e.g. {OLLAMA_BASE_URL}")
    parser.add_argument("--no-temperature", action="store_true", help="backend rejects the temperature parameter")
    parser.add_argument("--reasoning-effort", help="passed through for reasoning models")
    parser.add_argument("--nondeterministic", action="store_true", help="use deployment temperatures (not for E1/E2)")
    parser.add_argument("--timeout", type=float, help="per-request timeout in seconds (default 60 API, 900 local)")
    parser.add_argument("--max-tokens", type=int,
                        help="cap on a single completion (default 8192). Lower it for a backend "
                             "whose context window cannot hold the prompt plus the cap: A1 prompts "
                             "reach about 9,000 tokens, so a 16k model needs roughly 6144")
    parser.add_argument("--allow-dirty", action="store_true", help="run with uncommitted code changes")
    parser.add_argument("--dry-run", action="store_true", help="list the work and exit")
    args = parser.parse_args()

    # Backend and determinism policy (D27), applied before any model is built
    config.model.model_name = args.model
    config.model.base_url = args.base_url
    if args.base_url:
        config.model.api_key = "ollama"  # local OpenAI-compatible servers ignore the key
    config.model.supports_temperature = not args.no_temperature
    config.model.reasoning_effort = args.reasoning_effort
    config.model.deterministic = not args.nondeterministic
    config.model.request_timeout = args.timeout or (900.0 if args.base_url else 60.0)
    if args.max_tokens:
        config.model.max_tokens = args.max_tokens

    scenario_set, scenario_sha = scenarios.load(args.scenario_set)
    wanted = set(args.scenarios or [s["scenario_id"] for s in scenario_set["scenarios"]])
    selected = [s for s in scenario_set["scenarios"] if s["scenario_id"] in wanted]
    if len(selected) != len(wanted):
        sys.exit(f"Unknown scenario ids: {sorted(wanted - {s['scenario_id'] for s in selected})}")

    out_root = RESULTS_DIR / EXPERIMENT_DIRS[args.experiment] / model_slug(args.model)
    jobs = []
    for cond_id in args.conditions:
        for scenario in selected:
            for repeat in range(1, args.repeats + 1):
                suffix = f"_r{repeat}" if args.repeats > 1 else ""
                path = out_root / cond_id / f"{scenario['scenario_id']}{suffix}.json"
                if not path.exists():
                    jobs.append((CONDITIONS[cond_id], scenario, repeat, path))

    print(f"{len(jobs)} runs to do -> {out_root}", file=sys.stderr)
    if args.dry_run or not jobs:
        for cond, scenario, repeat, path in jobs:
            print(f"  {cond.id} {scenario['scenario_id']} r{repeat} -> {path.relative_to(RESULTS_DIR)}", file=sys.stderr)
        return

    code = code_state()
    if code["dirty"] and not args.allow_dirty and args.experiment != "smoke":
        sys.exit("Uncommitted changes under src/, schemas/ or the lock file. Commit first, or pass --allow-dirty.")
    index_report = corpus.INDEX_REPORT_PATH.read_bytes()
    store = corpus.load_corpus_store()
    pre = preflight(args.model)
    local = None
    if args.base_url:
        try:
            local = verify_local_context(args.base_url, args.model)
        except LocalContextError as error:
            sys.exit(str(error))
    started_at = datetime.now(timezone.utc)
    context = {
        "model": {
            "requested": args.model,
            "base_url": args.base_url,
            "deterministic": config.model.deterministic,
            "temperature_supported": config.model.supports_temperature,
            "seed": config.model.random_seed if config.model.deterministic else None,
            "reasoning_effort": args.reasoning_effort,
            "request_timeout_s": config.model.request_timeout,
            "max_output_tokens": config.model.max_tokens,
            "local": local,
            "pricing": PRICING.get(args.model),
            "pricing_date": PRICING_DATE,
            "pricing_source": PRICING_SOURCE,
        },
        "scenario_set": {
            "version": scenario_set["scenario_set_version"],
            "seed": scenario_set["seed"],
            "sha256": scenario_sha,
        },
        "corpus": {
            "version": corpus.CORPUS_VERSION,
            "collection": corpus.COLLECTION_NAME,
            "index_report_sha256": hashlib.sha256(index_report).hexdigest(),
            "manifest_sha256": _sha256_file(corpus.MANIFEST_PATH),
            "relevance_labels_sha256": _sha256_file(corpus.LABELS_PATH),
            "top_k": config.rag.top_k,
            "similarity_threshold": config.rag.similarity_threshold,
        },
        "code": code,
        "packages": {name: metadata.version(name) for name in PACKAGES},
        "run_date": started_at.date().isoformat(),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    (out_root / f"run_manifest_{stamp}.json").write_text(json.dumps({
        **context,
        "experiment": args.experiment,
        "conditions": args.conditions,
        "scenarios": sorted(wanted),
        "repeats": args.repeats,
        "workers": args.workers,
        "preflight": pre,
        "command": sys.argv,
        "started_at": started_at.isoformat(),
    }, indent=2) + "\n", encoding="utf-8")

    log_path = out_root / "logs" / f"{stamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    done = failed = streak = 0
    with log_path.open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(copy_context().run, run_one, args.experiment, cond, scenario, repeat,
                            json.loads(json.dumps(context)), store, path): (cond.id, scenario["scenario_id"], repeat)
                for cond, scenario, repeat, path in jobs
            }
            for future in as_completed(futures):
                cond_id, scenario_id, repeat = futures[future]
                record = future.result()
                done += 1
                streak = failure_streak(streak, record)
                problems = len(record["errors"]) + sum(len(m["errors"]) for m in record["modules"])
                failed += 1 if record["failed"] else 0
                lessons = sum(len(m["lessons"]) for m in record["modules"])
                items = sum(len(m["items"]) for m in record["modules"])
                cost = record["usage"]["cost_usd"]
                print(
                    f"[{done}/{len(jobs)}] {cond_id} {scenario_id} r{repeat}: "
                    f"{len(record['modules'])} modules, {lessons} lessons, {items} items, "
                    f"{record['usage']['input_tokens'] + record['usage']['output_tokens']} tokens, "
                    f"{'$%.4f' % cost if cost is not None else 'n/a'}, {record['wall_clock_s']:.0f}s, "
                    f"{problems} errors",
                    file=sys.stderr,
                )
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    for pending in futures:
                        pending.cancel()
                    print(
                        f"\nStopping: {streak} runs failed in a row, so the backend is likely "
                        f"unavailable rather than these scenarios being at fault. Fix the cause and "
                        f"rerun the same command; completed runs are skipped and failed ones retried.",
                        file=sys.stderr,
                    )
                    break
    print(f"Finished {done} runs; {failed} failed and were saved as *.failed.json for retry. Log: {log_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
