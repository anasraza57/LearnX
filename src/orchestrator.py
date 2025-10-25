"""
Learning System Orchestrator - Phase 5

Orchestrates the complete learning pipeline:
1. Syllabus generation (or loading)
2. Learner profile management
3. Teaching sessions with RAG
4. Adaptive assessment
5. Mastery-based pathway adaptation
6. Session persistence

This is the main entry point for the complete personalized learning system.
"""

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
import os
import uuid

from .models.learner_profile import LearnerModel
from .agents.syllabus_planner import SyllabusPlanner
from .agents.rag_instructor import RAGInstructor, create_instructor_from_documents
from .agents.assessment_generator import AssessmentGenerator, AssessmentQuestion
from .agents.grading_agent import GradingAgent
from .models.quiz_session import AdaptiveQuiz
from .utils.oer_fetcher import auto_fetch_module_content
from .config import config


# ==================== Configuration Constants ====================
PASS_THRESHOLD = 0.70
ADVANCE_MASTERY_THRESHOLD = 0.75
PRACTICE_MASTERY_THRESHOLD = 0.60
MAX_DIFFICULTY = 2
MIN_DIFFICULTY = -2
SESSION_DIR = "data/learner_progress"


# ==================== Session State Models ====================

@dataclass
class SessionEvent:
    """
    Single learning event (lesson + assessment).

    Captures complete metrics for one topic cycle including mastery improvement,
    time spent, and citations used.
    """
    topic_id: str
    score: float
    difficulty_level: str  # "easy", "medium", "hard"
    difficulty_hint: int  # -2 (easier) to +2 (harder)
    mastery_before: float
    mastery_after: float
    mastery_delta: float
    time_taken_minutes: float
    started_at: str  # ISO 8601
    ended_at: str  # ISO 8601
    passed: bool
    cited_sources: List[str] = field(default_factory=list)


@dataclass
class SessionState:
    """
    Complete orchestrator session state for persistence.

    Tracks current position in learning path, difficulty progression,
    and complete event history for analytics.
    """
    session_id: str
    learner_id: str
    module_id: str
    topic_cursor: int  # Index into module's topics list
    difficulty_hint: int  # -2 (easier) to +2 (harder)
    current_teaching_session_id: Optional[str] = None
    current_quiz_session_id: Optional[str] = None
    last_citations: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)  # SessionEvent dicts
    completed: bool = False
    created_at: str = ""
    updated_at: str = ""


