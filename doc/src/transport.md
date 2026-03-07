# transport.py

Defines the `Transport` abstract base class — the communication layer between the user and the orchestrator.

Each conversation is identified by name. The transport is responsible for listing active tabs, polling individual tabs for prompts, initializing tabs, storing the Claude Code `session_id` so conversations can be resumed, and writing responses back.

## `Transport` (ABC)

### Methods

| Method                    | Signature                                                                                                      | Description                                                         |
|---------------------------|----------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| `list_conversations`      | `() -> list[str]`                                                                                              | Return the names of all active conversation tabs.                   |
| `poll_tab`                | `(conversation_name: str) -> Optional[Message]`                                                                | Return the next unanswered user prompt from a specific tab, or `None`. |
| `initialize_tab_if_needed`| `(conversation_name: str) -> None`                                                                             | Initialize a tab with labels, input cell, checkbox, and headers if not yet set up. |
| `respond`                 | `(conversation_name: str, text: str, session_id: str, input_tokens: int = 0, output_tokens: int = 0) -> None` | Append the assistant response and persist the session ID.           |
| `report_error`            | `(conversation_name: str, error_text: str) -> None`                                                            | Append an error message to the conversation.                        |
| `report_info`             | `(conversation_name: str, info_text: str) -> None`                                                             | Append an informational message to the conversation.                |
| `get_conversation_history`| `(conversation_name: str) -> list[tuple[str, str]]`                                                            | Return conversation log as `[(role, text), ...]` in chronological order. |
| `clear_session_id`        | `(conversation_name: str) -> None`                                                                             | Remove the session ID from a conversation tab.                      |
| `write_heartbeat`         | `(conversation_name: str) -> None`                                                                             | Write a last-polled timestamp to the tab. Default: no-op.           |
| `reload_commands`         | `() -> int`                                                                                                    | Reload command list and re-apply to all tabs. Default: no-op (returns 0). |

`list_conversations`, `poll_tab`, `initialize_tab_if_needed`, `respond`, `report_error`, `report_info`, `get_conversation_history`, and `clear_session_id` are abstract and must be implemented by concrete subclasses (see `SheetsTransport`). `write_heartbeat` and `reload_commands` have default no-op implementations that subclasses may override.
