"""
E1 ablation conditions.

| Condition | Planner                 | Retrieval | Negotiation | Citation instruction |
|-----------|-------------------------|-----------|-------------|----------------------|
| A1        | multi-agent             | yes       | yes         | yes                  |
| A2        | one agent, one prompt   | yes       | n/a         | yes                  |
| A3        | multi-agent             | no        | yes         | n/a                  |
| A4        | single-shot syllabus    | yes       | no          | yes                  |
| A5        | multi-agent             | yes       | yes         | no                   |

A1 run on any backend is also that backend's E2 arm.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

NEGOTIATION_ROUNDS = 3  # the system default (LearningOrchestrator.generate_syllabus)


@dataclass(frozen=True)
class Condition:
    id: str
    label: str
    single_agent: bool
    retrieval: bool
    citation_instruction: bool
    max_negotiation_rounds: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


CONDITIONS: Dict[str, Condition] = {
    "A1": Condition("A1", "Full LearnX", single_agent=False, retrieval=True,
                    citation_instruction=True, max_negotiation_rounds=NEGOTIATION_ROUNDS),
    "A2": Condition("A2", "Single-agent baseline", single_agent=True, retrieval=True,
                    citation_instruction=True, max_negotiation_rounds=0),
    "A3": Condition("A3", "No retrieval", single_agent=False, retrieval=False,
                    citation_instruction=False, max_negotiation_rounds=NEGOTIATION_ROUNDS),
    "A4": Condition("A4", "No negotiation", single_agent=False, retrieval=True,
                    citation_instruction=True, max_negotiation_rounds=0),
    "A5": Condition("A5", "No citation instruction", single_agent=False, retrieval=True,
                    citation_instruction=False, max_negotiation_rounds=NEGOTIATION_ROUNDS),
}
