# Backlog
- [ ] **Graceful gspread retry**
  Add retry with exponential backoff for transient gspread API errors (503, etc.) in sheets_transport.py so the agent recovers gracefully instead of logging a raw traceback

