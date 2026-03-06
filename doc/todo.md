# Manual TODO

## Google Cloud setup
- [ ] Create GCP project, enable Sheets API
- [ ] Create service account, download JSON key to `credentials/service_account.json`
- [ ] Create Google Sheet with `commands` and `status` tabs (columns: timestamp | conversation_id | prompt | status | response | error)
- [ ] Share sheet with service account email
- [ ] Fill in `spreadsheet_id` in `config.yaml`

## End-to-end test
- [ ] `pip install -r requirements.txt`
- [ ] `python -m src.orchestrator config.yaml`
- [ ] Write a prompt row in the sheet, verify watcher picks it up and writes response back
