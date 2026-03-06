# sheets_transport.py

Concrete `Transport` implementation backed by a Google Spreadsheet, one tab per conversation.

## How it works

- Each spreadsheet tab represents a conversation.
- Users write rows with `role="user"` (or leave role empty — a row with text but no role is treated as a user prompt).
- The orchestrator appends rows with `role="claude"`.
- The Claude Code `session_id` is stored in cell A1 of each tab (`session_id=<id>`).
- A dedicated status tab (default name: `status`) receives heartbeat updates.

### Tab layout

| Row | Content                                        |
|-----|------------------------------------------------|
| 1   | `session_id=` or `session_id=<id>`            |
| 2   | Header row: `timestamp | role | status | text` |
| 3+  | Data rows                                      |

### Column layout

| Column | Field       | Description                                              |
|--------|-------------|----------------------------------------------------------|
| A (1)  | `timestamp` | UTC timestamp in `YYYY-MM-DD HH:MM:SS UTC` format.       |
| B (2)  | `role`      | `user`, `claude`, or `error`.                            |
| C (3)  | `status`    | `processing` or `done`.                                  |
| D (4)  | `text`      | The message content.                                     |

### Row colors

Rows are color-coded by role using background colors:

| Role    | Color      |
|---------|------------|
| `user`  | Light blue |
| `claude`| Light green|
| `error` | Light red  |

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
2. Checks the last row of each tab.
3. A row is treated as a user prompt if `role="user"`, or if role is empty and text (column D) is non-empty.
4. Rows with `status="processing"` or `status="done"` are skipped (already handled).
5. When a prompt is found, the row's status column is set to `"processing"` and the row is colored before returning.
6. Reads the `session_id` from cell A1 to allow conversation resumption.

### Response handling

- `respond` — marks the last user row as `done`, appends a `claude` row with timestamp + color, writes the `session_id` to A1.
- `report_error` — marks the last user row as `done`, appends an `error` row with timestamp + color.
- `update_status` — overwrites row A1 of the status tab with a timestamped key=value heartbeat.
