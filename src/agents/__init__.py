"""
AI agents for personalized learning.

This module contains LangChain-based agents for:
- Syllabus planning (curriculum design, learner advocacy)
- Instruction (RAG-based teaching with citations)
- Assessment (adaptive testing and evaluation)
"""

from .syllabus_planner import *
from .instructor import *

__all__ = [
    "syllabus_planner",
    "instructor",
]
