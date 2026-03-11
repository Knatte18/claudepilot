# Backlog

- [ ] **Update docs**
  Sync documentation with current scripts

- [ ] **Make a deployable tool**
  Package claudepilot as an installable Python package so it can be used from any repo without copying source code. Rename `src/` to `claudepilot/`, add a `pyproject.toml` with a CLI entry point (`claudepilot` command), and update all imports. Each target repo only needs `config/config.yaml` (pointing to its own Google Sheet), optionally `config/default_commands.txt`, and the service account JSON. Install once with `pip install -e C:\Code\claudepilot` (editable mode) — code changes in the claudepilot repo are picked up immediately, no re-install needed. Usage: `cd C:\Code\my-project && claudepilot config/config.yaml`. We also need to get a very good overview over what files and what is required to use the claudepilot in a new repo: what files must be added. What credentials must be setup. Etc. Right now, we need credentials/service_account.json. We will need to copy this one for ALL repos that wants to use the pilot? Or can be reuse one credential file? What the "config" folder has a too generic name for use as a generic config folder for the claudepilot. Perhaps use ./claudepilot, similar to ".llm/" and .claude/? The current "default_commands.txt": shuld it be tracked by git? I guess so.
