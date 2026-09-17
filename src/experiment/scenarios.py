"""
Controlled learner scenarios: a 3 x 2 x 2 x 2 full factorial (24 scenarios).

Scenarios are experimental inputs, not simulated learners: each fixes the
profile the system is given, and produces no scores. The set is generated once
and written to a versioned file that every condition and backend reuses
byte-identically. Generation is deterministic: running it again with the same
version and seed reproduces the same bytes.

Usage:
    python -m src.experiment.scenarios            # writes data/scenarios/scenarios_v1.json
    python -m src.experiment.scenarios --check    # verifies the file on disk is reproducible
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ..config import config
from ..models.learner_profile import LearnerModel

SCENARIO_SET_VERSION = "v1"
SEED = 20260917
SCENARIO_DIR = config.paths.data_dir / "scenarios"
TOPIC = "Introductory Python programming"

PRIOR_KNOWLEDGE_LEVELS = ["novice", "intermediate", "advanced"]

TIME_BUDGETS = {
    "4w": {"weekly_hours": 5.0, "duration_weeks": 4},
    "8w": {"weekly_hours": 5.0, "duration_weeks": 8},
}

GOAL_PROFILES = {
    "broad": {
        "description": "broad foundations across all four modules",
        "goals": [
            "Build a solid foundation across Python basics, control flow and functions, "
            "data structures, and object-oriented programming",
        ],
    },
    "narrow": {
        "description": "narrow applied focus on one strand (data structures)",
        "goals": [
            "Use Python data structures (lists, tuples, dictionaries and sets) to organise "
            "and process data in small practical scripts",
        ],
    },
}

PREFERENCE_PROFILES = {
    "P1": {"learning_style": ["reading_writing"], "pace": "slow", "difficulty_preference": "easy"},
    "P2": {"learning_style": ["kinesthetic"], "pace": "fast", "difficulty_preference": "hard"},
}

# The profile schema has no "novice" prior-knowledge level: a novice declares none.
PRIOR_KNOWLEDGE_TOPIC = "Python programming"


def scenario_file(version: str = SCENARIO_SET_VERSION) -> Path:
    return SCENARIO_DIR / f"scenarios_{version}.json"


def generate(version: str = SCENARIO_SET_VERSION, seed: int = SEED) -> Dict[str, Any]:
    """Build the scenario set. Pure function of (version, seed)."""
    rng = random.Random(seed)
    scenarios: List[Dict[str, Any]] = []
    factors = itertools.product(PRIOR_KNOWLEDGE_LEVELS, TIME_BUDGETS, GOAL_PROFILES, PREFERENCE_PROFILES)
    for number, (prior, budget_key, goal_key, pref_key) in enumerate(factors, start=1):
        budget = TIME_BUDGETS[budget_key]
        prefs = PREFERENCE_PROFILES[pref_key]
        scenario_id = f"S{number:02d}"
        scenarios.append({
            "scenario_id": scenario_id,
            "factors": {
                "prior_knowledge": prior,
                "time_budget": budget_key,
                "goal_profile": goal_key,
                "preference_profile": pref_key,
            },
            "topic": TOPIC,
            "weekly_hours": budget["weekly_hours"],
            "duration_weeks": budget["duration_weeks"],
            "total_hours": budget["weekly_hours"] * budget["duration_weeks"],
            "learner": {
                "learner_id": f"learner-{uuid.UUID(int=rng.getrandbits(128), version=4)}",
                "name": f"Scenario {scenario_id}",
                "goals": GOAL_PROFILES[goal_key]["goals"],
                "prior_knowledge": {} if prior == "novice" else {PRIOR_KNOWLEDGE_TOPIC: prior},
                **prefs,
            },
        })

    return {
        "scenario_set_version": version,
        "seed": seed,
        "generator": "src/experiment/scenarios.py",
        "design": "3 x 2 x 2 x 2 full factorial",
        "topic": TOPIC,
        "factor_levels": {
            "prior_knowledge": PRIOR_KNOWLEDGE_LEVELS,
            "time_budget": TIME_BUDGETS,
            "goal_profile": GOAL_PROFILES,
            "preference_profile": PREFERENCE_PROFILES,
        },
        "scenarios": scenarios,
    }


def serialise(scenario_set: Dict[str, Any]) -> bytes:
    return (json.dumps(scenario_set, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def load(version: str = SCENARIO_SET_VERSION) -> tuple[Dict[str, Any], str]:
    """Load a scenario set and return it with the SHA-256 of its bytes."""
    raw = scenario_file(version).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build_learner(scenario: Dict[str, Any]) -> LearnerModel:
    """Create the LearnerModel a scenario specifies (validated against the profile schema)."""
    spec = scenario["learner"]
    learner = LearnerModel(
        learner_id=spec["learner_id"],
        name=spec["name"],
        learning_style=list(spec["learning_style"]),
        pace=spec["pace"],
        difficulty_preference=spec["difficulty_preference"],
    )
    for goal in spec["goals"]:
        learner.add_goal(goal)
    for topic, level in spec["prior_knowledge"].items():
        learner.add_prior_knowledge(topic, level)
    learner._validate()
    return learner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default=SCENARIO_SET_VERSION)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--check", action="store_true", help="verify the existing file is reproducible")
    args = parser.parse_args()

    data = serialise(generate(args.version, args.seed))
    path = scenario_file(args.version)
    if args.check:
        ok = path.read_bytes() == data
        print(f"{path}: {'reproducible' if ok else 'DIFFERS from regenerated set'}")
        sys.exit(0 if ok else 1)
    if path.exists():
        sys.exit(f"{path} already exists. Scenario sets are written once; bump the version instead.")
    for scenario in json.loads(data)["scenarios"]:
        build_learner(scenario)  # every profile must validate before the set is written
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"Wrote {path} (sha256 {hashlib.sha256(data).hexdigest()})")


if __name__ == "__main__":
    main()
