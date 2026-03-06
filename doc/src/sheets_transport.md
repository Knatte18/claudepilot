# sheets_transport.py

Concrete `Transport` implementation backed by a Google Spreadsheet, one tab per conversation.

## How it works

- Each spreadsheet tab represents a conversation.
- Row 1 has labels ("Prompt:", "Send") and the session ID in H1.
- The user types a prompt into A2 and ticks the checkbox in B2 to submit.
- The orchestrator picks up the prompt, clears the input, inserts a user log row at the top (row 4), sends it to Claude Code, and inserts the response row above.
- Log rows are newest-first (inserted at row 4, pushing older rows down).
- A dedicated status tab (default name: `status`) receives heartbeat updates.

### Tab layout

| Row | Content                                                              |
|-----|----------------------------------------------------------------------|
| 1   | Labels: A1=`Prompt:` (bold), B1=`Send` (bold), H1=`session_id=<id>` |
| 2   | Input: A2=[user prompt, yellow bg, thick border], B2=[send checkbox] |
| 3   | Header row: `Text | Role | Status | Timestamp` (bold)               |
| 4+  | Data rows (newest first)                                             |

### Column layout (data rows)

| Column | Field       | Description                                              |
|--------|-------------|----------------------------------------------------------|
| A (1)  | `text`      | The message content.                                     |
| B (2)  | `role`      | `user`, `claude`, or `error`.                            |
| C (3)  | `status`    | `processing` or `done`.                                  |
| D (4)  | `timestamp` | UTC timestamp in `YYYY-MM-DD HH:MM:SS UTC` format.      |

### Row colors

Rows are color-coded by role using background colors:

| Role    | Color       |
|---------|-------------|
| `user`  | Light blue  |
| `claude`| Light green |
| `error` | Light red   |

The input cell (A2) has a light yellow background.

## `SheetsTransport`

### Constructor

```python
SheetsTransport(
    service_account_key_file: str,
    spreadsheet_id: str,
    status_tab: str = "status",
)
```

| Parameter                  | Description                                            |
|----------------------------|--------------------------------------------------------|
| `service_account_key_file` | Path to the Google service account JSON key file.      |
| `spreadsheet_id`           | The ID of the Google Spreadsheet to use.               |
| `status_tab`               | Name of the tab used for heartbeat/status updates.     |

Authentication uses `google.oauth2.service_account.Credentials` with the `spreadsheets` scope, authorized via `gspread`.

### Polling logic (`poll`)

1. Iterates over all worksheet tabs (skipping the status tab).
2. New/empty tabs are auto-initialized with labels, input cell, checkbox, and headers.
3. Active tabs (activity within the last 5 minutes) are checked every cycle. Inactive tabs are checked every 5th cycle. Tabs not yet seen are always checked for fast detection.
4. Reads A1:H4 and checks whether B2 (checkbox) is `TRUE` and A2 (prompt) is non-empty.
5. When a prompt is found:
   - Reads the `session_id` from H1.
   - Clears the checkbox (B2) and prompt text (A2) for immediate user feedback.
   - Inserts a user log row at row 4 with status `processing` and a light blue background.
6. **Crash recovery:** if the top data row (row 4) is a `user` row with status `processing` and the tab is not currently being processed, the prompt is re-dispatched.

### Response handling

- `respond` — inserts a `claude` row at row 4 (pushing the user row to row 5), marks the user row as `done`, writes the `session_id` to H1.
- `report_error` — inserts an `error` row at row 4, marks the user row as `done`.
- `update_status` — overwrites row A1 of the status tab with a timestamped key=value heartbeat. Creates the status tab if it doesn't exist.

### Tab auto-initialization (`_initialize_tab`)

When a new or empty tab is detected, it is set up with:

- Row 1: bold labels ("Prompt:", "Send").
- Row 2: yellow-background input cell (A2) with a thick border, boolean checkbox validation on B2.
- Row 3: bold column headers ("Text", "Role", "Status", "Timestamp").
