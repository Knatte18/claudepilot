"""
orchestrator.py — Main event loop for the ccpilot service.

The Orchestrator runs a supervisor loop that watches for new/deleted/renamed
conversation tabs and manages a pool of TabWorker threads. Each TabWorker
independently polls its own tab and runs its own Claude Code subprocess,
so multiple conversations proceed in parallel without blocking each other.

Also provides load_config() and build_orchestrator_from_config() helpers for
constructing a fully wired Orchestrator from a YAML config file, and exposes
a __main__ entry-point for running the service directly.
"""
from __future__ import annotations

import logging
import threading
import time

import yaml

from src.cc_bridge import ClaudeCodeBridge
from src.models import Message
from src.sheets_transport import SheetsTransport
from src.transport import Transport

logger = logging.getLogger(__name__)

_SUPERVISOR_INTERVAL = 10  # seconds between tab-list checks


class TabWorker:
    """Worker that independently polls and processes a single conversation tab.

    Each worker runs in its own thread, calls transport.poll_tab() in a loop,
    and dispatches any found prompts to the Claude Code bridge. The stop_event
    is set by the Orchestrator when the tab is deleted or renamed.
    """

    def __init__(
        self,
        tab_name: str,
        transport: Transport,
        bridge: ClaudeCodeBridge,
        stop_event: threading.Event,
        poll_fast_seconds: int = 2,
        poll_slow_seconds: int = 30,
        idle_threshold_seconds: int = 120,
    ) -> None:
        self._tab_name = tab_name
        self._transport = transport
        self._bridge = bridge
        self._stop_event = stop_event
        self._poll_fast = poll_fast_seconds
        self._poll_slow = poll_slow_seconds
        self._idle_threshold = idle_threshold_seconds
        self._last_activity = time.monotonic()

    def run(self) -> None:
        logger.info("TabWorker started for [%s]", self._tab_name)
        try:
            self._transport.initialize_tab_if_needed(self._tab_name)
        except Exception as exc:
            logger.warning("Failed to initialize tab [%s]: %s", self._tab_name, exc)

        while not self._stop_event.is_set():
            try:
                message = self._transport.poll_tab(self._tab_name)
                self._transport.write_heartbeat(self._tab_name)
                if message is not None:
                    self._handle_message(message)
                    self._last_activity = time.monotonic()
            except Exception as exc:
                logger.exception("Error in TabWorker [%s]: %s", self._tab_name, exc)

            idle = time.monotonic() - self._last_activity
            interval = self._poll_fast if idle < self._idle_threshold else self._poll_slow
            for _ in range(interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        logger.info("TabWorker stopped for [%s]", self._tab_name)

    def _handle_message(self, message: Message) -> None:
        combined_prompt = (
            f"{message.command} {message.text}".strip()
            if message.command
            else message.text
        )

        if combined_prompt.startswith("!!reload"):
            command_count = self._transport.reload_commands()
            self._transport.report_info(
                self._tab_name,
                f"Commands reloaded from _config ({command_count} entries).",
            )
            return

        response = self._bridge.send(combined_prompt, session_id=message.session_id)

        if response.is_error and "No conversation found with session ID" in (response.error or ""):
            logger.warning(
                "Session not found in [%s], spawning new session with history replay.",
                self._tab_name,
            )
            self._transport.clear_session_id(self._tab_name)

            history = self._transport.get_conversation_history(self._tab_name)
            # Drop the last user entry — that's the prompt we're about to send.
            if history and history[-1][0] == "user":
                history = history[:-1]

            context_lines = []
            if history:
                context_lines.append(
                    "This conversation was started on another machine. "
                    "Here is the prior conversation history for context:\n"
                )
                for role, text in history:
                    label = "User" if role == "user" else "Assistant"
                    context_lines.append(f"[{label}]: {text}\n")
                context_lines.append(
                    "---\nThe conversation continues. Respond to the following new prompt:\n"
                )

            replay_prompt = "".join(context_lines) + combined_prompt
            response = self._bridge.send(replay_prompt, session_id=None)

            if response.is_error:
                logger.error(
                    "CC error in [%s] after session respawn: %s",
                    self._tab_name, response.error,
                )
                self._transport.report_error(self._tab_name, response.error or "unknown error")
            else:
                self._transport.report_info(
                    self._tab_name,
                    "Session not found on this machine — new session spawned with conversation history.",
                )
                self._transport.respond(
                    self._tab_name,
                    response.text,
                    response.session_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
                logger.info(
                    "Responded in [%s] after session respawn (tokens in=%d out=%d)",
                    self._tab_name,
                    response.input_tokens,
                    response.output_tokens,
                )
        elif response.is_error:
            logger.error("CC error in [%s]: %s", self._tab_name, response.error)
            self._transport.report_error(self._tab_name, response.error or "unknown error")
        else:
            self._transport.respond(
                self._tab_name,
                response.text,
                response.session_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            logger.info(
                "Responded in [%s] (tokens in=%d out=%d)",
                self._tab_name,
                response.input_tokens,
                response.output_tokens,
            )


class Orchestrator:
    """Supervisor loop: watches for tab changes and manages a TabWorker per tab."""

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
        self._poll_fast = poll_fast_seconds
        self._poll_slow = poll_slow_seconds
        self._idle_threshold = idle_threshold_seconds
        # Maps tab_name -> (worker, thread, stop_event)
        self._workers: dict[str, tuple[TabWorker, threading.Thread, threading.Event]] = {}

    def run(self) -> None:
        """Start the supervisor loop. Runs until interrupted."""
        logger.info("Orchestrator started (multithreaded, one worker per tab).")
        try:
            while True:
                try:
                    self._sync_workers()
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    logger.exception("Error in supervisor loop: %s", exc)
                for _ in range(_SUPERVISOR_INTERVAL):
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down — stopping all workers.")
            for _, (_, _, stop_event) in self._workers.items():
                stop_event.set()
            for tab_name, (_, thread, _) in self._workers.items():
                thread.join(timeout=10)
                if thread.is_alive():
                    logger.warning("Worker for [%s] did not stop in time.", tab_name)
            logger.info("All workers stopped.")

    def _sync_workers(self) -> None:
        """Reconcile the worker pool with the current set of conversation tabs."""
        try:
            current_tabs = set(self._transport.list_conversations())
        except Exception as exc:
            logger.warning("Failed to list conversations: %s", exc)
            return

        existing_tabs = set(self._workers.keys())

        # Start workers for new tabs.
        for tab_name in current_tabs - existing_tabs:
            stop_event = threading.Event()
            worker = TabWorker(
                tab_name, self._transport, self._bridge, stop_event,
                poll_fast_seconds=self._poll_fast,
                poll_slow_seconds=self._poll_slow,
                idle_threshold_seconds=self._idle_threshold,
            )
            thread = threading.Thread(
                target=worker.run, name=f"tab-{tab_name}", daemon=True
            )
            self._workers[tab_name] = (worker, thread, stop_event)
            thread.start()
            logger.info("Started worker for new tab [%s]", tab_name)

        # Stop workers for deleted/renamed tabs.
        for tab_name in existing_tabs - current_tabs:
            _, _, stop_event = self._workers.pop(tab_name)
            stop_event.set()
            logger.info("Stopping worker for removed tab [%s]", tab_name)


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
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config/config.yaml"
    orchestrator = build_orchestrator_from_config(config_file)
    orchestrator.run()
