# cc_bridge.py

Invokes the Claude Code CLI as a subprocess and parses the result.

## `ClaudeCodeBridge`

### Constructor

```python
ClaudeCodeBridge(
    permission_mode: str = "bypassPermissions",
    executable: str = "claude",
    timeout_seconds: int = 300,
)
```

| Parameter         | Description                                                    |
|-------------------|----------------------------------------------------------------|
| `permission_mode` | Permission mode passed to the `--permission-mode` CLI flag.    |
| `executable`      | Path to the `claude` executable (configured in `config.yaml`). |
| `timeout_seconds` | Subprocess timeout in seconds (default 300, configurable via `subprocess_timeout_seconds` in `config.yaml`). |

### `send(prompt, session_id=None) -> Response`

Sends a prompt to Claude Code and returns a parsed `Response`.

1. Builds the CLI command with `--print`, `--output-format json`, and `--permission-mode`.
2. If a `session_id` is provided, adds `--resume <session_id>` to continue an existing conversation.
3. Runs the command as a subprocess with the configured timeout.
4. On non-zero exit, returns a `Response` with the error.
5. On success, parses the JSON output to extract the assistant's reply text, session ID, and token usage.

### JSON parsing

The bridge handles two CC output formats:

- **`result` field** — used directly as the assistant text.
- **`messages` array** — scans for `role="assistant"` messages and concatenates their text content blocks.
