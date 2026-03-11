# Changelog

## 2026-03-11 **Optimized Sheets API usage**
- Added `_retry_api_call()` helper in `sheets_transport.py` with exponential backoff (3 attempts, 1s/2s/4s delays) for transient gspread API errors (HTTP 429 and 503)
- Wrapped all gspread API calls in `poll_tab()`, `respond()`, `report_error()`, `report_info()`, `write_heartbeat()`, `get_conversation_history()`, `clear_session_id()`, and `_write_session_id()` with the retry helper
- Throttled heartbeat writes in `orchestrator.py` `TabWorker` from every poll cycle (every 2s when active) to every 30 seconds, cutting idle API usage in half
- Added `tests/test_sheets_transport.py` with 6 tests for retry logic and `tests/test_orchestrator.py` with 3 tests for heartbeat throttling

## 2026-03-07 **Multithreaded orchestrator (one worker per tab)**
- Replaced the single-threaded poll loop with a supervisor + thread-per-tab model: the `Orchestrator` runs a supervisor loop every 10s that spawns/stops `TabWorker` threads as tabs appear or disappear
- Added `TabWorker` class in `orchestrator.py`: each worker independently polls its own tab, dispatches to Claude Code, and writes responses back — multiple conversations now run in parallel
- Refactored `Transport` ABC: added `list_conversations()`, `poll_tab()`, `initialize_tab_if_needed()`, `write_heartbeat()` abstract/default methods; removed `poll()` and `update_status()`; promoted `get_conversation_history()` and `clear_session_id()` to the ABC
- Refactored `SheetsTransport`: implemented new ABC methods, removed all shared mutable state (`_active_tabs`, `_processing_tabs`, `_known_tabs`, `_poll_cycle`), removed dedicated status tab; added per-tab heartbeat timestamp written to K1 each poll cycle
- `build_orchestrator_from_config` simplified: `poll_fast_seconds`, `poll_slow_seconds`, `idle_threshold_seconds` removed from `Orchestrator` constructor (now hardcoded defaults in `TabWorker`)
- Updated `doc/src/transport.md`, `doc/src/sheets_transport.md`, and `doc/src/orchestrator.md`

## 2026-03-07 **Dropdown menu with common CC commands**
- Shifted all data columns right by one: column A is now Role (narrow), column B is Text (wide), C=Status, D=Timestamp, E=Tokens; session ID moved from H1 to J1
- Added command dropdown in A2 populated from a new `_config` tab (auto-created on startup with default entries: `!!reload`, `/taskmill:discuss`, `/taskmill:do`, `/taskmill:commit`, `/simplify`)
- The orchestrator concatenates the dropdown command and prompt text before sending to Claude Code
- Added `!!reload` special command: intercepted by the orchestrator, re-reads `_config`, re-applies dropdown validation to all conversation tabs, and posts a confirmation info row
- Added `command` field to the `Message` dataclass in `models.py`
- Added `reload_commands` default method to the `Transport` ABC; implemented in `SheetsTransport`
- Updated `doc/src/sheets_transport.md` to reflect new layout, `_config` tab, and `!!reload`

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
