"""
transport.py — Abstract Transport interface for ccpilot.

Defines the Transport ABC that all concrete transports must implement.
A transport is responsible for listing conversation tabs (list_conversations),
polling a single tab for unanswered prompts (poll_tab), initializing tabs
(initialize_tab_if_needed), writing back assistant responses (respond),
and reporting errors (report_error).
"""
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
    def list_conversations(self) -> list[str]:
        """Return the names of all active conversation tabs."""

    @abstractmethod
    def poll_tab(self, conversation_name: str) -> Optional[Message]:
        """Return the next unanswered user prompt from a specific tab, or None."""

    @abstractmethod
    def initialize_tab_if_needed(self, conversation_name: str) -> None:
        """Initialize a tab with labels, input cell, checkbox, and headers if not yet set up."""

    @abstractmethod
    def respond(
        self,
        conversation_name: str,
        text: str,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Append the assistant response and persist the session_id."""

    @abstractmethod
    def report_error(self, conversation_name: str, error_text: str) -> None:
        """Append an error message to the conversation."""

    @abstractmethod
    def report_info(self, conversation_name: str, info_text: str) -> None:
        """Append an informational message to the conversation."""

    @abstractmethod
    def get_conversation_history(self, conversation_name: str) -> list[tuple[str, str]]:
        """Return conversation log as [(role, text), ...] in chronological order."""

    @abstractmethod
    def clear_session_id(self, conversation_name: str) -> None:
        """Remove the session ID from a conversation tab."""

    def write_heartbeat(self, conversation_name: str) -> None:
        """Write a last-polled timestamp to the tab. Default implementation is a no-op."""

    def reload_commands(self) -> int:
        """Reload command list and re-apply to all conversation tabs.

        Returns the number of commands loaded. Default implementation is a no-op.
        """
        return 0
