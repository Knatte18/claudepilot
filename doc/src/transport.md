# transport.py

Defines the `Transport` abstract base class — the communication layer between the user and the orchestrator.

Each conversation is identified by name. The transport is responsible for storing the Claude Code `session_id` so conversations can be resumed.

## `Transport` (ABC)

### Methods

| Method         | Signature                                                        | Description                                          |
|----------------|------------------------------------------------------------------|------------------------------------------------------|
| `poll`         | `() -> Optional[Message]`                                        | Return the next unanswered user prompt, or `None`.   |
| `respond`      | `(conversation_name: str, text: str, session_id: str, input_tokens: int = 0, output_tokens: int = 0) -> None` | Append the assistant response and persist the session ID. |
| `report_error` | `(conversation_name: str, error_text: str) -> None`              | Append an error message to the conversation.         |
| `update_status`| `(status: dict) -> None`                                        | Publish a status/heartbeat dictionary.               |

All methods are abstract and must be implemented by concrete subclasses (see `SheetsTransport`).
