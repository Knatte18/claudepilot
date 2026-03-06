# orchestrator.py

Main loop that ties the transport and Claude Code bridge together.

## `Orchestrator`

### Constructor

```python
Orchestrator(
    transport: Transport,
    bridge: ClaudeCodeBridge,
    poll_fast_seconds: int = 2,
    poll_slow_seconds: int = 30,
    idle_threshold_seconds: int = 120,
)
```

| Parameter               | Description                                                                 |
|-------------------------|-----------------------------------------------------------------------------|
| `poll_fast_seconds`     | Polling interval while active (seconds since last prompt < idle threshold). |
| `poll_slow_seconds`     | Polling interval when idle.                                                 |
| `idle_threshold_seconds`| Seconds without activity before switching to the slow polling interval.     |

### `run()`

Starts a blocking polling loop that runs until interrupted (`KeyboardInterrupt`). Each tick:

1. Publishes a `state=polling` heartbeat via the transport.
2. Calls `transport.poll()` for an unanswered user prompt.
3. If a message is found, publishes `state=processing` and sends the prompt to Claude Code via the bridge.
4. On success, writes the response back through the transport.
5. On error, reports the error through the transport.
6. Sleeps for `poll_fast_seconds` if a prompt was processed recently, otherwise `poll_slow_seconds`.

Unhandled exceptions are logged but do not stop the loop. Sleep is done in 1-second increments so `Ctrl+C` is responsive on Windows.

### Adaptive polling

- After processing a prompt, `_last_activity_time` is updated.
- If `time.monotonic() - _last_activity_time < idle_threshold_seconds`, the fast interval is used.
- Otherwise the slow interval is used.

## Helper functions

### `load_config(config_path: str) -> dict`

Reads and parses a YAML configuration file.

### `build_orchestrator_from_config(config_path: str) -> Orchestrator`

Constructs a fully wired `Orchestrator` from a YAML config file. Expected config structure:

```yaml
google_sheets:
  service_account_key_file: path/to/key.json
  spreadsheet_id: <spreadsheet-id>
  status_tab: status                # optional, default "status"

claude_code:
  permission_mode: bypassPermissions  # optional
  executable: claude                  # optional
  poll_fast_seconds: 2                # optional
  poll_slow_seconds: 30               # optional
  idle_threshold_seconds: 120         # optional
```

## CLI entry point

When run as `python -m src.orchestrator [config.yaml]`, builds an orchestrator from the config file (defaults to `config.yaml`) and starts the polling loop.
