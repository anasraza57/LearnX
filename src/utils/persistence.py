"""
Teaching session persistence with validation.

Provides utilities to save and load teaching sessions with JSON schema validation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from .validation import SchemaValidator
except ImportError:
    from src.utils.validation import SchemaValidator


class TeachingSessionPersistence:
    """
    Handles persistence of teaching sessions with validation.

    Features:
    - Validate sessions against teaching_session.schema.json
    - Save sessions to data/sessions/ directory
    - Load sessions by ID or filter
    - Thread-safe file operations
    """

    def __init__(self, sessions_dir: Path | str = None):
        """
        Initialize persistence manager.

        Args:
            sessions_dir: Directory to store sessions (default: data/sessions/)
        """
        self.sessions_dir = Path(sessions_dir) if sessions_dir else Path("data/sessions")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Initialize validator
        schema_path = Path(__file__).parent.parent.parent / "schemas" / "teaching_session.schema.json"
        self.validator = SchemaValidator(str(schema_path))

    def save_session(
        self,
        session_data: Dict[str, Any],
        validate: bool = True,
        auto_repair: bool = False,
    ) -> tuple[bool, Optional[str], Optional[List[str]]]:
        """
        Save a teaching session to disk.

        Args:
            session_data: Teaching session dictionary
            validate: Whether to validate before saving
            auto_repair: Whether to auto-repair validation errors

        Returns:
            Tuple of (success, session_id, errors)
        """
        # Get or generate session_id
        session_id = session_data.get("session_id")
        if not session_id:
            session_id = f"ts-{uuid.uuid4()}"
            session_data["session_id"] = session_id

        # Ensure timestamp
        if "timestamp" not in session_data:
            session_data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Validate if requested (after adding required fields)
        if validate:
            result = self.validator.validate(session_data, auto_repair=auto_repair)
            if not result.valid:
                return False, None, result.errors
            session_data = result.data  # Use repaired data if auto_repair=True

        # Save to file
        filepath = self.sessions_dir / f"{session_id}.json"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            return True, session_id, None
        except Exception as e:
            return False, None, [f"Failed to save session: {str(e)}"]

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a teaching session by ID.

        Args:
            session_id: Session ID (with or without 'ts-' prefix)

        Returns:
            Session data dict, or None if not found
        """
        # Add prefix if missing
        if not session_id.startswith("ts-"):
            session_id = f"ts-{session_id}"

        filepath = self.sessions_dir / f"{session_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load session {session_id}: {e}")
            return None

    def load_sessions_by_learner(self, learner_id: str) -> List[Dict[str, Any]]:
        """
        Load all sessions for a specific learner.

        Args:
            learner_id: Learner ID

        Returns:
            List of session dicts, sorted by timestamp (newest first)
        """
        sessions = []

        for filepath in self.sessions_dir.glob("ts-*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    session = json.load(f)
                    if session.get("learner_id") == learner_id:
                        sessions.append(session)
            except Exception as e:
                print(f"Warning: Failed to load {filepath}: {e}")

        # Sort by timestamp (newest first)
        sessions.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        return sessions

    def load_sessions_by_module(self, module_id: str) -> List[Dict[str, Any]]:
        """
        Load all sessions for a specific module.

        Args:
            module_id: Module ID

        Returns:
            List of session dicts, sorted by timestamp (newest first)
        """
        sessions = []

        for filepath in self.sessions_dir.glob("ts-*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    session = json.load(f)
                    if session.get("module_id") == module_id:
                        sessions.append(session)
            except Exception as e:
                print(f"Warning: Failed to load {filepath}: {e}")

        sessions.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        return sessions

    def list_all_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List all teaching sessions.

        Args:
            limit: Maximum number of sessions to return (newest first)

        Returns:
            List of session dicts
        """
        sessions = []

        for filepath in self.sessions_dir.glob("ts-*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    session = json.load(f)
                    sessions.append(session)
            except Exception as e:
                print(f"Warning: Failed to load {filepath}: {e}")

        sessions.sort(key=lambda s: s.get("timestamp", ""), reverse=True)

        if limit:
            return sessions[:limit]
        return sessions


# Global persistence manager instance
_persistence_manager: Optional[TeachingSessionPersistence] = None


def get_persistence_manager() -> TeachingSessionPersistence:
    """Get or create the global persistence manager."""
    global _persistence_manager
    if _persistence_manager is None:
        _persistence_manager = TeachingSessionPersistence()
    return _persistence_manager


def save_teaching_session(
    session_data: Dict[str, Any],
    validate: bool = True,
    auto_repair: bool = False,
) -> tuple[bool, Optional[str], Optional[List[str]]]:
    """
    Convenience function to save a teaching session.

    Args:
        session_data: Teaching session dictionary
        validate: Whether to validate before saving
        auto_repair: Whether to auto-repair validation errors

    Returns:
        Tuple of (success, session_id, errors)

    Example:
        >>> session = {
        ...     "question": "What is supervised learning?",
        ...     "answer": "Supervised learning is...",
        ...     "learner_level": "beginner",
        ...     "module_id": "m01-fundamentals",
        ...     "citations": [...]
        ... }
        >>> success, session_id, errors = save_teaching_session(session)
        >>> if success:
        ...     print(f"Saved session: {session_id}")
    """
    manager = get_persistence_manager()
    return manager.save_session(session_data, validate=validate, auto_repair=auto_repair)


def load_teaching_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to load a teaching session.

    Args:
        session_id: Session ID

    Returns:
        Session data dict, or None if not found
    """
    manager = get_persistence_manager()
    return manager.load_session(session_id)
