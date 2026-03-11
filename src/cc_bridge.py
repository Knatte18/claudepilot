"""
cc_bridge.py — Subprocess bridge to the Claude Code CLI.

ClaudeCodeBridge wraps the `claude` CLI, invoking it as a short-lived
subprocess with --output-format json. It handles Windows .cmd shim resolution,
session resumption via --resume, timeout enforcement, and parsing of the JSON
envelope returned by Claude Code into a Response dataclass.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Optional

from src.models import Response

logger = logging.getLogger(__name__)


class ClaudeCodeBridge:
    """Invokes the Claude Code CLI as a subprocess and parses the result.

    Each call is a short-lived process.  Pass a session_id from a previous
    Response to continue an existing conversation (--resume).
    """

    def __init__(
        self,
        permission_mode: str = "bypassPermissions",
        executable: str = "claude",
        timeout_seconds: int = 300,
    ) -> None:
        self._permission_mode = permission_mode
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def send(self, prompt: str, session_id: Optional[str] = None) -> Response:
        """Send a prompt to Claude Code and return the parsed Response."""
        command = self._build_command(prompt, session_id)
        logger.debug("Invoking CC: %s", command)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            logger.error("CC subprocess timed out after %ds", self._timeout_seconds)
            return Response(
                text="",
                session_id=session_id or "",
                error=f"Claude Code timed out after {self._timeout_seconds}s",
            )

        if result.returncode != 0:
            error_text = result.stderr.strip() or f"exit code {result.returncode}"
            logger.error("CC subprocess failed: %s", error_text)
            return Response(text="", session_id=session_id or "", error=error_text)

        return self._parse_output(result.stdout, session_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_command(self, prompt: str, session_id: Optional[str]) -> list[str]:
        command = [self._executable]
        command.extend([
            "--print",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            self._permission_mode,
        ])
        if session_id:
            command.extend(["--resume", session_id])
        return command

    def _parse_output(self, raw_output: str, fallback_session_id: Optional[str]) -> Response:
        raw_output = raw_output.strip()
        if not raw_output:
            return Response(
                text="",
                session_id=fallback_session_id or "",
                error="Empty output from Claude Code",
            )

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse CC JSON output: %s", exc)
            return Response(
                text="",
                session_id=fallback_session_id or "",
                error=f"Malformed JSON from Claude Code: {exc}",
            )

        # Extract the assistant text from the message stream.
        assistant_text = self._extract_assistant_text(data)
        new_session_id = data.get("session_id") or fallback_session_id or ""

        usage = data.get("usage", {})
        return Response(
            text=assistant_text,
            session_id=new_session_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    def _extract_assistant_text(self, data: dict) -> str:
        """Pull the assistant's reply text out of the CC JSON envelope."""
        # CC --output-format json returns a top-level "result" or "messages" field.
        if "result" in data:
            return str(data["result"])

        messages = data.get("messages", [])
        parts: list[str] = []
        for message in messages:
            if message.get("role") != "assistant":
                continue
            content = message.get("content", [])
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
        return "\n".join(parts)
