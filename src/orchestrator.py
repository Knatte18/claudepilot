"""
orchestrator.py — Main event loop for the ccpilot service.

The Orchestrator polls a Transport for unanswered user prompts, forwards each
prompt to ClaudeCodeBridge, and writes the response (or error) back through the
same transport. It adapts its polling interval based on recent activity to
reduce API quota usage during idle periods.

Also provides load_config() and build_orchestrator_from_config() helpers for
constructing a fully wired Orchestrator from a YAML config file, and exposes
a __main__ entry-point for running the service directly.
"""
from __future__ import annotations

import logging
import time

import yaml

from src.cc_bridge import ClaudeCodeBridge
from src.sheets_transport import SheetsTransport
from src.transport import Transport

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main loop: poll transport for unanswered prompts, dispatch to CC, write back."""

    def __init__(
        self,
        transport: Transport,
        bridge: ClaudeCodeBridge,
        poll_fast_seconds: int = 2,
        poll_slow_seconds: int = 30,
        idle_threshold_seconds: int = 120,
    ) -> None:
        self._transport = transport
        self._bridge = bridge
        self._poll_fast_seconds = poll_fast_seconds
        self._poll_slow_seconds = poll_slow_seconds
        self._idle_threshold_seconds = idle_threshold_seconds
        self._last_activity_time = time.monotonic()

    def run(self) -> None:
        """Start the polling loop. Runs until interrupted."""
        logger.info(
            "Orchestrator started. Polling %ds (active) / %ds (idle).",
            self._poll_fast_seconds,
            self._poll_slow_seconds,
        )
        try:
            while True:
                try:
                    had_activity = self._tick()
                    if had_activity:
                        self._last_activity_time = time.monotonic()
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    logger.exception("Unhandled error in poll loop: %s", exc)
                idle_seconds = time.monotonic() - self._last_activity_time
                interval = self._poll_fast_seconds if idle_seconds < self._idle_threshold_seconds else self._poll_slow_seconds
                # Sleep in 1-second chunks so Ctrl+C is responsive on Windows.
                for _ in range(interval):
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down.")

    def _tick(self) -> bool:
        """Run one poll cycle. Returns True if a prompt was processed."""
        self._transport.update_status({"state": "polling"})

        message = self._transport.poll()
        if message is None:
            return False

        logger.info("Processing prompt in [%s]", message.conversation_name)
        self._transport.update_status({"state": "processing", "conversation": message.conversation_name})

        response = self._bridge.send(message.text, session_id=message.session_id)

        if response.is_error:
            logger.error("CC error in [%s]: %s", message.conversation_name, response.error)
            self._transport.report_error(message.conversation_name, response.error or "unknown error")
        else:
            self._transport.respond(
                message.conversation_name,
                response.text,
                response.session_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            logger.info(
                "Responded in [%s] (tokens in=%d out=%d)",
                message.conversation_name,
                response.input_tokens,
                response.output_tokens,
            )
        return True


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle)


def build_orchestrator_from_config(config_path: str) -> Orchestrator:
    """Construct a fully wired Orchestrator from a YAML config file."""
    config = load_config(config_path)

    sheets_config = config["google_sheets"]
    transport = SheetsTransport(
        service_account_key_file=sheets_config["service_account_key_file"],
        spreadsheet_id=sheets_config["spreadsheet_id"],
        status_tab=sheets_config.get("status_tab", "status"),
    )

    cc_config = config.get("claude_code", {})
    bridge = ClaudeCodeBridge(
        permission_mode=cc_config.get("permission_mode", "bypassPermissions"),
        executable=cc_config.get("executable", "claude"),
    )

    return Orchestrator(
        transport=transport,
        bridge=bridge,
        poll_fast_seconds=cc_config.get("poll_fast_seconds", 2),
        poll_slow_seconds=cc_config.get("poll_slow_seconds", 30),
        idle_threshold_seconds=cc_config.get("idle_threshold_seconds", 120),
    )


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    orchestrator = build_orchestrator_from_config(config_file)
    orchestrator.run()
