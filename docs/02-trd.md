# Technical requirements

## Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.11 or newer, virtual environment, single local Flask process bound to loopback |
| Interface | Flask routes, Jinja templates, plain CSS, native HTML forms |
| Classification and state | Python functions and standard-library data structures. Synthetic JSON fixtures and process memory |
| Verification | `pytest`, Flask test client, fake mailbox, simulated Gmail transport |
| Optional Gmail integration | Google API Python client, `google-auth`, `google-auth-httplib2`, and `google-auth-oauthlib` in an optional `gmail` dependency group. [Google Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) |

## Architecture

Flask routes handle forms and render pages. A workflow module owns preview and confirmation. A pure classifier accepts normalized message text and returns a decision. A mailbox interface supplies messages, current labels, and one operation to apply an allowed category. Mock and Gmail implementations share that contract.

```text
pyproject.toml                  Dependencies and test configuration
recruitment_mail/
  __init__.py                   Flask app factory and mode selection
  routes.py                     Start, preview, confirmation, results
  workflow.py                   Run state, selection checks, outcomes
  classify.py                   Rules and fixed category-to-label mapping
  mailbox.py                    Mailbox contract and mock implementation
  gmail.py                      Optional OAuth and Gmail implementation
  fixtures/inbox.json           Fictional demonstration mailbox
  templates/                    Base, start, preview, results
  static/app.css                Layout, typography, focus and status styles
tests/                          Classification, workflow, route and adapter tests
docs/                           Existing six project documents
```

**Classification rules.** Match case-insensitive phrases in the subject and current message text after normalizing whitespace. Use the plain-text MIME part when available, otherwise extract visible text from HTML. Ignore attachments and quoted reply history. A generic word such as “application,” “test,” or “reply” is insufficient on its own.

| Category and exact Gmail label | Positive evidence |
|---|---|
| `Recruitment - Application confirmation` | Explicit acknowledgment such as “we received your application” or “thank you for applying” |
| `Recruitment - Interview invitation` | Invitation to attend, book, or schedule an interview |
| `Recruitment - Assessment invitation` | Invitation to complete a hiring test, coding exercise, or recruitment assessment |
| `Recruitment - Rejection` | Explicit negative hiring decision such as “we will not be moving forward with your application” |
| `Recruitment - Response request` | Recruitment context plus an explicit request to reply, confirm details, or provide information, when no more specific category applies |

A specific invitation or decision takes precedence over a courtesy acknowledgment. If multiple specific invitations or decisions remain plausible, mark the row **Needs review**. A request to act sets the attention flag independently of the category. “No reply needed” suppresses a reply-only signal. A separate instruction to complete an assessment still sets the flag. Unrelated mail contributes only to the scan count.

## Constraints

- **Mock by default.** Mock startup and all automated tests work without credentials or Gmail access. The mock mailbox retains label changes across scans in the same process and resets from fixtures on restart.
- **Dedicated account only.** Explicit live configuration supplies an expected test-account address and desktop OAuth client credentials. Use loopback OAuth with state validation, request `gmail.modify`, and compare the authenticated Gmail profile with the configured address before listing mail. Bind each preview to that account. [Gmail profile reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile)
- **Limit writes at the adapter.** Accept only the five fixed category names. Resolve or create an exact user label after confirmation and add its ID to the individual message with `messages.modify`. Preserve other labels. The OAuth permission is broader than the app’s operation, so verify the outgoing request shape in tests. [Gmail message modification reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/modify)
- **Local security.** Disable Flask debug mode for normal use. Keep credential files outside the repository and OAuth tokens in memory. Use CSRF tokens for form submissions, a random session secret, and an HTTP-only, SameSite session cookie. Keep email content and OAuth tokens out of cookies and logs. Render mail-derived fields as escaped text and discard body text after classification.
- **Bounded state.** Keep the current preview and results server-side, tied to the browser session. A preview expires after 15 minutes or when replaced. A process restart invalidates pending confirmations.

## Decisions and reasons

| Decision | Reason | Alternative considered |
|---|---|---|
| Server-rendered local app | The preview table and confirmed results are easy to demonstrate offline | CLI or separately built JavaScript frontend |
| Deterministic phrase rules | Each classification can be explained with a short fixture and an expected outcome | Model-based classification |
| Message IDs and current mailbox labels for duplicate prevention | They distinguish messages in a thread and reflect changes between runs | Local database of processed messages |
| Confirm individual messages within a batch | One false positive can be deselected while retaining the rest of the run | All-or-nothing batch approval |
