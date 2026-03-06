# Changelog

## 2026-03-06 **Implemented remote control of CC via Google Sheets**
- Created project skeleton with `requirements.txt`, `config.yaml`, `.gitignore`
- Defined `Message` and `Response` dataclasses in `src/models.py`
- Defined abstract `Transport` interface in `src/transport.py`
- Implemented `SheetsTransport` in `src/sheets_transport.py` (gspread + service account auth, polls "commands" tab, writes heartbeat to "status" tab)
- Implemented `ClaudeCodeBridge` in `src/cc_bridge.py` (spawns `claude --print` subprocess, parses JSON output, handles errors)
- Implemented `Orchestrator` in `src/orchestrator.py` (poll loop, conversation-to-session mapping, config loading from YAML)
- Manual steps (GCP setup, end-to-end test) tracked in `doc/todo.md`
