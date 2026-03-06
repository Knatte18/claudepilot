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

    def __init__(self, transport: Transport, bridge: ClaudeCodeBridge, polling_interval_seconds: int = 10) -> None:
        self._transport = transport
        self._bridge = bridge
        self._polling_interval_seconds = polling_interval_seconds

    def run(self) -> None:
        """Start the polling loop. Runs until interrupted."""
        logger.info("Orchestrator started. Polling every %ds.", self._polling_interval_seconds)
        while True:
            try:
                self._tick()
            except KeyboardInterrupt:
                logger.info("Shutting down.")
                break
            except Exception as exc:
                logger.exception("Unhandled error in poll loop: %s", exc)
            time.sleep(self._polling_interval_seconds)

    def _tick(self) -> None:
        self._transport.update_status({"state": "polling"})

        message = self._transport.poll()
        if message is None:
            return

        logger.info("Processing prompt in [%s]", message.conversation_name)
        self._transport.update_status({"state": "processing", "conversation": message.conversation_name})

        response = self._bridge.send(message.text, session_id=message.session_id)

        if response.is_error:
            logger.error("CC error in [%s]: %s", message.conversation_name, response.error)
            self._transport.report_error(message.conversation_name, response.error or "unknown error")
        else:
            self._transport.respond(message.conversation_name, response.text, response.session_id)
            logger.info(
                "Responded in [%s] (tokens in=%d out=%d)",
                message.conversation_name,
                response.input_tokens,
                response.output_tokens,
            )


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
    polling_interval = cc_config.get("polling_interval_seconds", 10)

    return Orchestrator(transport=transport, bridge=bridge, polling_interval_seconds=polling_interval)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    orchestrator = build_orchestrator_from_config(config_file)
    orchestrator.run()