class LearningOrchestrator:
    """
    Main orchestrator for the personalized learning system.

    Manages the complete learning cycle:
    - Learner enrollment and profile management
    - Teaching session delivery
    - Adaptive assessment
    - Mastery tracking and pathway adaptation
    - Session persistence
    """

    def __init__(
        self,
        learner: LearnerModel,
        syllabus: Optional[Dict[str, Any]] = None,
        documents_path: Optional[Path] = None,
        persist_dir: Optional[Path] = None,
    ):
        """
        Initialize the learning orchestrator.

        Args:
            learner: Learner profile/model
            syllabus: Optional syllabus dict (if None, will need to generate)
            documents_path: Path to teaching documents for RAG
            persist_dir: Directory for saving sessions
        """
        self.learner = learner
        self.syllabus = syllabus
        self.documents_path = documents_path
        self.persist_dir = persist_dir or Path("data/sessions")

        # Initialize components
        self.instructor: Optional[RAGInstructor] = None
        self.assessment_generator: Optional[AssessmentGenerator] = None
        self.grading_agent = GradingAgent()

        # Track current session state
        self.current_module_id: Optional[str] = None
        self.current_teaching_session_id: Optional[str] = None
        self.current_quiz_session: Optional[AdaptiveQuiz] = None

        # Session tracking
        self.session_history: List[Dict[str, Any]] = []
        self._last_citations: List[str] = []  # Citations from last teaching interaction
        self._session_start_time: Optional[datetime] = None  # For time tracking
        self._current_topic_id: Optional[str] = None  # Current topic being taught/assessed

        # SessionState for typed state management
        self.session_state: Optional[SessionState] = None

        # Ensure persist directory exists
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    # ==================== Syllabus Generation ====================

    def generate_syllabus(
        self,
        topic: str,
        duration_weeks: int = 8,
        weekly_hours: float = 5.0,
        max_negotiation_rounds: int = 3,
        save_to_disk: bool = True,
        auto_fetch_content: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate personalized syllabus using multi-agent negotiation.

        Args:
            topic: Main subject/topic for the course
            duration_weeks: Course duration in weeks
            weekly_hours: Available study time per week
            max_negotiation_rounds: Maximum rounds of agent negotiation
            save_to_disk: Whether to save syllabus to disk
            auto_fetch_content: Whether to automatically fetch OER content for modules

        Returns:
            Generated syllabus dictionary
        """
        planner = SyllabusPlanner(learner=self.learner)

        syllabus = planner.generate_syllabus(
            topic=topic,
            duration_weeks=duration_weeks,
            weekly_hours=weekly_hours,
            max_negotiation_rounds=max_negotiation_rounds,
        )

        # Store syllabus in orchestrator
        self.syllabus = syllabus

        # Optionally save to disk
        if save_to_disk:
            planner.save_syllabus(syllabus, output_dir=self.persist_dir / "sessions" / "syllabi")

        # Automatically fetch educational content for modules
        if auto_fetch_content:
            self._auto_fetch_module_content()

        return syllabus

    # ==================== Learner Enrollment ====================

    def enroll_learner(self, module_id: str) -> Dict[str, Any]:
        """
        Enroll learner in a module from the syllabus.

        Args:
            module_id: Module identifier from syllabus

        Returns:
            Enrollment confirmation with module details

        Raises:
            ValueError: If prerequisites are not met or previous module not completed
        """
        if not self.syllabus:
            raise ValueError("Cannot enroll: No syllabus loaded")

        # Find module in syllabus
        module = self._find_module(module_id)
        if not module:
            raise ValueError(f"Module {module_id} not found in syllabus")

        # Check if learner has completed the previous module (if not first module)
        if self.current_module_id and self.current_module_id != module_id:
            # Check if current module is completed
            learner_data = self.learner.to_dict()
            current_module_progress = learner_data["progress"]["module_progress"].get(
                self.current_module_id, {}
            )

            # Check if passed assessment
            if current_module_progress.get("status") != "completed":
                raise ValueError(
                    f"Cannot enroll in new module: You must complete and pass the assessment "
                    f"for '{self.current_module_id}' first"
                )

        # Check prerequisites
        prerequisites = module.get("prerequisites", [])
        if prerequisites:
            learner_data = self.learner.to_dict()
            module_progress = learner_data["progress"].get("module_progress", {})

            unmet_prerequisites = []
            for prereq_id in prerequisites:
                prereq_status = module_progress.get(prereq_id, {})
                prereq_score = prereq_status.get("best_score", 0.0)

                # Require at least 70% mastery on prerequisites
                if prereq_score < (PASS_THRESHOLD * 100):
                    prereq_module = self._find_module(prereq_id)
                    prereq_title = prereq_module.get("title", prereq_id) if prereq_module else prereq_id
                    unmet_prerequisites.append(
                        f"{prereq_title} (current: {prereq_score:.1f}%, required: {PASS_THRESHOLD * 100:.0f}%)"
                    )

            if unmet_prerequisites:
                raise ValueError(
                    f"Cannot enroll in '{module.get('title')}': Prerequisites not met:\n"
                    + "\n".join(f"  - {prereq}" for prereq in unmet_prerequisites)
                )

        # Check prior knowledge for personalized insights and topic acceleration
        module_topics = module.get("topics", [])
        prior_knowledge = self.learner.get_prior_knowledge()

        relevant_prior_knowledge = {}
        skip_suggested = []  # Topics that can be skipped/accelerated
        acceleration_available = False

        for topic, level in prior_knowledge.items():
            # Check if any module topics relate to prior knowledge
            topic_lower = topic.lower()
            for module_topic in module_topics:
                if topic_lower in module_topic.lower() or module_topic.lower() in topic_lower:
                    relevant_prior_knowledge[topic] = level

                    # Suggest skipping/acceleration for intermediate or advanced knowledge
                    if level in ["intermediate", "advanced", "expert"]:
                        skip_suggested.append({
                            "topic": module_topic,
                            "prior_level": level,
                            "reason": f"You have {level} knowledge in this area"
                        })
                        acceleration_available = True
                    break

        # Start module in learner profile
        self.learner.start_module(module_id=module_id)

        self.current_module_id = module_id

        # Adjust initial difficulty based on prior knowledge
        initial_difficulty_hint = 0  # Neutral by default
        if relevant_prior_knowledge:
            # If learner has intermediate/advanced knowledge, start at higher difficulty
            advanced_count = sum(1 for level in relevant_prior_knowledge.values()
                                if level in ["intermediate", "advanced", "expert"])
            if advanced_count >= len(relevant_prior_knowledge) * 0.5:  # 50% or more advanced
                initial_difficulty_hint = 1  # Start slightly harder
                print(f"   🚀 Starting at increased difficulty due to prior knowledge in {advanced_count} area(s)")

        # Initialize SessionState for this module
        self.session_state = SessionState(
            session_id=f"sess-{uuid.uuid4()}",
            learner_id=self.learner.learner_id,
            module_id=module_id,
            topic_cursor=0,  # Start at first topic
            difficulty_hint=initial_difficulty_hint,  # Adjusted based on prior knowledge
            history=[],
            completed=False,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Build personalized enrollment response
        enrollment_response = {
            "module_id": module_id,
            "title": module.get("title"),
            "enrolled": True,
            "learner_id": self.learner.learner_id,
            "session_id": self.session_state.session_id,
            "prior_knowledge": relevant_prior_knowledge,  # Include prior knowledge insights
            "topics": module_topics,
            "acceleration_available": acceleration_available,  # Whether topic acceleration is available
        }

        # Add acceleration info if applicable
        if acceleration_available and skip_suggested:
            enrollment_response["skip_suggested"] = skip_suggested
            enrollment_response["acceleration_message"] = (
                f"Based on your prior knowledge, you may be able to accelerate through "
                f"{len(skip_suggested)} topic(s). We'll start at an increased difficulty level."
            )

        return enrollment_response

    def skip_to_topic(self, topic_index: int) -> Dict[str, Any]:
        """
        Skip to a specific topic in the current module based on prior knowledge.

        Args:
            topic_index: Index of the topic to skip to (0-based)

        Returns:
            Confirmation with new topic position
        """
        if not self.session_state:
            raise ValueError("No active session. Enroll in a module first.")

        module = self._find_module(self.current_module_id)
        if not module:
            raise ValueError(f"Module {self.current_module_id} not found")

        topics = module.get("topics", [])
        if topic_index < 0 or topic_index >= len(topics):
            raise ValueError(
                f"Invalid topic index {topic_index}. Module has {len(topics)} topics."
            )

        old_cursor = self.session_state.topic_cursor
        self.session_state.topic_cursor = topic_index
        self.session_state.updated_at = datetime.now(timezone.utc).isoformat()

        # Save updated state
        self._save_session_state()

        return {
            "skipped": True,
            "previous_topic_index": old_cursor,
            "current_topic_index": topic_index,
            "current_topic": topics[topic_index],
            "topics_skipped": topic_index - old_cursor if topic_index > old_cursor else 0,
            "message": f"Skipped to topic {topic_index + 1}/{len(topics)}: {topics[topic_index]}"
        }

    # ==================== Teaching Session ====================

    def start_teaching_session(
        self,
        module_id: Optional[str] = None,
        load_documents: bool = True,
    ) -> Dict[str, Any]:
        """
        Start a teaching session for a module.

        Args:
            module_id: Module to teach (uses current if None)
            load_documents: Whether to load documents for RAG

        Returns:
            Session info with teaching_session_id
        """
        module_id = module_id or self.current_module_id
        if not module_id:
            raise ValueError("No module specified for teaching")

        # Initialize RAG instructor if not already done
        if self.instructor is None and load_documents:
            self._initialize_instructor(module_id)

            # Note: instructor may be None if no documents found, which is OK
            # Teaching will work without RAG (no citations)

        # Generate teaching session ID
        import uuid
        self.current_teaching_session_id = f"ts-{uuid.uuid4()}"

        return {
            "teaching_session_id": self.current_teaching_session_id,
            "module_id": module_id,
            "rag_enabled": self.instructor is not None,
            "status": "active",
        }

    def teach(self, question: str, max_tokens: int = 500, search_all_modules: bool = False) -> Dict[str, Any]:
        """
        Deliver teaching content in response to learner question.

        Args:
            question: Learner's question
            max_tokens: Maximum response length (currently not used by RAG instructor)
            search_all_modules: If True, search across ALL modules, not just current one

        Returns:
            Teaching response with content and citations
        """
        if not self.instructor:
            raise ValueError("Teaching session not initialized. Call start_teaching_session() first.")

        # Get learner's prior knowledge
        prior_knowledge = self.learner.get_prior_knowledge()

        # Prepare metadata filter (if searching only current module)
        metadata_filter = None
        if not search_all_modules and self.current_module_id:
            # Only search current module's documents
            metadata_filter = {"module_id": self.current_module_id}

        # Get teaching response from RAG instructor with prior knowledge
        response = self.instructor.teach(
            question=question,
            prior_knowledge=prior_knowledge,
            metadata_filter=metadata_filter
        )

        # Store citations for session tracking
        citations_list = [asdict(c) for c in response.citations]

        # Create simplified citation strings for tracking
        self._last_citations = []
        for c in citations_list:
            source = c.get('source', 'unknown')
            url = c.get('url')
            if url:
                self._last_citations.append(f"{source} ({url})")
            elif c.get('page'):
                self._last_citations.append(f"{source} (p.{c.get('page')})")
            else:
                self._last_citations.append(source)

        # Teaching session tracked in orchestrator's session_state

        return {
            "response": response.answer,
            "citations": citations_list,
            "cited_sources": self._last_citations,  # Simplified source list
            "teaching_session_id": self.current_teaching_session_id,
            "searched_all_modules": search_all_modules,
        }

    def ask_general_question(self, question: str) -> Dict[str, Any]:
        """
        Ask a general question about ANY topic in the syllabus, not limited to current module.

        This is useful when learners want to:
        - Ask about topics from other modules
        - Get broader context
        - Explore related concepts

        Args:
            question: Any question about course content

        Returns:
            Teaching response with citations from across all modules
        """
        # Create a general instructor if none exists (searches all documents)
        if not self.instructor:
            # Initialize instructor with ALL documents (not just current module)
            documents_dir = self.persist_dir / "documents"
            if documents_dir.exists():
                from src.agents.rag_instructor import create_instructor_from_documents

                # Get learner data for personalization
                learner_data = self.learner.to_dict()
                learning_style = learner_data.get("learning_style", "mixed")
                interests = learner_data.get("personal_info", {}).get("interests", [])

                self.instructor = create_instructor_from_documents(
                    documents_dir=documents_dir,
                    learning_style=learning_style,
                    interests=interests,
                )

        # Search across ALL modules
        return self.teach(question=question, search_all_modules=True)

    def teach_module_content(self) -> Dict[str, Any]:
        """
        Proactively teach all topics in the current module sequentially.

        This provides a structured lesson covering all module topics,
        with optional Q&A afterwards.

        Returns:
            Dict with lessons for each topic and citations
        """
        if not self.current_module_id:
            raise ValueError("No module enrolled. Call enroll_learner() first.")

        # Get module details
        module = self._find_module(self.current_module_id)
        if not module:
            raise ValueError(f"Module {self.current_module_id} not found in syllabus")

        topics = module.get("topics", [])
        outcomes = module.get("outcomes", [])

        if not topics:
            return {
                "module_id": self.current_module_id,
                "module_title": module.get("title"),
                "lessons": [],
                "message": "No topics defined for this module"
            }

        lessons = []
        all_citations = []

        # Teach each topic sequentially
        for i, topic in enumerate(topics, 1):
            # Generate teaching content for this topic
            question = f"Teach me about {topic}. Explain the key concepts, provide examples, and cover the essential points."

            if self.instructor:
                # Use RAG-based teaching with citations
                response = self.instructor.teach(question=question)

                lesson = {
                    "topic_number": i,
                    "topic": topic,
                    "content": response.answer,
                    "citations": [asdict(c) for c in response.citations],
                    "confidence": response.confidence,
                }

                all_citations.extend([asdict(c) for c in response.citations])
            else:
                # Fallback: Generate content without RAG
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=config.model.model_name,
                    temperature=0.7,
                    api_key=config.model.api_key,
                )

                prompt = f"""You are teaching a module on {module.get('title')}.

Topic: {topic}

Learning Outcomes for this module:
{chr(10).join(f"- {outcome}" for outcome in outcomes)}

Provide a comprehensive lesson on {topic}. Include:
1. Clear explanations of key concepts
2. Practical examples
3. How it relates to the learning outcomes
4. Important points to remember

Length: 300-500 words."""

                response = llm.invoke(prompt)

                lesson = {
                    "topic_number": i,
                    "topic": topic,
                    "content": response.content,
                    "citations": [],
                    "confidence": 0.5,  # Lower confidence without citations
                }

            lessons.append(lesson)

        return {
            "module_id": self.current_module_id,
            "module_title": module.get("title"),
            "total_topics": len(topics),
            "lessons": lessons,
            "all_citations": all_citations,
            "teaching_session_id": self.current_teaching_session_id,
        }

    # ==================== Assessment Session ====================

    def start_assessment(
        self,
        module_id: Optional[str] = None,
        num_questions: Optional[int] = None,
        difficulty: Optional[str] = None,
        adaptive: bool = True,
    ) -> Dict[str, Any]:
        """
        Start an adaptive assessment session with intelligent defaults.

        Args:
            module_id: Module to assess (uses current if None)
            num_questions: Number of questions (auto-determined if None)
            difficulty: Starting difficulty (uses learner's performance if None)
            adaptive: Whether to adapt difficulty

        Returns:
            Quiz session info with first question
        """
        module_id = module_id or self.current_module_id
        if not module_id:
            raise ValueError("No module specified for assessment")

        # Get module details
        module = self._find_module(module_id)
        if not module:
            raise ValueError(f"Module {module_id} not found")

        # Initialize assessment generator if needed
        if self.assessment_generator is None:
            vector_store = self.instructor.vector_store if self.instructor else None
            self.assessment_generator = AssessmentGenerator(vector_store=vector_store)

        # Auto-determine number of questions based on module topics
        if num_questions is None:
            topics = module.get("topics", [])
            # 1-2 questions per topic, minimum 3, maximum 10
            num_questions = min(10, max(3, len(topics) * 2))

        # Auto-determine starting difficulty based on learner's performance
        if difficulty is None:
            learner_data = self.learner.to_dict()
            analytics = learner_data.get("performance_analytics", {})

            # Use recommended difficulty from learner model
            recommended = self.learner.recommended_difficulty
            difficulty = recommended if recommended != "unknown" else "medium"

            # Override with session state difficulty hint if available
            if self.session_state:
                difficulty_map = {
                    -2: "easy",    # Remediation level 2
                    -1: "easy",    # Remediation level 1
                    0: "medium",   # Neutral
                    1: "medium",   # Slight challenge
                    2: "hard",     # Advanced
                }
                difficulty = difficulty_map.get(self.session_state.difficulty_hint, difficulty)

        # Create adaptive quiz
        self.current_quiz_session = AdaptiveQuiz(
            learner_id=self.learner.learner_id,
            module_id=module_id,
            teaching_session_id=self.current_teaching_session_id,
            starting_difficulty=difficulty,
            num_questions=num_questions,
            adaptive=adaptive,
        )

        # Track session start time for metrics
        self._session_start_time = datetime.now(timezone.utc)

        # Generate first question automatically
        topics = module.get("topics", [])
        if topics:
            first_topic = topics[0]
            first_question = self.generate_question(
                topic=first_topic,
                question_type="multiple_choice",
                difficulty=difficulty
            )
        else:
            first_question = None

        return {
            "quiz_session_id": self.current_quiz_session.session_id,
            "module_id": module_id,
            "module_title": module.get("title"),
            "num_questions": num_questions,
            "adaptive": adaptive,
            "starting_difficulty": difficulty,
            "started_at": self._session_start_time.isoformat(),
            "current_question": self._format_question(first_question) if first_question else None,
            "current_question_number": 1,
            "total_questions": num_questions,
            "difficulty_reason": f"Based on your performance history (recommended: {self.learner.recommended_difficulty})"
        }

    def generate_question(
        self,
        topic: str,
        question_type: str = "multiple_choice",
        difficulty: Optional[str] = None,
    ) -> AssessmentQuestion:
        """
        Generate a question for the current assessment.

        Args:
            topic: Topic for the question
            question_type: Type of question
            difficulty: Difficulty level (uses quiz's current if None)

        Returns:
            Generated question
        """
        if not self.current_quiz_session:
            raise ValueError("No active assessment. Call start_assessment() first.")

        if not self.assessment_generator:
            raise ValueError("Assessment generator not initialized")

        # Use quiz's current difficulty if not specified
        difficulty = difficulty or self.current_quiz_session.current_difficulty

        # Generate question
        question = self.assessment_generator.generate_question(
            module_id=self.current_module_id,
            topic=topic,
            question_type=question_type,
            difficulty=difficulty,
            use_rag=self.instructor is not None,
        )

        # Validate and add to quiz
        question.validate()
        self.current_quiz_session.add_question(question)

        return question

    def submit_answer(
        self,
        answer: str,
        time_taken_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Submit learner's answer to current question and get next question.

        Args:
            answer: Learner's answer
            time_taken_seconds: Time spent on question

        Returns:
            Response with grading results and next question (if available)
        """
        if not self.current_quiz_session:
            raise ValueError("No active assessment")

        if not self.current_quiz_session.questions:
            raise ValueError("No questions in assessment")

        # Get current question (last added question)
        current_question = self.current_quiz_session.questions[-1]

        # Submit answer (auto-grades if possible)
        response = self.current_quiz_session.submit_answer(
            question_id=current_question.question_id,
            learner_answer=answer,
            time_taken_seconds=time_taken_seconds,
        )

        # If needs manual grading, grade with LLM
        if response.score is None:
            grading_result = self.grading_agent.grade_response(current_question, answer)
            response.score = grading_result.score
            response.is_correct = grading_result.is_correct
            response.feedback = grading_result.feedback
            response.graded_by = "llm"
            response.response_status = "graded"

        # Prepare result
        result = {
            "question_number": len(self.current_quiz_session.responses),
            "total_questions": self.current_quiz_session.num_questions,
            "is_correct": response.is_correct,
            "score": response.score,
            "feedback": response.feedback,
            "graded_by": response.graded_by,
            "current_difficulty": self.current_quiz_session.current_difficulty,
            "questions_remaining": self.current_quiz_session.num_questions - len(self.current_quiz_session.responses),
        }

        # Generate next question if not done
        if len(self.current_quiz_session.responses) < self.current_quiz_session.num_questions:
            module = self._find_module(self.current_module_id)
            topics = module.get("topics", [])

            # Cycle through topics
            topic_index = len(self.current_quiz_session.responses) % len(topics)
            next_topic = topics[topic_index] if topics else "General"

            # Generate next question with current (adapted) difficulty
            next_question = self.generate_question(
                topic=next_topic,
                question_type="multiple_choice",
                difficulty=self.current_quiz_session.current_difficulty
            )

            result["next_question"] = self._format_question(next_question)
            result["next_question_number"] = len(self.current_quiz_session.responses) + 1
            result["assessment_complete"] = False
        else:
            result["next_question"] = None
            result["assessment_complete"] = True
            result["message"] = "All questions answered! Click 'Complete Assessment' to see your final results."

        return result

    def complete_assessment(self) -> Dict[str, Any]:
        """
        Complete the current assessment and update learner profile.

        Returns:
            Quiz results and recommendations
        """
        if not self.current_quiz_session:
            raise ValueError("No active assessment")

        # Complete quiz
        result = self.current_quiz_session.complete_quiz()

        # Calculate time metrics
        end_time = datetime.now(timezone.utc)
        if self._session_start_time:
            time_delta = (end_time - self._session_start_time).total_seconds() / 60.0  # minutes
        else:
            time_delta = 5.0  # Fallback

        # Get mastery before (from module_progress)
        learner_data_before = self.learner.to_dict()
        module_progress_before = learner_data_before["progress"].get("module_progress", {})
        mastery_before = module_progress_before.get(self.current_module_id, {}).get("best_score", 0.0)

        # Update learner profile with quiz results
        self.learner.record_quiz_result(
            quiz_session_id=self.current_quiz_session.session_id,
            module_id=self.current_module_id,
            score=result["score"],
            difficulty=self.current_quiz_session.starting_difficulty,
            num_questions=len(self.current_quiz_session.questions),
            time_taken_minutes=int(time_delta),  # Convert to integer for schema compliance
            passed=result["passed"],
        )

        # Mark module as completed if passed
        if result["passed"]:
            self.learner.complete_module(
                module_id=self.current_module_id,
                score=result["score"],
                time_spent_minutes=int(time_delta),
            )

        # Get mastery after update (from module_progress)
        learner_data_after = self.learner.to_dict()
        module_progress_after = learner_data_after["progress"].get("module_progress", {})
        mastery_after = module_progress_after.get(self.current_module_id, {}).get("best_score", 0.0)
        mastery_delta = mastery_after - mastery_before

        # Save quiz session
        self._save_quiz_session(self.current_quiz_session)

        # Create session event for history
        session_event = {
            "type": "assessment",
            "session_id": self.current_quiz_session.session_id,
            "module_id": self.current_module_id,
            "score": result["score"],
            "passed": result["passed"],
            "difficulty": self.current_quiz_session.starting_difficulty,
            "time_taken_minutes": time_delta,
            "mastery_before": mastery_before,
            "mastery_after": mastery_after,
            "mastery_delta": mastery_delta,
            "cited_sources": self._last_citations,  # From teaching session
            "started_at": self._session_start_time.isoformat() if self._session_start_time else None,
            "ended_at": end_time.isoformat(),
            "timestamp": end_time.isoformat(),
        }
        self.session_history.append(session_event)

        # Add metrics to result
        result["metrics"] = {
            "time_taken_minutes": time_delta,
            "mastery_before": mastery_before,
            "mastery_after": mastery_after,
            "mastery_delta": mastery_delta,
            "cited_sources_count": len(self._last_citations),
        }

        # Apply pathway adaptation if SessionState is active
        if self.session_state:
            # Create SessionEvent
            session_event_obj = SessionEvent(
                topic_id=self._current_topic_id or self.current_module_id,  # Use topic if set, fallback to module
                score=result["score"],
                difficulty_level=self.current_quiz_session.starting_difficulty,
                difficulty_hint=self.session_state.difficulty_hint,
                mastery_before=mastery_before,
                mastery_after=mastery_after,
                mastery_delta=mastery_delta,
                time_taken_minutes=time_delta,
                started_at=self._session_start_time.isoformat() if self._session_start_time else end_time.isoformat(),
                ended_at=end_time.isoformat(),
                passed=result["passed"],
                cited_sources=self._last_citations,
            )

            # Add to session state history
            self.session_state.history.append(asdict(session_event_obj))

            # Apply advance or remediation
            current_module = self._find_module(self.current_module_id)
            if result["passed"] and result["score"] >= (PASS_THRESHOLD * 100):
                self.session_state = self._advance_cursor(self.session_state, current_module)
            else:
                self.session_state = self._apply_remediation(self.session_state)

            # Save updated state
            self._save_session_state()

        return result

    # ==================== Pathway Navigation Helpers ====================

    def _advance_cursor(self, state: SessionState, current_module: Dict[str, Any]) -> SessionState:
        """
        Advance topic cursor after successful mastery.

        Args:
            state: Current session state
            current_module: Module dictionary from syllabus

        Returns:
            Updated session state
        """
        topics = current_module.get("topics", [])

        # Move to next topic
        state.topic_cursor += 1

        # Check if module completed
        if state.topic_cursor >= len(topics):
            state.completed = True
            print(f"✅ Module {state.module_id} completed!")

            # Check for next module
            next_module_id = self._get_next_module(state.module_id)
            if next_module_id:
                print(f"📚 Next module available: {next_module_id}")
            else:
                print("🎉 All modules completed!")

        state.updated_at = datetime.now(timezone.utc).isoformat()
        return state

    def _apply_remediation(self, state: SessionState) -> SessionState:
        """
        Apply remediation strategy after poor performance.

        Lowers difficulty and prepares for review/reteaching.

        Args:
            state: Current session state

        Returns:
            Updated session state with lowered difficulty
        """
        # Decrease difficulty (with floor)
        state.difficulty_hint = max(MIN_DIFFICULTY, state.difficulty_hint - 1)

        print(f"📉 Applying remediation: difficulty adjusted to {state.difficulty_hint}")
        print("💡 Recommendation: Review previous teaching materials before retrying")

        state.updated_at = datetime.now(timezone.utc).isoformat()
        return state

    # ==================== Mastery-Based Adaptation ====================

    def adapt_pathway(self) -> Dict[str, Any]:
        """
        Adapt learning pathway based on current mastery levels.

        Uses quiz results and mastery levels to determine:
        - Should learner advance to next module?
        - Should learner review current module?
        - Which topics need more practice?

        Returns:
            Adaptation recommendations
        """
        if not self.current_module_id:
            return {"action": "enroll", "message": "No current module"}

        # Get latest assessment from learner data
        learner_data = self.learner.to_dict()
        assessment_history = learner_data["performance_analytics"].get("assessment_history", [])
        if not assessment_history:
            return {"action": "assess", "message": "No assessments yet"}

        latest = assessment_history[-1]

        # Get mastery level for current module from module_progress
        module_progress = learner_data["progress"].get("module_progress", {})
        current_mastery = module_progress.get(self.current_module_id, {}).get("best_score", 0.0) / 100.0

        # Decision logic using constants
        if latest["passed"] and current_mastery >= ADVANCE_MASTERY_THRESHOLD:
            action = "advance"
            message = f"Strong mastery ({current_mastery:.1%}). Ready for next module."
            next_module = self._get_next_module(self.current_module_id)
        elif latest["passed"] and current_mastery >= PRACTICE_MASTERY_THRESHOLD:
            action = "practice"
            message = f"Good progress ({current_mastery:.1%}). Additional practice recommended."
            next_module = self.current_module_id
        elif not latest["passed"] or current_mastery < PRACTICE_MASTERY_THRESHOLD:
            action = "review"
            message = f"Needs review ({current_mastery:.1%}). More teaching recommended."
            next_module = self.current_module_id
        else:
            action = "continue"
            message = "Continue current module"
            next_module = self.current_module_id

        return {
            "action": action,
            "message": message,
            "current_module": self.current_module_id,
            "current_mastery": current_mastery,
            "next_module": next_module,
            "last_score": latest["score"],
            "last_passed": latest["passed"],
        }

    # ==================== Session Persistence ====================

    def save_state(self, filename: Optional[str] = None) -> Path:
        """
        Save current orchestrator state to disk.

        Now delegates to _save_session_state() for SessionState,
        and also saves legacy dict format for backward compatibility.

        Args:
            filename: Optional filename (auto-generated if None)

        Returns:
            Path to saved file
        """
        # Save SessionState if active (preferred method)
        if self.session_state:
            self._save_session_state()

        # Also save legacy dict format for backward compatibility
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"orchestrator_state_{self.learner.learner_id}_{timestamp}.json"

        filepath = self.persist_dir / filename

        state = {
            "learner_id": self.learner.learner_id,
            "current_module_id": self.current_module_id,
            "current_teaching_session_id": self.current_teaching_session_id,
            "current_quiz_session_id": self.current_quiz_session.session_id if self.current_quiz_session else None,
            "session_history": self.session_history,
            "last_citations": self._last_citations,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        # Atomic write: write to temp file then replace
        temp_filepath = filepath.with_suffix(".json.tmp")
        try:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            # Atomic replace (POSIX-compliant)
            os.replace(temp_filepath, filepath)
        except Exception as e:
            # Clean up temp file if write failed
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise e

        return filepath

    def load_state(self, filepath: Path) -> None:
        """
        Load orchestrator state from disk.

        Args:
            filepath: Path to state file
        """
        with open(filepath, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.current_module_id = state.get("current_module_id")
        self.current_teaching_session_id = state.get("current_teaching_session_id")
        self.session_history = state.get("session_history", [])
        self._last_citations = state.get("last_citations", [])

    # ==================== Helper Methods ====================

    def _initialize_instructor(self, module_id: str) -> None:
        """Initialize RAG instructor with documents and learner preferences."""
        # Try multiple document locations
        search_paths = []

        if self.documents_path:
            search_paths.append(self.documents_path)

        # Default locations to search
        search_paths.extend([
            Path("data/documents") / module_id,  # Module-specific folder
            Path("data/documents"),  # General documents folder
            Path("documents") / module_id,
            Path("documents"),
        ])

        # Find first path with documents (PDF or Markdown)
        doc_files = []
        for path in search_paths:
            if path.exists():
                pdfs = list(path.glob("*.pdf"))
                mds = list(path.glob("*.md"))
                all_docs = pdfs + mds

                if all_docs:
                    doc_files = all_docs
                    print(f"📚 Found {len(doc_files)} documents in: {path} ({len(pdfs)} PDFs, {len(mds)} Markdown)")
                    break

        if not doc_files:
            print(f"⚠️  No documents found for RAG. Searched: {[str(p) for p in search_paths[:3]]}")
            print(f"    Teaching will work without citations. To enable RAG, add documents to: data/documents/")
            return

        # Use the directory that contains the documents
        documents_dir = doc_files[0].parent

        # Get learner's learning style and interests
        learner_data = self.learner.to_dict()
        learning_style = learner_data.get("cognitive_profile", {}).get("learning_style", ["visual"])
        interests = learner_data.get("personal_info", {}).get("interests", [])

        self.instructor = create_instructor_from_documents(
            documents_dir=documents_dir,
            collection_name=f"module_{module_id}",
            force_reload=True,  # Always reload to pick up latest metadata (URLs, source types)
            learning_style=learning_style,  # Pass learning style to instructor
            interests=interests,  # Pass interests for personalized examples
        )

        # Share vector store with assessment generator
        if self.instructor and self.instructor.vector_store:
            self.assessment_generator = AssessmentGenerator(
                vector_store=self.instructor.vector_store
            )

    def _find_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        """Find module in syllabus by ID."""
        if not self.syllabus or "modules" not in self.syllabus:
            return None

        for module in self.syllabus["modules"]:
            if module.get("id") == module_id:
                return module
        return None

    def _get_next_module(self, current_module_id: str) -> Optional[str]:
        """Get next module ID from syllabus."""
        if not self.syllabus or "modules" not in self.syllabus:
            return None

        modules = self.syllabus["modules"]
        for i, module in enumerate(modules):
            if module.get("id") == current_module_id:
                if i + 1 < len(modules):
                    return modules[i + 1].get("id")
        return None

    def _save_quiz_session(self, quiz: AdaptiveQuiz) -> None:
        """Save quiz session to disk in quiz_sessions subfolder."""
        # Create quiz_sessions directory if it doesn't exist
        quiz_sessions_dir = self.persist_dir / "quiz_sessions"
        quiz_sessions_dir.mkdir(exist_ok=True)

        filename = f"quiz_session_{quiz.session_id}.json"
        filepath = quiz_sessions_dir / filename

        # Convert quiz to dict (simplified for now)
        quiz_data = {
            "session_id": quiz.session_id,
            "learner_id": quiz.learner_id,
            "module_id": quiz.module_id,
            "teaching_session_id": quiz.teaching_session_id,
            "status": quiz.status,
            "score": quiz.overall_score,
            "passed": quiz.passed,
            "num_questions": len(quiz.questions),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(filepath, "w") as f:
            json.dump(quiz_data, f, indent=2)

    def _load_quiz_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load quiz session from disk.

        Args:
            session_id: Quiz session ID to load

        Returns:
            Quiz session data dict, or None if not found
        """
        quiz_sessions_dir = self.persist_dir / "quiz_sessions"
        filename = f"quiz_session_{session_id}.json"
        filepath = quiz_sessions_dir / filename

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading quiz session {session_id}: {e}")
            return None

    def _save_session_state(self) -> None:
        """Save SessionState atomically to disk."""
        if not self.session_state:
            return

        # Ensure session directory exists
        session_dir = Path(SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)

        # File path based on learner ID
        filepath = session_dir / f"{self.session_state.learner_id}_session.json"
        temp_filepath = filepath.with_suffix(".json.tmp")

        try:
            # Write to temp file
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(asdict(self.session_state), f, indent=2, ensure_ascii=False)

            # Atomic replace
            os.replace(temp_filepath, filepath)
        except Exception as e:
            # Clean up temp file on error
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise e

    def _load_session_state(self, learner_id: str) -> Optional[SessionState]:
        """Load SessionState from disk."""
        session_dir = Path(SESSION_DIR)
        filepath = session_dir / f"{learner_id}_session.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                state_dict = json.load(f)

            # Reconstruct SessionState
            return SessionState(**state_dict)
        except Exception as e:
            print(f"Warning: Failed to load session state: {e}")
            return None

    def _format_question(self, question: AssessmentQuestion) -> Dict[str, Any]:
        """
        Format a question for display in UI.

        Args:
            question: AssessmentQuestion object

        Returns:
            Formatted question dictionary
        """
        if not question:
            return None

        formatted = {
            "question_id": question.question_id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "difficulty": question.difficulty,
            "points": question.points,
        }

        if question.question_type == "multiple_choice" and question.options:
            formatted["options"] = [
                {
                    "option_id": opt.get("option_id"),
                    "text": opt.get("text"),
                }
                for opt in question.options
            ]

        return formatted

    def _auto_fetch_module_content(self) -> None:
        """
        Automatically fetch educational content for all modules in the syllabus.
        Uses Wikipedia and synthetic generation to populate document store.
        Prioritizes content based on learner's interests.
        """
        if not self.syllabus or "modules" not in self.syllabus:
            return

        # Get learner's interests for content prioritization
        learner_data = self.learner.to_dict()
        interests = learner_data.get("personal_info", {}).get("interests", [])

        print("\n📚 Auto-fetching educational content for modules...")
        print("=" * 60)
        if interests:
            print(f"🎯 Learner interests: {', '.join(interests)}")

        for module in self.syllabus["modules"]:
            module_id = module.get("id")
            if not module_id:
                continue

            print(f"\n📖 Module: {module.get('title')} ({module_id})")

            # Fetch content for this module from multiple OER sources
            created_files = auto_fetch_module_content(
                module=module,
                module_id=module_id,
                output_dir=self.persist_dir / "documents",  # data/documents
                use_wikipedia=True,
                use_arxiv=True,  # Fetch research papers
                use_youtube=False,  # Disabled (requires transcript availability)
                use_synthetic=True,  # Fallback to synthetic if no OER content
                learner_interests=interests,  # Pass interests for prioritization
            )

            if created_files:
                print(f"   ✅ Created {len(created_files)} document(s)")
            else:
                print(f"   ⚠️  No content created (may need manual documents)")

        print("\n" + "=" * 60)
        print("✅ Content fetching complete!\n")

    def get_learner_summary(self) -> Dict[str, Any]:
        """Get comprehensive learner summary."""
        learner_data = self.learner.to_dict()
        mastery_summary = self.learner.get_mastery_summary()

        analytics = learner_data["performance_analytics"]
        progress = learner_data["progress"]

        # Build mastery levels dict from module_progress
        mastery_levels = {
            module_id: prog.get("best_score", 0.0)
            for module_id, prog in progress["module_progress"].items()
        }

        return {
            "learner_id": self.learner.learner_id,
            "name": self.learner.name,
            "current_module": self.current_module_id,
            "overall_gpa": analytics.get("average_score", 0.0),
            "overall_mastery_level": self.learner.overall_mastery_level,
            "mastery_levels": mastery_levels,
            "mastery_summary": mastery_summary,  # Include detailed mastery breakdown
            "strengths": analytics.get("strengths", []),
            "weaknesses": analytics.get("weaknesses", []),
            "performance_trend": analytics.get("performance_trend", "stable"),
            "recommended_difficulty": self.learner.recommended_difficulty,
            "total_assessments": len(analytics.get("assessment_history", [])),
            "study_time_hours": progress.get("total_study_time_minutes", 0) / 60.0,
            "session_count": len(self.session_history),
        }
