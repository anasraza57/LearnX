"""
Learner Model: Profile management, progress tracking, and adaptive learning.

This module provides comprehensive learner modeling capabilities:
- Profile creation and management
- Progress tracking with mastery levels
- Adaptive difficulty adjustment based on performance
- Performance analytics and trend analysis
- Thread-safe profile persistence
"""

from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from jsonschema import ValidationError

try:
    from ..config import config
    from ..utils.validation import LearnerProfileValidator
except ImportError:
    # Fallback for testing or standalone use
    from src.config import config
    from src.utils.validation import LearnerProfileValidator


# Type aliases for clarity
LearningStyle = Literal["visual", "auditory", "reading_writing", "kinesthetic"]
Pace = Literal["slow", "moderate", "fast", "self_paced"]
MasteryLevel = Literal["novice", "beginner", "intermediate", "advanced", "expert"]
DifficultyLevel = Literal["very_easy", "easy", "medium", "hard", "very_hard"]
ModuleStatus = Literal["not_started", "in_progress", "completed", "mastered"]
PerformanceTrend = Literal["declining", "stable", "improving"]


class LearnerModel:
    """
    Comprehensive learner profile with cognitive modeling and progress tracking.

    Thread-safe for concurrent access. All mutations acquire a lock.
    """

    _lock = threading.Lock()
    _validator: Optional[LearnerProfileValidator] = None

    def __init__(
        self,
        learner_id: Optional[str] = None,
        name: str = "Anonymous Learner",
        email: Optional[str] = None,
        learning_style: Optional[list[LearningStyle]] = None,
        pace: Pace = "moderate",
        difficulty_preference: DifficultyLevel = "medium",
        validate: bool = True,
    ):
        """
        Initialize a new learner profile.

        Args:
            learner_id: Unique identifier (auto-generated if None)
            name: Learner's name
            email: Contact email (optional)
            learning_style: VARK preferences (defaults to ["visual"])
            pace: Learning pace preference
            difficulty_preference: Starting difficulty level
            validate: Whether to validate on creation (default: True, set False for testing)
        """
        self._data = self._create_default_profile(
            learner_id or self._generate_id(),
            name,
            email,
            learning_style or ["visual"],
            pace,
            difficulty_preference,
        )
        if validate:
            self._validate()

    @staticmethod
    def _generate_id() -> str:
        """Generate unique learner ID in required format."""
        return f"learner-{uuid.uuid4()}"

    @staticmethod
    def _utc_now() -> str:
        """Get current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _get_validator(cls) -> LearnerProfileValidator:
        """Get cached validator instance."""
        if cls._validator is None:
            cls._validator = LearnerProfileValidator()
        return cls._validator

    def _create_default_profile(
        self,
        learner_id: str,
        name: str,
        email: Optional[str],
        learning_style: list[LearningStyle],
        pace: Pace,
        difficulty_preference: DifficultyLevel,
    ) -> dict:
        """Create a default profile structure."""
        now = self._utc_now()

        profile = {
            "meta": {
                "schema_version": 1,
                "created_at": now,
                "last_updated": now,
            },
            "learner_id": learner_id,
            "personal_info": {
                "name": name,
                "email": email,
                "goals": [],
                "interests": [],
                "prior_knowledge": {},
            },
            "cognitive_profile": {
                "learning_style": learning_style,
                "pace": pace,
            },
            "learning_preferences": {
                "difficulty_preference": difficulty_preference,
                "hints_enabled": True,
                "gamification_enabled": False,
            },
            "progress": {
                "enrolled_syllabus_id": None,
                "current_module_id": None,
                "modules_completed": [],
                "overall_completion_percent": 0.0,
                "module_progress": {},
                "learning_streak_days": 0,
                "total_study_time_minutes": 0,
            },
            "performance_analytics": {
                "overall_mastery_level": "novice",
                "average_score": 0.0,
                "strengths": [],
                "weaknesses": [],
                "recommended_difficulty": difficulty_preference,
                "performance_trend": "stable",
                "assessment_history": [],
            },
        }

        if email:
            profile["personal_info"]["email"] = email

        return profile

    def _validate(self) -> None:
        """
        Validate profile against schema using LearnerProfileValidator.

        Raises:
            ValidationError: If profile is invalid
        """
        validator = self._get_validator()
        result = validator.validate(self._data, auto_repair=False)

        if not result.valid:
            # Raise ValidationError with all error messages
            error_msg = "\n".join(result.errors)
            raise ValidationError(error_msg)

    def _update_timestamp(self) -> None:
        """Update last_updated timestamp."""
        self._data["meta"]["last_updated"] = self._utc_now()

    # ==================== Profile Access ====================

    @property
    def learner_id(self) -> str:
        """Get learner ID."""
        return self._data["learner_id"]

    @property
    def name(self) -> str:
        """Get learner name."""
        return self._data["personal_info"]["name"]

    @property
    def learning_style(self) -> list[LearningStyle]:
        """Get learning style preferences (VARK)."""
        return self._data["cognitive_profile"]["learning_style"]

    @property
    def pace(self) -> Pace:
        """Get learning pace preference."""
        return self._data["cognitive_profile"]["pace"]

    @property
    def difficulty_preference(self) -> DifficultyLevel:
        """Get difficulty preference."""
        return self._data["learning_preferences"]["difficulty_preference"]

    @property
    def recommended_difficulty(self) -> DifficultyLevel:
        """Get adaptive difficulty recommendation based on performance."""
        return self._data["performance_analytics"]["recommended_difficulty"]

    @property
    def overall_mastery_level(self) -> MasteryLevel:
        """Get overall mastery level."""
        return self._data["performance_analytics"]["overall_mastery_level"]

    @property
    def overall_completion_percent(self) -> float:
        """Get overall completion percentage."""
        return self._data["progress"]["overall_completion_percent"]

    # ==================== Personal Info Management ====================

    def add_goal(self, goal: str) -> None:
        """Add a learning goal."""
        with self._lock:
            if goal and goal not in self._data["personal_info"]["goals"]:
                self._data["personal_info"]["goals"].append(goal)
                self._update_timestamp()

    def add_interest(self, interest: str) -> None:
        """Add an interest."""
        with self._lock:
            if interest and interest not in self._data["personal_info"]["interests"]:
                self._data["personal_info"]["interests"].append(interest)
                self._update_timestamp()

    def add_prior_knowledge(self, topic: str, level: str) -> None:
        """Add prior knowledge for a topic."""
        with self._lock:
            if topic and level:
                self._data["personal_info"]["prior_knowledge"][topic] = level
                self._update_timestamp()

    def get_goals(self) -> list[str]:
        """Get list of learning goals."""
        return self._data["personal_info"]["goals"]

    def get_interests(self) -> list[str]:
        """Get list of interests."""
        return self._data["personal_info"]["interests"]

    def get_prior_knowledge(self) -> dict[str, str]:
        """Get prior knowledge dictionary."""
        return self._data["personal_info"]["prior_knowledge"]

    # ==================== Enrollment & Progress ====================

    def enroll_in_syllabus(self, syllabus_id: str, total_modules: int = 1) -> None:
        """
        Enroll learner in a syllabus.

        Args:
            syllabus_id: Unique syllabus identifier
            total_modules: Total number of modules in syllabus
        """
        with self._lock:
            self._data["progress"]["enrolled_syllabus_id"] = syllabus_id
            self._data["progress"]["current_module_id"] = None
            self._data["progress"]["modules_completed"] = []
            self._data["progress"]["overall_completion_percent"] = 0.0
            self._data["progress"]["module_progress"] = {}
            self._update_timestamp()

    def start_module(self, module_id: str) -> None:
        """
        Mark a module as started.

        Args:
            module_id: Module identifier
        """
        with self._lock:
            if module_id not in self._data["progress"]["module_progress"]:
                self._data["progress"]["module_progress"][module_id] = {
                    "status": "in_progress",
                    "mastery_level": "novice",
                    "started_at": self._utc_now(),
                    "time_spent_minutes": 0,
                    "attempts": 0,
                    "best_score": 0.0,
                }
            else:
                self._data["progress"]["module_progress"][module_id]["status"] = "in_progress"

            self._data["progress"]["current_module_id"] = module_id
            self._update_timestamp()

    def complete_module(
        self,
        module_id: str,
        score: float,
        time_spent_minutes: int,
        mastery_level: Optional[MasteryLevel] = None,
    ) -> None:
        """
        Mark a module as completed.

        Args:
            module_id: Module identifier
            score: Final score (0-100)
            time_spent_minutes: Time spent on module
            mastery_level: Mastery level (auto-computed if None)
        """
        with self._lock:
            if module_id not in self._data["progress"]["module_progress"]:
                self.start_module(module_id)

            progress = self._data["progress"]["module_progress"][module_id]
            progress["status"] = "completed"
            progress["completed_at"] = self._utc_now()
            progress["time_spent_minutes"] = time_spent_minutes
            progress["best_score"] = max(progress.get("best_score", 0.0), score)
            progress["mastery_level"] = mastery_level or self._compute_mastery_from_score(score)

            if module_id not in self._data["progress"]["modules_completed"]:
                self._data["progress"]["modules_completed"].append(module_id)

            self._data["progress"]["total_study_time_minutes"] += time_spent_minutes
            self._update_timestamp()
            self._recompute_completion_percent()

    def _compute_mastery_from_score(self, score: float) -> MasteryLevel:
        """
        Compute mastery level from score.

        Score ranges:
        - 0-50: novice
        - 50-65: beginner
        - 65-80: intermediate
        - 80-90: advanced
        - 90-100: expert
        """
        if score < 50:
            return "novice"
        elif score < 65:
            return "beginner"
        elif score < 80:
            return "intermediate"
        elif score < 90:
            return "advanced"
        else:
            return "expert"

    def _recompute_completion_percent(self) -> None:
        """Recompute overall completion percentage."""
        total_modules = len(self._data["progress"]["module_progress"])
        if total_modules == 0:
            self._data["progress"]["overall_completion_percent"] = 0.0
            return

        completed = len(self._data["progress"]["modules_completed"])
        self._data["progress"]["overall_completion_percent"] = round(
            (completed / total_modules) * 100, 2
        )

    # ==================== Assessment & Performance ====================

    def record_assessment(
        self,
        module_id: str,
        score: float,
        difficulty: DifficultyLevel,
        time_taken_minutes: int,
        hints_used: int = 0,
    ) -> None:
        """
        Record an assessment attempt.

        Args:
            module_id: Module identifier
            score: Assessment score (0-100)
            difficulty: Difficulty level
            time_taken_minutes: Time taken
            hints_used: Number of hints used
        """
        with self._lock:
            # Add to assessment history
            assessment = {
                "module_id": module_id,
                "timestamp": self._utc_now(),
                "score": round(score, 2),
                "difficulty": difficulty,
                "time_taken_minutes": time_taken_minutes,
                "hints_used": hints_used,
            }
            self._data["performance_analytics"]["assessment_history"].append(assessment)

            # Update module progress
            if module_id not in self._data["progress"]["module_progress"]:
                self.start_module(module_id)

            progress = self._data["progress"]["module_progress"][module_id]
            progress["attempts"] = progress.get("attempts", 0) + 1
            progress["best_score"] = max(progress.get("best_score", 0.0), score)

            self._update_timestamp()
            self._recompute_performance_analytics()

    def _recompute_performance_analytics(self) -> None:
        """Recompute all performance analytics based on assessment history."""
        history = self._data["performance_analytics"]["assessment_history"]

        if not history:
            return

        # Compute average score
        scores = [a["score"] for a in history]
        avg_score = sum(scores) / len(scores)
        self._data["performance_analytics"]["average_score"] = round(avg_score, 2)

        # Compute overall mastery
        self._data["performance_analytics"]["overall_mastery_level"] = (
            self._compute_mastery_from_score(avg_score)
        )

        # Compute performance trend (last 5 assessments vs previous 5)
        if len(history) >= 10:
            recent_scores = scores[-5:]
            previous_scores = scores[-10:-5]
            recent_avg = sum(recent_scores) / 5
            previous_avg = sum(previous_scores) / 5

            if recent_avg > previous_avg + 5:
                trend = "improving"
            elif recent_avg < previous_avg - 5:
                trend = "declining"
            else:
                trend = "stable"

            self._data["performance_analytics"]["performance_trend"] = trend

        # Adaptive difficulty recommendation
        self._data["performance_analytics"]["recommended_difficulty"] = (
            self._compute_recommended_difficulty()
        )

    def _compute_recommended_difficulty(self) -> DifficultyLevel:
        """
        Compute recommended difficulty based on recent performance.

        Strategy:
        - Recent avg < 50: decrease difficulty
        - Recent avg 50-65: stay at easy/medium
        - Recent avg 65-80: stay at medium
        - Recent avg 80-90: increase to hard
        - Recent avg > 90: increase to very_hard
        """
        history = self._data["performance_analytics"]["assessment_history"]

        if not history:
            return self._data["learning_preferences"]["difficulty_preference"]

        # Use last 3 assessments
        recent = history[-3:]
        avg_score = sum(a["score"] for a in recent) / len(recent)

        if avg_score < 50:
            return "very_easy"
        elif avg_score < 65:
            return "easy"
        elif avg_score < 80:
            return "medium"
        elif avg_score < 90:
            return "hard"
        else:
            return "very_hard"

    def identify_strengths_weaknesses(self, threshold: float = 75.0) -> None:
        """
        Identify strengths and weaknesses from assessment history.

        Args:
            threshold: Score threshold for strength identification (default 75%)
        """
        with self._lock:
            history = self._data["performance_analytics"]["assessment_history"]

            if not history:
                return

            # Group by module
            module_scores: dict[str, list[float]] = {}
            for assessment in history:
                module_id = assessment["module_id"]
                if module_id not in module_scores:
                    module_scores[module_id] = []
                module_scores[module_id].append(assessment["score"])

            strengths = []
            weaknesses = []

            for module_id, scores in module_scores.items():
                avg = sum(scores) / len(scores)
                if avg >= threshold:
                    strengths.append(module_id)
                elif avg < 60:
                    weaknesses.append(module_id)

            self._data["performance_analytics"]["strengths"] = strengths
            self._data["performance_analytics"]["weaknesses"] = weaknesses
            self._update_timestamp()

    # ==================== Persistence ====================

    def to_dict(self) -> dict:
        """Export profile as dictionary (deep copy to prevent mutations)."""
        with self._lock:
            return deepcopy(self._data)

    def save(self, filepath: Optional[Path] = None) -> Path:
        """
        Save profile to JSON file.

        Args:
            filepath: Custom save path (defaults to data/profiles/{learner_id}.json)

        Returns:
            Path where profile was saved
        """
        with self._lock:
            if filepath is None:
                profiles_dir = config.paths.project_root / "data" / "profiles"
                profiles_dir.mkdir(parents=True, exist_ok=True)
                filepath = profiles_dir / f"{self.learner_id}.json"

            self._validate()  # Ensure valid before saving

            with open(filepath, "w") as f:
                json.dump(self._data, f, indent=2)

            return filepath

    @classmethod
    def load(cls, filepath: Path) -> LearnerModel:
        """
        Load profile from JSON file.

        Args:
            filepath: Path to profile JSON

        Returns:
            LearnerModel instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If profile is invalid
        """
        with open(filepath, "r") as f:
            data = json.load(f)

        # Create instance without calling __init__
        instance = cls.__new__(cls)
        instance._data = data
        instance._validate()

        return instance

    @classmethod
    def load_by_id(cls, learner_id: str) -> LearnerModel:
        """
        Load profile by learner ID from default location.

        Args:
            learner_id: Learner identifier

        Returns:
            LearnerModel instance
        """
        profiles_dir = config.paths.project_root / "data" / "profiles"
        filepath = profiles_dir / f"{learner_id}.json"
        return cls.load(filepath)

    # ==================== Recommendations & Analytics ====================

    def weak_modules(self, k: int = 5, threshold: float = 60.0) -> list[str]:
        """
        Get modules with lowest mastery (below threshold).

        Args:
            k: Maximum number of modules to return
            threshold: Mastery threshold (0-100)

        Returns:
            List of module IDs, ordered by mastery (lowest first)
        """
        with self._lock:
            module_progress = self._data["progress"]["module_progress"]

            # Get modules with scores below threshold
            weak = [
                (module_id, progress.get("best_score", 0.0))
                for module_id, progress in module_progress.items()
                if progress.get("best_score", 0.0) < threshold
            ]

            # Sort by score (ascending)
            weak.sort(key=lambda x: x[1])

            return [module_id for module_id, _ in weak[:k]]

    def recommend_next_modules(
        self,
        syllabus_modules: list[dict],
        k: int = 3,
        mastery_threshold: float = 70.0,
    ) -> list[str]:
        """
        Recommend next modules to study based on:
        1. Prerequisites are satisfied (>= mastery_threshold)
        2. Module not yet completed
        3. Lower current mastery first

        Args:
            syllabus_modules: List of module dicts from syllabus
            k: Number of modules to recommend
            mastery_threshold: Score needed to satisfy prerequisite

        Returns:
            List of recommended module IDs
        """
        with self._lock:
            module_progress = self._data["progress"]["module_progress"]
            completed = set(self._data["progress"]["modules_completed"])

            # Determine which modules have satisfied prerequisites
            eligible = []

            for module in syllabus_modules:
                module_id = module.get("id", "")
                if module_id in completed:
                    continue  # Already completed

                # Check prerequisites
                prereqs = module.get("prerequisites", [])
                prereqs_ok = True

                for prereq_id in prereqs:
                    prereq_score = module_progress.get(prereq_id, {}).get("best_score", 0.0)
                    if prereq_score < mastery_threshold:
                        prereqs_ok = False
                        break

                if prereqs_ok:
                    current_score = module_progress.get(module_id, {}).get("best_score", 0.0)
                    eligible.append((module_id, current_score))

            # Sort by current score (ascending - prioritize weak areas)
            eligible.sort(key=lambda x: x[1])

            return [module_id for module_id, _ in eligible[:k]]

    def weekly_load_feasible(
        self,
        syllabus_duration_weeks: int,
        syllabus_total_hours: float,
        buffer: float = 1.1,
    ) -> bool:
        """
        Check if learner's study load is feasible given syllabus requirements.

        Args:
            syllabus_duration_weeks: Duration of syllabus in weeks
            syllabus_total_hours: Total estimated hours for syllabus
            buffer: Allowable buffer (default 1.1 = 110%)

        Returns:
            True if average weekly load is feasible, False otherwise
        """
        if syllabus_duration_weeks <= 0:
            return True

        # Calculate required weekly hours
        required_weekly = syllabus_total_hours / syllabus_duration_weeks

        # Get learner's preferred session length and availability
        prefs = self._data.get("learning_preferences", {})
        session_minutes = prefs.get("preferred_session_length_minutes", 60)
        sessions_per_week = 3  # Assume 3 sessions per week by default

        available_weekly = (session_minutes / 60.0) * sessions_per_week

        # Check if available hours meet requirements (with buffer)
        return available_weekly >= (required_weekly / buffer)

    def get_mastery_summary(self) -> dict:
        """
        Get summary statistics of module mastery.

        Returns:
            Dict with mean, median, min, max, and distribution
        """
        try:
            from ..utils.progress import mastery_summary, mastery_by_category
        except ImportError:
            from src.utils.progress import mastery_summary, mastery_by_category

        with self._lock:
            module_progress = self._data["progress"]["module_progress"]
            mastery_scores = {
                module_id: progress.get("best_score", 0.0)
                for module_id, progress in module_progress.items()
            }

            if not mastery_scores:
                return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "count": 0}

            summary = mastery_summary(mastery_scores)
            categories = mastery_by_category(mastery_scores)

            return {
                **summary,
                "by_level": {k: len(v) for k, v in categories.items()},
            }

    # ==================== Phase 3 Integration ====================

    def add_history_entry(
        self,
        session_id: str,
        question: str,
        answer: str,
        module_id: Optional[str] = None,
        confidence: float = 1.0,
        helpful: Optional[bool] = None,
    ) -> None:
        """
        Add a teaching session to learner's history.

        This enables Phase 2 + Phase 3 integration, tracking which RAG
        sessions the learner participated in.

        Args:
            session_id: Teaching session ID (from Phase 3)
            question: Question asked
            answer: Answer provided (summary)
            module_id: Optional module context
            confidence: RAG confidence score
            helpful: Optional learner feedback on helpfulness
        """
        with self._lock:
            # Initialize history if not exists
            if "history" not in self._data:
                self._data["history"] = []

            # Add history entry
            entry = {
                "session_id": session_id,
                "timestamp": self._utc_now(),
                "question": question,
                "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer,
                "module_id": module_id,
                "confidence": round(confidence, 2),
            }

            if helpful is not None:
                entry["helpful"] = helpful

            self._data["history"].append(entry)

            # Limit history to last 100 entries
            if len(self._data["history"]) > 100:
                self._data["history"] = self._data["history"][-100:]

            self._update_timestamp()

    # ==================== Phase 4 Integration ====================

    def record_quiz_result(
        self,
        quiz_session_id: str,
        module_id: str,
        score: float,
        difficulty: DifficultyLevel,
        num_questions: int,
        time_taken_minutes: int,
        passed: bool,
    ) -> None:
        """
        Record quiz/assessment results (Phase 4 integration).

        This updates the learner's assessment history and triggers
        performance recomputation just like regular assessments.

        Args:
            quiz_session_id: Quiz session ID (from Phase 4)
            module_id: Module assessed
            score: Overall score (0-100)
            difficulty: Quiz difficulty level
            num_questions: Number of questions in quiz
            time_taken_minutes: Total time spent
            passed: Whether learner passed
        """
        # Record as a regular assessment (reuses existing logic)
        self.record_assessment(
            module_id=module_id,
            score=score,
            difficulty=difficulty,
            time_taken_minutes=time_taken_minutes,
            hints_used=0,  # Quiz-level doesn't track individual hints
        )

        # Also store quiz-specific metadata in assessment history
        if self._data["performance_analytics"]["assessment_history"]:
            last_assessment = self._data["performance_analytics"]["assessment_history"][-1]
            last_assessment["quiz_session_id"] = quiz_session_id
            last_assessment["num_questions"] = num_questions
            last_assessment["passed"] = passed

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"LearnerModel(id={self.learner_id}, "
            f"name='{self.name}', "
            f"mastery={self.overall_mastery_level}, "
            f"completion={self.overall_completion_percent:.1f}%)"
        )
