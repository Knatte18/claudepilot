from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.models import Message


class Transport(ABC):
    """Abstract communication layer between the user and the orchestrator.

    Each conversation is identified by name. The transport is responsible for
    storing the CC session_id so conversations can be resumed.
    """

    @abstractmethod
    def poll(self) -> Optional[Message]:
        """Return the next unanswered user prompt, or None."""

    @abstractmethod
    def respond(self, conversation_name: str, text: str, session_id: str) -> None:
        """Append the assistant response and persist the session_id."""

    @abstractmethod
    def report_error(self, conversation_name: str, error_text: str) -> None:
        """Append an error message to the conversation."""

    @abstractmethod
    def update_status(self, status: dict) -> None:
        """Publish a status/heartbeat dictionary."""
