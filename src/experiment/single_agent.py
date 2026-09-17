"""
A2: single-agent baseline.

One agent, with one system prompt, performs planning, instruction and
assessment. It is given everything the multi-agent system is given:
- the same model and backend;
- the same learner profile fields;
- the same retrieval stack (same vector store, top-k and threshold), the same
  [Source N] context format and the same citation instruction;
- the same syllabus JSON format, and the same deterministic post-processing
  (schema repair and hour rescaling) that the multi-agent planner applies.

It differs only in that no work is divided between specialised agents: there is
no advocate/designer negotiation, no separate extractor, and the tutor that
teaches and writes quiz items is the same agent that wrote the syllabus, with
its syllabus kept in its conversation.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..agents.assessment_generator import AssessmentGenerator, AssessmentQuestion
from ..agents.rag_instructor import (
    CITATION_INSTRUCTION,
    NO_CONTEXT_ANSWER,
    build_citations,
    extract_inline_citations,
    format_context,
    learning_style_guidance,
)
from ..agents.syllabus_planner import SyllabusPlanner, syllabus_json_spec
from ..config import config
from ..llm import make_chat_model, parse_json_response, tracked_invoke
from ..models.learner_profile import LearnerModel
from ..utils.vector_store import VectorStore

# Deployment temperature for the single agent: the instructor's, since most of
# its calls are instruction. Irrelevant under the deterministic policy.
SINGLE_AGENT_TEMPERATURE = 0.7

SYSTEM_PROMPT = """You are an AI tutor for {topic}. You do all of the tutoring work yourself: you design the learner's syllabus, you teach each topic, and you write the assessment questions.

Learner Profile:
- Name: {name}
- Learning Goals: {goals}
- Prior Knowledge: {prior_knowledge}
- Learning Style: {learning_style}
- Preferred Pace: {pace}
- Difficulty Preference: {difficulty}
- Available Time: {weekly_hours} hours/week for {duration_weeks} weeks
- Total Time Budget: {total_hours} hours

When designing the syllabus:
1. Align modules with the learner's stated goals
2. Keep total estimated hours within the time budget
3. Order modules in a logical progression, starting at an appropriate difficulty
4. Make prerequisites between modules explicit
5. Give each module specific, measurable learning outcomes and specific topics
6. Recommend accessible, high-quality resources

When teaching:
1. Answer using ONLY information from the provided context
2. Adapt your explanation complexity to the learner's level (novice/beginner/intermediate/advanced/expert)
3. Build on the learner's prior knowledge when relevant - connect new concepts to what they already know
4. Format your response according to the learner's learning style preferences:
{style_guidance}
5. Be clear, accurate, and pedagogical
6. If the context doesn't contain enough information, say so honestly
7. Break down complex concepts into understandable parts

When writing assessment questions:
1. Create a clear, unambiguous question
2. Provide 4 options (A, B, C, D)
3. Only ONE option should be correct
4. Make distractors plausible but clearly wrong
5. Match the specified difficulty and Bloom's level
6. Align with the learning objective"""

PLAN_TASK = """TASK: Design the learner's syllabus now.

Design 5-7 modules that comprehensively cover {topic} while respecting the time constraints. Each module needs an ID (format: m01-descriptive-slug), a title, 3-4 learning outcomes, 4-6 topics, estimated hours, prerequisites if any, and 2-3 recommended resources with names and URLs where possible.

Return the syllabus as JSON with this exact format:

{json_spec}

REQUIREMENTS:
1. Module IDs MUST match pattern: m01-lowercase-with-hyphens (m01, m02, m03, etc.)
2. Set prior_knowledge based on the learner's profile
3. Return ONLY the JSON, no additional text

JSON:"""

TEACH_TASK = """TASK: Teach the learner.

**Learner Level:** {learner_level}
**Question:** {question}

**Context from educational materials:**
{context}

{citation_block}**Answer:**"""

ASSESS_TASK = """TASK: Write one multiple-choice question.

**Topic:** {topic}
**Difficulty:** {difficulty} (very_easy/easy/medium/hard/very_hard)
**Bloom's Level:** {bloom_level} (remember/understand/apply/analyze/evaluate/create)
**Learning Objective:** {learning_objective}

