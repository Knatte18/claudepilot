"""
models.py — Shared data classes used across the ccpilot service.

Defines Message (a user prompt read from a transport) and Response (the result
returned by the Claude Code bridge after processing a prompt).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """A user prompt discovered in a conversation tab."""

    conversation_name: str
    text: str
    session_id: Optional[str]


@dataclass
class Response:
    """The result of sending a Message to Claude Code."""

    text: str
    session_id: str
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def is_error(self) -> bool:
        return self.error is not None
