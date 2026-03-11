- [ ] **Token cost aggregation**
  Token counts (input_tokens, output_tokens) are tracked per message in cc_bridge.py JSON parsing (lines 107-156) and context percentage is written to E1 per response. But there is no cumulative view. Add a summary per tab showing total tokens used and estimated cost. Could be written to the _config tab or to a dedicated row in each tab. The Response dataclass in models.py already carries input_tokens and output_tokens fields.

- [ ] **Make a deployable tool**
  Package claudepilot as an installable Python package so it can be used from any repo without copying source code. Rename `src/` to `claudepilot/`, add a `pyproject.toml` with a CLI entry point (`claudepilot` command), and update all imports. Each target repo only needs `config/config.yaml` (pointing to its own Google Sheet), optionally `config/default_commands.txt`, and the service account JSON. Install once with `pip install -e C:\Code\claudepilot` (editable mode) — code changes in the claudepilot repo are picked up immediately, no re-install needed. Usage: `cd C:\Code\my-project && claudepilot config/config.yaml`. We also need to get a very good overview over what files and what is required to use the claudepilot in a new repo: what files must be added. What credentials must be setup. Etc. Right now, we need credentials/service_account.json. We will need to copy this one for ALL repos that wants to use the pilot? Or can be reuse one credential file? What the "config" folder has a too generic name for use as a generic config folder for the claudepilot. Perhaps use ./claudepilot, similar to ".llm/" and .claude/? The current "default_commands.txt": shuld it be tracked by git? I guess so.
- [ ] **Update docs**
  Sync documentation with current scripts

- [ ] **Update default_commands.txt**
  Sync with all current taskmill commands

