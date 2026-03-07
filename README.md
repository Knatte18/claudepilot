# claudepilot

Remote control of [Claude Code](https://docs.anthropic.com/en/docs/claude-code) via Google Sheets.

Each spreadsheet tab is a conversation. Type a prompt in column D, and the orchestrator picks it up, sends it to Claude Code CLI, and writes the response back.

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm install -g @anthropic-ai/claude-code`)
- A Google Cloud service account with Sheets API enabled

## Google Cloud setup

1. Create a GCP project and enable the Google Sheets API
2. Create a service account and download the JSON key to `credentials/service_account.json`
3. Create a Google Sheet with a `status` tab and at least one conversation tab
4. Share the sheet with the service account email (Editor role)

## Installation

```bash
poetry install
```

## Configuration

Copy `config/config.example.yaml` to `config/config.yaml` and fill in:

- `google_sheets.spreadsheet_id` — from the sheet URL
- `google_sheets.service_account_key_file` — path to service account JSON key
- `claude_code.executable` — path to `claude` (or `claude.cmd` on Windows)

The spreadsheet must be shared with the service account email (Editor role).

## Sheet layout

Each conversation tab has this structure:

| Row | Content |
|-----|---------|
| 1   | **Prompt:** \| **Send** \| \| \| session_id (H1, managed) |
| 2   | [input cell, yellow, thick border] \| [send checkbox] |
| 3   | **Text** \| **Role** \| **Status** \| **Timestamp** (header) |
| 4+  | Log entries, newest first |

Type your prompt in A2 and tick the checkbox in B2 to send. The orchestrator clears the input, logs the prompt, sends it to Claude Code, and inserts the response above.

New tabs are auto-initialized with headers and checkbox when detected.

## Running

```bash
python -m src.orchestrator config/config.yaml
```

Stop with Ctrl+C.

## Polling behavior

- **Active polling** (default 5s) — used when there has been recent activity
- **Idle polling** (default 30s) — used after no activity for 2 minutes
- Inactive tabs (no activity for 5 minutes) are checked every 5th poll cycle

All intervals are configurable in `config/config.yaml`.
