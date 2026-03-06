from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from src.models import Message
from src.transport import Transport

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_STATUS_TAB = "status"

# Conversation tab layout:
#   Row 1: "session_id=" or "session_id=<id>"
#   Row 2: header row (role | text | timestamp)
#   Row 3+: data rows

_ROW_SESSION = 1
_ROW_HEADER = 2
_ROW_DATA_START = 3

_COL_ROLE = 1
_COL_TEXT = 2
_COL_TIMESTAMP = 3


class SheetsTransport(Transport):
    """Transport backed by a Google Spreadsheet, one tab per conversation.

    Creating a new tab starts a new conversation. The user writes rows with
    role="user". The watcher appends rows with role="assistant". The CC
    session_id is stored in cell A1 of each tab.
    """

    def __init__(
        self,
        service_account_key_file: str,
        spreadsheet_id: str,
        status_tab: str = _STATUS_TAB,
    ) -> None:
        credentials = Credentials.from_service_account_file(
            service_account_key_file, scopes=_SCOPES
        )
        client = gspread.authorize(credentials)
        self._spreadsheet = client.open_by_key(spreadsheet_id)
        self._status_tab_name = status_tab

    def poll(self) -> Optional[Message]:
        """Scan all conversation tabs for an unanswered user prompt."""
        for worksheet in self._spreadsheet.worksheets():
            if worksheet.title == self._status_tab_name:
                continue

            all_values = worksheet.get_all_values()
            if len(all_values) < _ROW_DATA_START:
                continue

            last_row = all_values[-1]
            role = last_row[_COL_ROLE - 1].strip().lower() if len(last_row) >= _COL_ROLE else ""
            if role != "user":
                continue

            text = last_row[_COL_TEXT - 1].strip() if len(last_row) >= _COL_TEXT else ""
            if not text:
                continue

            session_id = self._read_session_id(all_values)
            return Message(
                conversation_name=worksheet.title,
                text=text,
                session_id=session_id,
            )

        return None

    def respond(self, conversation_name: str, text: str, session_id: str) -> None:
        """Append the assistant response and store the session_id."""
        worksheet = self._spreadsheet.worksheet(conversation_name)
        timestamp = datetime.now(timezone.utc).isoformat()
        worksheet.append_row(["assistant", text, timestamp])
        self._write_session_id(worksheet, session_id)

    def report_error(self, conversation_name: str, error_text: str) -> None:
        """Append an error row to the conversation."""
        worksheet = self._spreadsheet.worksheet(conversation_name)
        timestamp = datetime.now(timezone.utc).isoformat()
        worksheet.append_row(["error", error_text, timestamp])

    def update_status(self, status: dict) -> None:
        """Overwrite the status tab with a heartbeat."""
        try:
            status_worksheet = self._spreadsheet.worksheet(self._status_tab_name)
        except gspread.WorksheetNotFound:
            status_worksheet = self._spreadsheet.add_worksheet(
                title=self._status_tab_name, rows=1, cols=10
            )
        timestamp = datetime.now(timezone.utc).isoformat()
        row_values = [timestamp] + [f"{k}={v}" for k, v in status.items()]
        status_worksheet.update("A1", [row_values])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_session_id(self, all_values: list[list[str]]) -> Optional[str]:
        if not all_values:
            return None
        header = all_values[_ROW_SESSION - 1]
        if not header:
            return None
        cell_value = header[0].strip()
        if cell_value.startswith("session_id="):
            session_value = cell_value[len("session_id="):]
            return session_value if session_value else None
        return None

    def _write_session_id(self, worksheet: gspread.Worksheet, session_id: str) -> None:
        worksheet.update_cell(_ROW_SESSION, 1, f"session_id={session_id}")
