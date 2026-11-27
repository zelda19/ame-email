# Data and API contracts

## Models

All application records are transient. The Gmail mailbox owns persistent labels in live mode.

| Model | Fields and meaning |
|---|---|
| Message | Provider message ID, sender, subject, received timestamp, current text, current label IDs. Text is transient classifier input. |
| Decision | Optional category, attention boolean, disposition of matched, ambiguous, or unrelated. |
| Preview | Opaque run ID, session owner, mailbox identity, expiry, run state, scan counts, and rows keyed by message ID. Rows retain display fields, decision, eligibility, and reason. |
| Result | Run ID and one outcome per unique selected ID. Outcomes are applied, already labeled, failed, unverified, or unprocessed, with a short safe explanation where needed. |

## Relationships

One preview belongs to one session and mailbox. Each unique ID has at most one proposed category. Only eligible rows from that preview can become selected results. The five result counts sum to the number of unique selected IDs. The UI may group failed and unverified counts while preserving each row’s exact status.

## API contracts

The browser interface uses HTML forms and redirects. The server derives labels and account identity from the saved preview.

| Method and path | Input | Result |
|---|---|---|
| `GET /` | Session | Start page with mode and mailbox status |
| `POST /preview` | CSRF token | Build a preview, replace the previous one, and redirect to its page |
| `GET /runs/<id>` | Session-owned run ID | Render preview, processing state, or completed results |
| `POST /runs/<id>/confirm` | CSRF token and selected message IDs | Apply the validated selection once and redirect to the run. A replay returns the existing state. |
| `POST /runs/<id>/cancel` | CSRF token | Discard a pending preview and redirect to Start |

Reject an empty or invalid selection as a form error, invalid CSRF with `403`, and an unknown or another session’s run with `404`. An expired preview prompts a rescan. Use the mailbox contract to list inbox IDs, read messages, inspect current label state, and apply one approved category. Keep OAuth and provider-specific error translation inside the Gmail adapter.
