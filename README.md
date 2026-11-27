# Recruitment Mail

Recruitment Mail is a local Flask dashboard for reviewing hiring messages and
applying category labels after you confirm the selection. The portfolio demo
uses a fictional inbox and works offline.

## Features

- Preview up to 50 inbox messages per scan and see scanned, matched, and attention-required counts.
- Classify application confirmations, interview invitations, assessment invitations, rejections, and response requests.
- Review proposed labels and deselect messages before confirmation. Ambiguous messages and conflicting labels are flagged for review.
- See per-message outcomes, then rescan to reconcile uncertain writes and identify already-labeled messages.

## Run the recruitment mail demo

From the project root, create a local virtual environment with Python 3.11
or newer, install the project, and start Flask on loopback:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
RECRUITMENT_MAIL_MODE=mock .venv/bin/python -m flask --app recruitment_mail run --host 127.0.0.1 --no-debug --no-debugger --no-reload
```

Open http://127.0.0.1:5000. The default **Mock inbox** uses fictional messages
and needs no Google credentials. Select **Preview inbox**, review the category
and attention columns, then deselect any proposals you want to skip.
Select **Apply selected labels** and inspect the results. **Preview again**
shows which messages are already labeled. Restart the app to reset the demo.

## Testing

Run the suite from the project root after installing the test extra:

```sh
.venv/bin/python -m pytest -q
```

Tests use fictional messages, Flask's test client, and simulated Gmail
transports. They require no Gmail credentials or network access. On Linux
with user namespaces enabled, enforce network isolation with
`unshare -Un .venv/bin/python -B -m pytest -q`.

## Optional Gmail test account

1. Enable the Gmail API in a Google Cloud project, configure OAuth consent,
   and create a **Desktop app** OAuth client. If the consent screen is in
   testing mode, add your dedicated Gmail test account as a test user.
   Use an account that contains only fictional test mail.
   [Google Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
2. Download the desktop client JSON to a private location outside the project.
   Install the optional dependencies into the project virtual environment
   with `.venv/bin/python -m pip install -e '.[gmail]'`.
3. Start from the project root and replace the shell values below with the
   dedicated account address and external client file path.

   ```sh
   RECRUITMENT_MAIL_MODE=gmail \
   RECRUITMENT_GMAIL_ACCOUNT='dedicated-test@example.com' \
   RECRUITMENT_GMAIL_CLIENT_FILE='/absolute/path/outside/project/desktop-client.json' \
   .venv/bin/python -m flask --app recruitment_mail run --host 127.0.0.1 --no-debug --no-debugger --no-reload
   ```

4. Open the authorization URL printed in the terminal within three minutes.
   Sign in to the dedicated account. The app verifies the authorized Gmail
   profile before enabling preview and displays the verified address on Start.
   Keep debug logging off. Tokens stay in memory, and restarting requires
   authorization again.

For the optional live check, preview two eligible fictional messages, select
one, and confirm. In Gmail, verify the selected message gained exactly its
proposed recruitment label and the deselected message retained its original
labels. Run a fresh preview and check that the selected message is now
**Already labeled**.

## Architecture

Flask routes serve Jinja templates and native HTML forms. The workflow
keeps previews and results in process memory and uses a deterministic phrase
classifier. A shared mailbox contract lets the workflow use either the mock
inbox or the optional Gmail adapter. The adapter handles OAuth, MIME
normalization, and provider-specific requests. Plain CSS and server-rendered
forms keep the interface usable without JavaScript.

## Security and limitations

- Run one local process bound to loopback with debug mode off. Previews are session-bound and expire after 15 minutes. Form submissions require CSRF tokens, and confirmation validates the selection before allowing one submission per preview.
- In Gmail mode, use a dedicated test account. The app verifies the authenticated profile before reading messages. Desktop OAuth credentials belong outside the repository, and tokens stay in memory. Keep credential files and tokens out of Git regardless of filename.
- Gmail grants the broader `gmail.modify` scope. The adapter adds only an approved recruitment category label to each confirmed message and preserves its other labels. If a write is unverified, rescan before confirming again.
- The classifier uses English phrases and may miss unfamiliar wording. Scans are limited to 50 inbox messages. Run history and mock label changes reset on restart.

## Docs

| File | Purpose |
|---|---|
| `docs/01-prd.md` | What and why |
| `docs/02-trd.md` | How: stack and architecture |
| `docs/03-design.md` | Screens, components, visual rules |
| `docs/04-appflow.md` | User journeys and navigation |
| `docs/05-schema.md` | Data models and API contracts |
| `docs/06-plan.md` | Phased checklist with verification |
