# models.py

Data classes shared across the application.

## `Message`

Represents a user prompt discovered in a conversation tab.

| Field               | Type            | Description                                      |
|---------------------|-----------------|--------------------------------------------------|
| `conversation_name` | `str`           | Name of the conversation (matches the tab title). |
| `command`           | `Optional[str]` | Command selected from the dropdown (e.g. `/taskmill:discuss`). `None` if no command selected. |
| `text`              | `str`           | The user's prompt text.                          |
| `session_id`        | `Optional[str]` | Claude Code session ID for resuming a conversation. `None` for new conversations. |

## `Response`

The result returned after sending a `Message` to Claude Code.

| Field           | Type            | Description                                 |
|-----------------|-----------------|---------------------------------------------|
| `text`          | `str`           | The assistant's reply text.                 |
| `session_id`    | `str`           | Session ID for continuing the conversation. |
| `error`         | `Optional[str]` | Error description, or `None` on success.    |
| `input_tokens`  | `int`           | Number of input tokens consumed.            |
| `output_tokens` | `int`           | Number of output tokens generated.          |

### Properties

- `is_error` — returns `True` when `error` is not `None`.