**Context from teaching materials:**
{context}

**Format your response as JSON:**
{{
  "question_text": "...",
  "options": [
    {{"option_id": "A", "text": "...", "is_correct": false}},
    {{"option_id": "B", "text": "...", "is_correct": true}},
    {{"option_id": "C", "text": "...", "is_correct": false}},
    {{"option_id": "D", "text": "...", "is_correct": false}}
  ],
  "explanation": "Brief explanation of why B is correct",
  "bloom_level": "{bloom_level}"
}}

**Question:**"""


class SingleAgentTutor:
    """The A2 baseline: one agent that plans, teaches and assesses."""

    def __init__(
        self,
        learner: LearnerModel,
        vector_store: VectorStore,
        learner_level: str,
        model_name: Optional[str] = None,
    ):
        self.learner = learner
        self.vector_store = vector_store
        self.learner_level = learner_level
        self.model_name = model_name
        self.llm = make_chat_model("single_agent", temperature=SINGLE_AGENT_TEMPERATURE, model_name=model_name)
        # Reuse the planner only for its deterministic post-processing and fallback
        self._planner = SyllabusPlanner(learner=learner, model_name=model_name)
        self.system_message: Optional[SystemMessage] = None
        self.plan_exchange: List[Any] = []
        self.history: List[tuple[str, str]] = []
        self.last_run: Dict[str, Any] = {}

    def _prior_knowledge_text(self) -> str:
        prior = self.learner.get_prior_knowledge()
        if not prior:
            return "None stated (complete beginner)"
        return ", ".join(f"{topic} ({level})" for topic, level in prior.items())

    def _messages(self, task: str) -> List[Any]:
        """System prompt, the agent's own syllabus exchange, recent teaching, then the task."""
        recent = ""
        if self.history:
            recent = "**Recent Conversation:**\n" + "".join(
                f"Q{i}: {q}\nA{i}: {a[:200]}...\n" for i, (q, a) in enumerate(self.history[-3:], 1)
            ) + "\n"
        return [self.system_message, *self.plan_exchange, HumanMessage(content=recent + task)]

    def generate_syllabus(self, topic: str, duration_weeks: int, weekly_hours: float) -> Dict[str, Any]:
        self.system_message = SystemMessage(content=SYSTEM_PROMPT.format(
            topic=topic,
            name=self.learner.name,
            goals=", ".join(self.learner.get_goals()) or f"General knowledge in {topic}",
            prior_knowledge=self._prior_knowledge_text(),
            learning_style=", ".join(self.learner.learning_style),
            pace=self.learner.pace,
            difficulty=self.learner.difficulty_preference,
            weekly_hours=weekly_hours,
            duration_weeks=duration_weeks,
            total_hours=weekly_hours * duration_weeks,
            style_guidance=learning_style_guidance(self.learner.learning_style),
        ))
        task = PLAN_TASK.format(topic=topic, json_spec=syllabus_json_spec(topic, duration_weeks, weekly_hours))
        request = HumanMessage(content=task)
        reply, call_id = tracked_invoke(self.llm, [self.system_message, request])
        self.plan_exchange = [request, AIMessage(content=reply.content)]

        planner = self._planner
        planner.last_run = {
            "max_negotiation_rounds": 0,
            "rounds_completed": 0,
            "approved": None,
            "repairs": [],
            "prompts": {"single_agent_system": self.system_message.content, "plan_task": task},
            "plan_response": reply.content,
            "extraction_call_id": call_id,
        }
        parsed = planner.parse_syllabus_json(reply.content, topic, duration_weeks, weekly_hours)
        syllabus = planner.finalise_syllabus(parsed, duration_weeks, weekly_hours)
        self.last_run = planner.last_run
        return syllabus

    def teach_topic(self, topic: str) -> Dict[str, Any]:
        question = f"Teach me about {topic}. Explain the key concepts, provide examples, and cover the essential points."
        started = time.perf_counter()
        retrieved = self.vector_store.search(
            query=question,
            top_k=config.rag.top_k,
            min_similarity=config.rag.similarity_threshold,
        )
        retrieval_s = time.perf_counter() - started
        lesson: Dict[str, Any] = {
            "topic": topic,
            "question": question,
            "mode": "grounded",
            "refused": False,
            "retrieval_s": retrieval_s,
            "call_id": None,
            "retrieved": [
                {
                    "passage_index": rank,
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "source": doc.metadata.get("source"),
                    "url": doc.metadata.get("original_url"),
                    "doc_id": doc.metadata.get("doc_id"),
                    "strand": doc.metadata.get("strand"),
                    "similarity": score,
                    "content": doc.content,
                }
                for rank, (doc, score) in enumerate(retrieved, 1)
            ],
        }
        if not retrieved:
            lesson.update({"content": NO_CONTEXT_ANSWER, "refused": True, "citations": [],
                           "inline_citations": [], "confidence": 0.0, "prompt": None})
            return lesson

        task = TEACH_TASK.format(
            learner_level=self.learner_level,
            question=question,
            context=format_context(retrieved),
            citation_block=CITATION_INSTRUCTION + "\n\n",
        )
        messages = self._messages(task)
        reply, call_id = tracked_invoke(self.llm, messages)
        answer = reply.content
        self.history.append((question, answer))
        lesson.update({
            "content": answer,
            "citations": [asdict(c) for c in build_citations(retrieved)],
            "inline_citations": extract_inline_citations(answer, len(retrieved)),
            "confidence": min(1.0, sum(s for _, s in retrieved) / len(retrieved) * 1.2),
            "prompt": "\n\n".join(m.content for m in messages),
            "call_id": call_id,
        })
        return lesson

    def generate_question(self, module_id: str, topic: str, difficulty: str) -> AssessmentQuestion:
        bloom_level = AssessmentGenerator._suggest_bloom_level(None, difficulty)
        learning_objective = f"Assess understanding of {topic}"
        started = time.perf_counter()
        retrieved = self.vector_store.search(
            query=topic,
            top_k=config.rag.top_k,
            min_similarity=config.rag.similarity_threshold,
        )
        retrieval_s = time.perf_counter() - started
        context = (
            "\n\n".join(doc.content for doc, _ in retrieved)
            if retrieved else f"Generate a question about {topic} for educational assessment."
        )
        task = ASSESS_TASK.format(
            topic=topic, difficulty=difficulty, bloom_level=bloom_level,
            learning_objective=learning_objective, context=context,
        )
        messages = self._messages(task)
        reply, call_id = tracked_invoke(self.llm, messages)
        raw = reply.content
        parse_fallback = False
        try:
            data = parse_json_response(raw)
            if not isinstance(data, dict) or "question_text" not in data:
                raise json.JSONDecodeError("reply is not a question object", raw, 0)
        except json.JSONDecodeError:
            parse_fallback = True
            data = {
                "question_text": f"What is {topic}?",
                "options": [
                    {"option_id": "A", "text": "Option A", "is_correct": True},
                    {"option_id": "B", "text": "Option B", "is_correct": False},
                    {"option_id": "C", "text": "Option C", "is_correct": False},
                    {"option_id": "D", "text": "Option D", "is_correct": False},
                ],
                "explanation": "This is the correct answer.",
                "bloom_level": bloom_level,
            }
        return AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text=data.get("question_text", ""),
            question_type="multiple_choice",
            difficulty=difficulty,
            module_id=module_id,
            topic_id=topic,
            options=data.get("options"),
            explanation=data.get("explanation"),
            bloom_level=data.get("bloom_level", bloom_level),
            learning_objectives=[learning_objective],
            generation_meta={
                "rag_attempted": True,
                "retrieval_hits": len(retrieved),
                "retrieval_failed": not retrieved,
                "retrieved": [
                    {
                        "chunk_id": doc.metadata.get("chunk_id"),
                        "source": doc.metadata.get("source"),
                        "doc_id": doc.metadata.get("doc_id"),
                        "strand": doc.metadata.get("strand"),
                        "similarity": score,
                        "content": doc.content,
                    }
                    for doc, score in retrieved
                ],
                "retrieval_s": retrieval_s,
                "parse_fallback": parse_fallback,
                "raw_response": raw,
                "prompt": "\n\n".join(m.content for m in messages),
                "call_id": call_id,
            },
        )
