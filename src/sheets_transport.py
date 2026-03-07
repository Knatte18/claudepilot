"""
sheets_transport.py — Google Sheets-backed Transport implementation.

SheetsTransport implements the Transport interface using a Google Spreadsheet
as the communication channel. Each conversation is a separate tab. Users type
a prompt into cell A2 and tick a checkbox in B2 to submit it; the orchestrator
reads the prompt, logs it as a row, sends it to Claude Code, and inserts the
response above. A dedicated status tab is updated each poll cycle as a
heartbeat. Inactive tabs are polled less frequently to conserve API quota.
"""
from __future__ import annotations

import logging
import time
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
#   Row 1: A1="Prompt:" B1="Send" C1="Context:" D1=<percentage>  H1=session_id
#   Row 2: A2=[user input, yellow bg, thick border]  B2=[send checkbox]
#   Row 3: header row (Text | Role | Status | Timestamp | Tokens) (bold)
#   Row 4+: data rows, newest first (inserted at row 4, pushing older rows down)

_ROW_LABEL = 1
_ROW_INPUT = 2
_ROW_HEADER = 3
_ROW_DATA_START = 4

_COL_TEXT = 1       # A (also the prompt input on _ROW_INPUT)
_COL_ROLE = 2       # B (also the send checkbox on _ROW_INPUT)
_COL_STATUS = 3     # C
_COL_TIMESTAMP = 4  # D
_COL_TOKENS = 5     # E
_COL_SESSION_ID = 8  # H (only on _ROW_LABEL, out of the way)

_COL_CONTEXT_LABEL = 3  # C (on _ROW_LABEL)
_COL_CONTEXT_VALUE = 4  # D (on _ROW_LABEL)

_CONTEXT_WINDOW_TOKENS = 200_000

# Background colors per role (RGB 0-1 scale for Google Sheets API).
_ROLE_COLORS = {
    "claude": {"red": 0.85, "green": 0.93, "blue": 0.83},  # light green
    "error": {"red": 0.96, "green": 0.80, "blue": 0.80},   # light red
    "user": {"red": 0.87, "green": 0.92, "blue": 0.97},    # light blue
    "info": {"red": 1.0, "green": 0.95, "blue": 0.70},     # light amber
}

_INPUT_COLOR = {"red": 1.0, "green": 0.95, "blue": 0.80}  # light yellow


