# Backlog
- [1] **Per-tab CC configuration**
  Add per-tab settings via columns in the _config tab, read by orchestrator.py and passed to cc_bridge.py send(). Three settings: (1) Working directory — pass as cwd= to subprocess.run in cc_bridge.py line 48. Validate path exists, fall back to default if empty. (2) Model and max-turns — append --model and --max-turns to the command list in cc_bridge.py send() lines 90-105. The _config tab already exists and could have columns for tab name, model, max_turns. (3) System prompt — append --system-prompt to the command list if non-empty. All three follow the same pattern: read from _config, pass through orchestrator to bridge.
  - started: 2026-03-11T09:29:33Z

- [ ] **cc_bridge hardening**
  Two small fixes in cc_bridge.py. (1) Replace hardcoded node path C:\Program Files\nodejs\node.exe at line 85 with shutil.which('node'). The _resolve_executable function (lines 70-88) falls back to this path when node.exe is not in the .cmd shim directory. (2) Make subprocess timeout configurable: move _SUBPROCESS_TIMEOUT_SECONDS = 300 (line 22) to config.yaml with 300 as default. The timeout is used in subprocess.run() at line 48.

- [ ] **Cap session respawn history**
  orchestrator.py lines 108-126 fetch full conversation history via get_conversation_history() and replay it as one prompt when a session is lost. With long conversations this can exceed the CC context window (200k tokens). Add a cap: limit replay to the last N message pairs (e.g. 20) or estimate token count and truncate. get_conversation_history() in sheets_transport.py line 281 returns all rows. The respawn code at orchestrator.py lines 113-124 formats them as User/Assistant pairs.

- [ ] **Token cost aggregation**
  Token counts (input_tokens, output_tokens) are tracked per message in cc_bridge.py JSON parsing (lines 107-156) and context percentage is written to E1 per response. But there is no cumulative view. Add a summary per tab showing total tokens used and estimated cost. Could be written to the _config tab or to a dedicated row in each tab. The Response dataclass in models.py already carries input_tokens and output_tokens fields.

- [ ] **Make a deployable tool**
  Package claudepilot as an installable Python package so it can be used from any repo without copying source code. Rename `src/` to `claudepilot/`, add a `pyproject.toml` with a CLI entry point (`claudepilot` command), and update all imports. Each target repo only needs `config/config.yaml` (pointing to its own Google Sheet), optionally `config/default_commands.txt`, and the service account JSON. Install once with `pip install -e C:\Code\claudepilot` (editable mode) — code changes in the claudepilot repo are picked up immediately, no re-install needed. Usage: `cd C:\Code\my-project && claudepilot config/config.yaml`. We also need to get a very good overview over what files and what is required to use the claudepilot in a new repo: what files must be added. What credentials must be setup. Etc. Right now, we need credentials/service_account.json. We will need to copy this one for ALL repos that wants to use the pilot? Or can be reuse one credential file? What the "config" folder has a too generic name for use as a generic config folder for the claudepilot. Perhaps use ./claudepilot, similar to ".llm/" and .claude/? The current "default_commands.txt": shuld it be tracked by git? I guess so.
- [ ] **Update docs**
  Sync documentation with current scripts

- [ ] **Update default_commands.txt**
  Sync with all current taskmill commands

