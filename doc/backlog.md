# Backlog
- [p] **Add multithreading**
  Right now there is one thread in the script that polls all sheets. But it means that the whole process stops when it is waiting for a prompt. This kind of eliminates the idea of having multiple sheets. The idea is then to let the main orchestration thread spawn a dedicated thread per Sheet, which polls its own sheet, and handles every interaction with Claude CLI itself. If the sheet is deleted, the thread dies. If the sheet is renamed (which is handled atm), the thread dies, but the main thread spawns a new thread.
  - started: 2026-03-07T06:29:30Z
  - plan: .llm/plans/2026-03-07-065833-add-multithreading.md

- [ ] **Graceful gspread retry**
  Add retry with exponential backoff for transient gspread API errors (503, etc.) in sheets_transport.py so the agent recovers gracefully instead of logging a raw traceback