class SheetsTransport(Transport):
    """Transport backed by a Google Spreadsheet, one tab per conversation.

    Each tab has labels on row 1 ("Prompt:", "Send"), an input cell (A2) with
    a send checkbox (B2), and column headers on row 3. The user types a prompt
    in A2 and ticks the checkbox. The orchestrator picks it up, inserts it as
    a log row at the top (row 4), sends it to CC, and inserts the response above.
    Log rows are newest-first (inserted at row 4).
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
        try:
            self._spreadsheet = client.open_by_key(spreadsheet_id)
        except gspread.SpreadsheetNotFound:
            raise RuntimeError(
                f"Spreadsheet {spreadsheet_id} not found. "
                "Check the ID and that the sheet is shared with the service account."
            )
        except gspread.exceptions.APIError as exc:
            raise RuntimeError(f"Cannot access spreadsheet: {exc}") from exc
        self._status_tab_name = status_tab
        tabs = [ws.title for ws in self._spreadsheet.worksheets()]
        logger.info("Connected to spreadsheet. Tabs: %s", tabs)
        self._active_tabs: dict[str, float] = {}
        self._poll_cycle = 0
        self._processing_tabs: set[str] = set()
        self._known_tabs: set[str] = set()

    def poll(self) -> Optional[Message]:
        """Scan conversation tabs for a prompt submitted via checkbox.

        New/empty tabs are auto-initialized with headers and checkbox.
        Active tabs are checked every cycle; inactive tabs every 5th cycle.
        Tabs not yet seen are always checked (for fast new-tab detection).
        """
        self._poll_cycle += 1
        check_inactive = (self._poll_cycle % 5 == 0)

        for worksheet in self._spreadsheet.worksheets():
            if worksheet.title == self._status_tab_name:
                continue

            is_new_tab = worksheet.title not in self._known_tabs
            if not is_new_tab and not self._is_tab_active(worksheet.title) and not check_inactive:
                continue

            try:
                values = worksheet.get("A1:H4")
                self._known_tabs.add(worksheet.title)

                # Auto-initialize new/empty tabs.
                if not values or len(values) < _ROW_HEADER:
                    self._initialize_tab(worksheet)
                    continue

                label_row = values[_ROW_LABEL - 1]
                input_row = values[_ROW_INPUT - 1] if len(values) >= _ROW_INPUT else []
                checkbox_value = (
                    input_row[_COL_ROLE - 1].strip().upper()
                    if len(input_row) >= _COL_ROLE else ""
                )
                prompt_text = (
                    input_row[_COL_TEXT - 1].strip()
                    if len(input_row) >= _COL_TEXT else ""
                )

                if checkbox_value == "TRUE" and prompt_text:
                    session_id = self._read_session_id(label_row)
                    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                    # Clear input first (so user sees immediate feedback).
                    worksheet.update_cell(_ROW_INPUT, _COL_ROLE, False)
                    worksheet.update_cell(_ROW_INPUT, _COL_TEXT, "")

                    # Insert user row at top of log.
                    worksheet.insert_rows(
                        [[prompt_text, "user", "processing", timestamp]],
                        row=_ROW_DATA_START,
                        value_input_option="RAW",
                    )
                    worksheet.format(
                        f"A{_ROW_DATA_START}:E{_ROW_DATA_START}",
                        {"backgroundColor": _ROLE_COLORS["user"]},
                    )

                    self._active_tabs[worksheet.title] = time.monotonic()
                    self._processing_tabs.add(worksheet.title)

                    return Message(
                        conversation_name=worksheet.title,
                        text=prompt_text,
                        session_id=session_id,
                    )

                # Crash recovery: re-process a stuck "processing" user row.
                if (
                    len(values) >= _ROW_DATA_START
                    and worksheet.title not in self._processing_tabs
                ):
                    data_row = values[_ROW_DATA_START - 1]
                    role = (
                        data_row[_COL_ROLE - 1].strip().lower()
                        if len(data_row) >= _COL_ROLE else ""
                    )
                    status = (
                        data_row[_COL_STATUS - 1].strip().lower()
                        if len(data_row) >= _COL_STATUS else ""
                    )
                    text = (
                        data_row[_COL_TEXT - 1].strip()
                        if len(data_row) >= _COL_TEXT else ""
                    )

                    if role == "user" and status == "processing" and text:
                        session_id = self._read_session_id(label_row)
                        logger.warning(
                            "Recovering stuck prompt in [%s]: %s",
                            worksheet.title, text[:80],
                        )
                        self._active_tabs[worksheet.title] = time.monotonic()
                        self._processing_tabs.add(worksheet.title)
                        return Message(
                            conversation_name=worksheet.title,
                            text=text,
                            session_id=session_id,
                        )

            except gspread.exceptions.APIError as exc:
                logger.warning("API error on tab [%s], skipping: %s", worksheet.title, exc)
                continue

        return None

    def respond(
        self,
        conversation_name: str,
        text: str,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Insert the assistant response at the top of the log."""
        worksheet = self._spreadsheet.worksheet(conversation_name)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        tokens_cell = f"{input_tokens} / {output_tokens}" if input_tokens or output_tokens else ""

        # Insert response row at top of log (pushes user row from 4 to 5).
        worksheet.insert_rows(
            [[text, "claude", "done", timestamp, tokens_cell]],
            row=_ROW_DATA_START,
            value_input_option="RAW",
        )
        worksheet.format(
            f"A{_ROW_DATA_START}:E{_ROW_DATA_START}",
            {"backgroundColor": _ROLE_COLORS["claude"]},
        )

        # Mark the user row (now shifted to row 5) as done.
        worksheet.update_cell(_ROW_DATA_START + 1, _COL_STATUS, "done")

        # Update context usage percentage on the label row.
        if input_tokens:
            percentage = min(round(input_tokens / _CONTEXT_WINDOW_TOKENS * 100), 100)
            worksheet.update_cell(_ROW_LABEL, _COL_CONTEXT_VALUE, f"{percentage}%")

        self._write_session_id(worksheet, session_id)
        self._processing_tabs.discard(conversation_name)

    def report_error(self, conversation_name: str, error_text: str) -> None:
        """Insert an error row at the top of the log."""
        worksheet = self._spreadsheet.worksheet(conversation_name)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Insert error row at top of log (pushes user row from 4 to 5).
        worksheet.insert_rows(
            [[error_text, "error", "done", timestamp]],
            row=_ROW_DATA_START,
            value_input_option="RAW",
        )
        worksheet.format(
            f"A{_ROW_DATA_START}:E{_ROW_DATA_START}",
            {"backgroundColor": _ROLE_COLORS["error"]},
        )

        # Mark the user row (now shifted to row 5) as done.
        worksheet.update_cell(_ROW_DATA_START + 1, _COL_STATUS, "done")

        self._processing_tabs.discard(conversation_name)

    def report_info(self, conversation_name: str, info_text: str) -> None:
        """Insert an informational row at the top of the log."""
        worksheet = self._spreadsheet.worksheet(conversation_name)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        worksheet.insert_rows(
            [[info_text, "info", "done", timestamp]],
            row=_ROW_DATA_START,
            value_input_option="RAW",
        )
        worksheet.format(
            f"A{_ROW_DATA_START}:E{_ROW_DATA_START}",
            {"backgroundColor": _ROLE_COLORS["info"]},
        )

    def update_status(self, status: dict) -> None:
        """Overwrite the status tab with a heartbeat."""
        try:
            status_worksheet = self._spreadsheet.worksheet(self._status_tab_name)
        except gspread.WorksheetNotFound:
            status_worksheet = self._spreadsheet.add_worksheet(
                title=self._status_tab_name, rows=1, cols=10
            )
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        row_values = [timestamp] + [f"{k}={v}" for k, v in status.items()]
        status_worksheet.update("A1", [row_values])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _initialize_tab(self, worksheet: gspread.Worksheet) -> None:
        """Set up a new conversation tab with labels, input cell, checkbox, and headers."""
        # Row 1: labels.  Row 3: column headers (capitalized).
        worksheet.update(
            "A1",
            [
                ["Prompt:", "Send", "Context:", ""],
                [],
                ["Text", "Role", "Status", "Timestamp", "Tokens"],
            ],
            value_input_option="RAW",
        )

        # Batch API requests: checkbox validation on B2, thick border around A2.
        thick_border = {
            "style": "SOLID_THICK",
            "colorStyle": {"rgbColor": {"red": 0, "green": 0, "blue": 0}},
        }
        self._spreadsheet.batch_update({
            "requests": [
                # Checkbox data validation on B2.
                {
                    "setDataValidation": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": _ROW_INPUT - 1,
                            "endRowIndex": _ROW_INPUT,
                            "startColumnIndex": _COL_ROLE - 1,
                            "endColumnIndex": _COL_ROLE,
                        },
                        "rule": {
                            "condition": {"type": "BOOLEAN"},
                            "showCustomUi": True,
                        },
                    }
                },
                # Thick border around A2.
                {
                    "updateBorders": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": _ROW_INPUT - 1,
                            "endRowIndex": _ROW_INPUT,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1,
                        },
                        "top": thick_border,
                        "bottom": thick_border,
                        "left": thick_border,
                        "right": thick_border,
                    }
                },
            ],
        })
        worksheet.update_cell(_ROW_INPUT, _COL_ROLE, False)

        # Yellow background for input cell (A2), bold on labels (row 1) and headers (row 3).
        worksheet.format("A2", {"backgroundColor": _INPUT_COLOR})
        worksheet.format("A1:D1", {"textFormat": {"bold": True}})
        worksheet.format("A3:E3", {"textFormat": {"bold": True}})

        # Mark as active so it gets polled frequently right away.
        self._active_tabs[worksheet.title] = time.monotonic()

        logger.info("Initialized tab [%s]", worksheet.title)

    def _read_session_id(self, label_row: list[str]) -> Optional[str]:
        if len(label_row) < _COL_SESSION_ID:
            return None
        cell_value = label_row[_COL_SESSION_ID - 1].strip()
        if cell_value.startswith("session_id="):
            session_value = cell_value[len("session_id="):]
            return session_value if session_value else None
        return None

    def _write_session_id(self, worksheet: gspread.Worksheet, session_id: str) -> None:
        worksheet.update_cell(_ROW_LABEL, _COL_SESSION_ID, f"session_id={session_id}")

    def get_conversation_history(self, conversation_name: str) -> list[tuple[str, str]]:
        """Read all log rows and return as [(role, text), ...] in chronological order.

        Rows are stored newest-first in the sheet (row 4 is newest), so the
        returned list is reversed to be chronological.
        """
        worksheet = self._spreadsheet.worksheet(conversation_name)
        all_values = worksheet.get_all_values()
        rows = all_values[_ROW_DATA_START - 1:]  # skip label, input, header rows
        history: list[tuple[str, str]] = []
        for row in rows:
            text = row[_COL_TEXT - 1].strip() if len(row) >= _COL_TEXT else ""
            role = row[_COL_ROLE - 1].strip().lower() if len(row) >= _COL_ROLE else ""
            if role in ("user", "claude") and text:
                history.append((role, text))
        history.reverse()
        return history

    def clear_session_id(self, conversation_name: str) -> None:
        """Remove the session ID from a conversation tab."""
        worksheet = self._spreadsheet.worksheet(conversation_name)
        worksheet.update_cell(_ROW_LABEL, _COL_SESSION_ID, "")

    def _is_tab_active(self, tab_name: str) -> bool:
        last_activity = self._active_tabs.get(tab_name)
        if last_activity is None:
            return False
        return (time.monotonic() - last_activity) < 300
