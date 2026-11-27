# Data and API contracts

## Models

All application records are transient. The Gmail mailbox owns persistent labels in live mode.

| Model | Fields and meaning |
|---|---|
| Message | Provider message ID, sender, subject, received timestamp, current text, current user label names and inbox membership. The Gmail adapter resolves provider label IDs to exact names. Text is transient classifier input. |
| Decision | Optional category, attention boolean, disposition of matched, ambiguous, or unrelated. |
| Preview | Opaque run ID, session ownership, expiry, run state, scan counts, and rows keyed by message ID. Rows retain display fields, decision, eligibility, and reason. |
| Result | Run ID and one outcome per unique selected ID. Outcomes are applied, already labeled, failed, unverified, or unprocessed, with a short safe explanation where needed. |

## Relationships

One preview belongs to one session and mailbox. Each unique ID has at most one proposed category. Only eligible rows from that preview can become selected results. The five result counts sum to the number of unique selected IDs. The UI may group failed and unverified counts while preserving each row’s exact status.

## API contracts

The browser interface uses HTML forms and redirects. The server derives categories from the saved preview. The workflow uses a fixed mailbox adapter for the lifetime of the app.

| Method and path | Input | Result |
|---|---|---|
| `GET /` | Session | Start page with mode and mailbox status |
| `POST /preview` | CSRF token | Build a preview, replace the previous one, and redirect to its page |
| `GET /runs/<id>` | Session-owned run ID | Render preview, processing state, or completed results |
| `POST /runs/<id>/confirm` | CSRF token and selected message IDs | Apply the validated selection once and redirect to the run. A replay returns the existing state. |
| `POST /runs/<id>/cancel` | CSRF token | Discard a pending preview and redirect to Start |

Reject an empty or invalid selection as a form error, invalid CSRF with `403`, and an unknown or another session’s run with `404`. An expired preview returns `410` and prompts a rescan. A valid form submission that navigates to another page redirects with `303`.

## Mailbox adapter

- `list_inbox_ids(limit)` returns message IDs up to the scan limit.
- `read_message(message_id)` returns a normalized message with its current user label names and inbox membership. Confirmation uses this operation to recheck the selected row.
- An adapter can expose `preview_reader()` to supply a reader for one scan. Gmail takes one label-name map for a nonempty preview and reuses it for the messages in that scan. Confirmation reads a fresh map and resolves the exact target label again before writing.
- `apply_category(message_id, category)` adds one allowed category label to the message and preserves other labels. Gmail keeps provider label IDs, OAuth, and provider error translation within the adapter.
