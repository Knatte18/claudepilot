# Changelog

## 2026-03-06 **Rewrote sheets_transport.md to match current code**
- Corrected tab layout: row 1 labels, row 2 input+checkbox, row 3 headers, row 4+ data (was: row 1 session_id, row 2 headers, row 3+ data)
- Corrected column order: text | role | status | timestamp (was: timestamp | role | status | text)
- Corrected session ID location: H1 on label row (was: A1)
- Documented checkbox-based submission model, active/inactive tab polling tiers, crash recovery, and tab auto-initialization

## 2026-03-06 **Added module docstrings to all .py files**
- Added module-level docstrings to `src/__init__.py`, `src/models.py`, `src/transport.py`, `src/orchestrator.py`, `src/cc_bridge.py`, and `src/sheets_transport.py` describing each module's purpose and role in the system

## 2026-03-06 **Updated source documentation**
- Updated `doc/src/orchestrator.md` to reflect adaptive polling (`poll_fast_seconds`, `poll_slow_seconds`, `idle_threshold_seconds`) replacing the old `polling_interval_seconds` parameter
- Updated `doc/src/sheets_transport.md` to reflect new column layout (`timestamp | role | status | text`), status tracking (`processing`/`done`), and row color formatting per role

## 2026-03-06 **Implemented remote control of CC via Google Sheets**
- Created project skeleton with `requirements.txt`, `config.yaml`, `.gitignore`
- Defined `Message` and `Response` dataclasses in `src/models.py`
- Defined abstract `Transport` interface in `src/transport.py`
- Implemented `SheetsTransport` in `src/sheets_transport.py` (gspread + service account auth, polls "commands" tab, writes heartbeat to "status" tab)
- Implemented `ClaudeCodeBridge` in `src/cc_bridge.py` (spawns `claude --print` subprocess, parses JSON output, handles errors)
- Implemented `Orchestrator` in `src/orchestrator.py` (poll loop, conversation-to-session mapping, config loading from YAML)
- Manual steps (GCP setup, end-to-end test) tracked in `doc/todo.md`
