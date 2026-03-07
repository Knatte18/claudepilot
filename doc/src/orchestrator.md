# orchestrator.py

Main loop that ties the transport and Claude Code bridge together using a thread-per-tab model.

## `TabWorker`

Manages a single conversation tab in its own thread. Each worker independently polls its tab and dispatches prompts to the Claude Code bridge.

### Constructor

```python
TabWorker(
    tab_name: str,
    transport: Transport,
    bridge: ClaudeCodeBridge,
    stop_event: threading.Event,
    poll_fast_seconds: int = 2,
    poll_slow_seconds: int = 30,
    idle_threshold_seconds: int = 120,
)
```

| Parameter               | Description                                                    |
|-------------------------|----------------------------------------------------------------|
| `tab_name`              | The name of the conversation tab this worker manages.          |
| `transport`             | The shared transport instance.                                 |
| `bridge`                | The shared Claude Code bridge instance.                        |
| `stop_event`            | Set by the Orchestrator to signal the worker to stop.          |
| `poll_fast_seconds`     | Polling interval while active (default 2).                     |
| `poll_slow_seconds`     | Polling interval when idle (default 30).                       |
| `idle_threshold_seconds`| Seconds without activity before switching to slow (default 120).|

### `run()`

Runs the worker loop until `stop_event` is set:

1. Calls `transport.initialize_tab_if_needed()` once on startup.
2. Loops: calls `transport.poll_tab()`, then `transport.write_heartbeat()`.
3. If a message is found, calls `_handle_message()` and records the activity time.
4. Sleeps for `poll_fast_seconds` if active recently, or `poll_slow_seconds` if idle longer than `idle_threshold_seconds`. Sleep is done in 1-second increments so `stop_event` is checked promptly.

### `_handle_message()`

Processes a single prompt:

1. Prepends the command (if any) to the prompt text.
2. Intercepts `!!reload` — reloads commands from `_config` and posts an info row.
3. Sends the combined prompt to the Claude Code bridge.
4. **Session recovery:** if CC returns "No conversation found with session ID", clears the session ID, builds a context prompt from the tab's history, and spawns a new session. Posts an info row noting the respawn.
5. On error, posts an error row. On success, posts the response and logs token usage.

## `Orchestrator`

Supervisor loop that manages the pool of `TabWorker` threads.

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

Polling intervals are forwarded to each `TabWorker` spawned by the supervisor.

### `run()`

Starts a blocking supervisor loop that runs until interrupted (`KeyboardInterrupt`). Every `_SUPERVISOR_INTERVAL` (10s):

1. Calls `transport.list_conversations()` to get the current set of tabs.
2. Spawns a new daemon `TabWorker` thread for each tab not yet in the worker pool.
3. Sets the `stop_event` for workers whose tabs no longer exist (deleted or renamed).

On `KeyboardInterrupt`, sets all stop events and joins all threads (timeout 10s each), then exits.

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

When run as `python -m src.orchestrator [config/config.yaml]`, builds an orchestrator from the config file (defaults to `config/config.yaml`) and starts the supervisor loop.
