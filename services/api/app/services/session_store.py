"""
In-memory session state store for OCR extraction sessions.
Maintains transient server-side extraction state to record candidate values,
track user corrections, and enforce stateful confirmation integrity.

DEPLOYMENT BEHAVIOR & ARCHITECTURAL ASSUMPTIONS:
1. Process-Local & Volatile:
   ExtractionSessionStore is strictly in-memory within the active server process.
2. Deployment Constraint (MVP):
   Requires single-process execution (e.g. uvicorn with 1 worker) or sticky-session routing
   at the load balancer / reverse proxy layer.
3. Fail-Closed Resilience:
   If an instance restarts or a confirmation request routes to a worker lacking the session,
   the server MUST fail closed (HTTP 404/410). It MUST NEVER silently fall back to issuing a
   confirmation token without authenticating active server-side session state.
4. Production Scaling Roadmap:
   For distributed multi-instance horizontal scaling without sticky sessions, this in-memory
   store should be replaced by a shared TTL key-value backend (such as Redis or Memcached).
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractionSession:
    """
    Represents an active server-side OCR extraction session.
    """

    extraction_id: str
    created_at: float
    raw_text: str
    candidates: dict[str, Any] = field(default_factory=dict)
    is_confirmed: bool = False
    confirmed_digest: str | None = None
    confirmed_values: dict[str, Any] | None = None
    user_modified: bool = False
    modified_fields: list[str] = field(default_factory=list)


class ExtractionSessionStore:
    """
    Thread-safe, bounded, in-memory store for active OCR extraction sessions with TTL eviction.
    """

    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 2000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, ExtractionSession] = {}
        self._lock = threading.Lock()

    def _prune_expired_locked(self, now: float) -> None:
        """Removes expired sessions and ensures session capacity does not exceed limit."""
        expired_ids = [
            sid for sid, s in self._sessions.items() if (now - s.created_at) > self.ttl_seconds
        ]
        for sid in expired_ids:
            self._sessions.pop(sid, None)

        if len(self._sessions) > self.max_sessions:
            # Evict oldest sessions
            sorted_sessions = sorted(self._sessions.values(), key=lambda s: s.created_at)
            excess = len(self._sessions) - self.max_sessions
            for s in sorted_sessions[:excess]:
                self._sessions.pop(s.extraction_id, None)

    def save_session(
        self,
        extraction_id: str,
        raw_text: str,
        candidates: dict[str, Any],
        created_at: float | None = None,
    ) -> ExtractionSession:
        """
        Registers a new extraction session with extracted OCR candidates.
        """
        now = created_at if created_at is not None else time.time()
        with self._lock:
            self._prune_expired_locked(now)
            session = ExtractionSession(
                extraction_id=extraction_id,
                created_at=now,
                raw_text=raw_text,
                candidates=candidates,
            )
            self._sessions[extraction_id] = session
            return session

    def get_session(
        self, extraction_id: str, current_time: float | None = None
    ) -> ExtractionSession | None:
        """
        Retrieves an active session by extraction_id if not expired.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            if (now - session.created_at) > self.ttl_seconds:
                self._sessions.pop(extraction_id, None)
                return None
            return session

    def confirm_session(
        self,
        extraction_id: str,
        confirmed_digest: str,
        confirmed_values: dict[str, Any],
        current_time: float | None = None,
    ) -> tuple[bool, str, ExtractionSession | None]:
        """
        Records user confirmation in the session state.
        Computes differences between original OCR candidate values and confirmed values
        to transparently track user edits and corrections.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False, f"Session '{extraction_id}' not found in active session store.", None
            if (now - session.created_at) > self.ttl_seconds:
                self._sessions.pop(extraction_id, None)
                return False, f"Session '{extraction_id}' has expired.", None

            # Compare confirmed values against candidates
            modified_fields: list[str] = []
            for field_name, submitted_val in confirmed_values.items():
                orig_cand = session.candidates.get(field_name)
                orig_val = getattr(orig_cand, "value", None) if orig_cand is not None else None
                # Check for numerical difference
                if orig_val is None and submitted_val is not None:
                    modified_fields.append(field_name)
                elif orig_val is not None and submitted_val is None:
                    modified_fields.append(field_name)
                elif orig_val is not None and submitted_val is not None:
                    if abs(float(orig_val) - float(submitted_val)) > 1e-4:
                        modified_fields.append(field_name)

            session.is_confirmed = True
            session.confirmed_digest = confirmed_digest
            session.confirmed_values = confirmed_values
            session.user_modified = len(modified_fields) > 0
            session.modified_fields = modified_fields

            return True, "", session

    def clear(self) -> None:
        """Clears all sessions (used for test isolation)."""
        with self._lock:
            self._sessions.clear()


# Default singleton session store instance
session_store = ExtractionSessionStore()
