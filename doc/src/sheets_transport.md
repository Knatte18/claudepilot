# sheets_transport.py

Concrete `Transport` implementation backed by a Google Spreadsheet, one tab per conversation.

## How it works

- Each spreadsheet tab represents a conversation.
- Row 1 has labels, the session ID in J1, and a last-polled heartbeat timestamp in K1.
- The user selects a command from the dropdown in A2, types a prompt into B2, and ticks the checkbox in C2 to submit.
- The orchestrator concatenates the command (if any) and the prompt text, clears the input cells, inserts a user log row at the top (row 4), sends the combined text to Claude Code, and inserts the response row above.
- Log rows are newest-first (inserted at row 4, pushing older rows down).
- A `_config` tab holds the command list for the dropdown. Sending `!!reload` refreshes the dropdown on all tabs without restarting.
- Each conversation tab receives a heartbeat timestamp in K1 each time its `TabWorker` polls it.

### Tab layout

| Row | Content                                                                                                                     |
|-----|-----------------------------------------------------------------------------------------------------------------------------|
| 1   | Labels: A1=`Command:` (bold), B1=`Prompt:` (bold), C1=`Send` (bold), D1=`Context:` (bold), E1=percentage, J1=`session_id=<id>`, K1=last-polled timestamp |
| 2   | Input: A2=[command dropdown], B2=[user prompt, yellow bg, thick border], C2=[send checkbox]                                 |
| 3   | Header row: `Role \| Text \| Status \| Timestamp \| Tokens` (bold)                                                          |
| 4+  | Data rows (newest first)                                                                                                    |

### Column layout (data rows)

| Column | Field       | Description                                              |
|--------|-------------|----------------------------------------------------------|
| A (1)  | `role`      | `user`, `claude`, `error`, or `info`.                    |
| B (2)  | `text`      | The message content.                                     |
| C (3)  | `status`    | `processing` or `done`.                                  |
| D (4)  | `timestamp` | UTC timestamp in `YYYY-MM-DD HH:MM:SS UTC` format.      |
| E (5)  | `tokens`    | Token usage as `input / output` (on claude rows).        |

### Row colors

Rows are color-coded by role using background colors:

| Role    | Color       |
|---------|-------------|
| `user`  | Light blue  |
| `claude`| Light green |
| `error` | Light red   |
| `info`  | Light amber |

The prompt input cell (B2) has a light yellow background.

### _config tab

The `_config` tab stores the command list for the A2 dropdown. It is auto-created on first startup with default entries.

| Row | A              |
|-----|----------------|
| 1   | **Commands**   |
| 2   | !!reload       |
| 3   | /simplify      |
| 4   | /taskmill:discuss |
| 5   | /taskmill:do   |
| ... | *(etc.)*       |

The full list is read from `config/default_commands.txt` on first startup. That file supports `#` comment lines. Users can add, remove, or reorder rows in the `_config` tab freely. Changes take effect after sending `!!reload` from any conversation tab.

### !!reload command

Sending `!!reload` (in the text input or via the dropdown) is intercepted by the `TabWorker` before reaching Claude Code. It re-reads the `_config` tab and re-applies the dropdown validation to all conversation tabs. An info row is posted confirming the reload with the number of commands loaded.

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
| `status_tab`               | Name of the tab to exclude from conversation listing.  |

Authentication uses `google.oauth2.service_account.Credentials` with the `spreadsheets` scope, authorized via `gspread`. On startup, the `_config` tab is auto-created if missing, and the command list is loaded into memory.

### Retry logic

All gspread API calls are wrapped in `_retry_api_call()`, which retries up to 3 times with exponential backoff (1s, 2s, 4s) on transient errors (HTTP 429 and 503).

### Tab listing (`list_conversations`)

Returns all tab names except the status tab and `_config`.

### Single-tab polling (`poll_tab`)

1. Reads A1:J4 of the given tab.
2. Checks whether C2 (checkbox) is `TRUE` and B2 (prompt) is non-empty.
3. When a prompt is found:
   - Reads the `session_id` from J1 and the command from A2.
   - Clears the checkbox (C2), prompt text (B2), and dropdown (A2) for immediate user feedback.
   - Inserts a user log row at row 4 with status `processing` and a light blue background.
   - Returns a `Message` with `command` and `text` as separate fields.
4. **Crash recovery:** if the top data row (row 4) is a `user` row with status `processing`, the prompt is re-dispatched.

### Tab initialization (`initialize_tab_if_needed`)

Reads the first three rows of the tab. If headers are missing (new or empty tab), calls `_initialize_tab` to set up labels, dropdown, input cell, checkbox, and headers.

### Heartbeat (`write_heartbeat`)

Writes the current UTC timestamp to K1 of the tab. Called by `TabWorker` each poll cycle as a last-polled indicator.

### Response handling

- `respond` — inserts a `claude` row at row 4 (pushing the user row to row 5), marks the user row as `done`, writes the `session_id` to J1, and updates the context usage percentage in E1.
- `report_error` — inserts an `error` row at row 4, marks the user row as `done`.
- `report_info` — inserts an `info` row at row 4 (no user row shift).
- `reload_commands` — re-reads the `_config` tab and re-applies dropdown validation to all conversation tabs. Returns the command count.

### Tab auto-initialization (`_initialize_tab`)

When a new or empty tab is detected, it is set up with:

- Row 1: bold labels ("Command:", "Prompt:", "Send", "Context:").
- Row 2: dropdown validation on A2, yellow-background prompt input cell (B2) with a thick border, boolean checkbox validation on C2.
- Row 3: bold column headers ("Role", "Text", "Status", "Timestamp", "Tokens").
