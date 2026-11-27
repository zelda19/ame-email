# Phased implementation

**Ownership.** `coder` owns implementation and automated verification in each phase. Work in a fresh session for the first unchecked phase and tick its tasks only after verification passes. Use `debugger` for a reproducible failure needing isolated diagnosis, `specialist` for a difficult cross-component issue, and `reviewer` for independent inspection when necessary. Each phase uses `tdd` at the public interfaces listed below.

## Phase 1 — Preview a fictional inbox

- [x] Build the Flask app factory, mock mailbox, deterministic classifier, and start and preview screens.
- [x] Include fixtures for all five categories, overlapping invitation and reply language, negative wording, unrelated mail, ambiguous messages, and distinct messages with identical subjects.
- **Verify:** Run `python -m pytest -q` offline. Assert expected categories and attention flags through the classifier interface. Use the Flask test client to verify required preview columns, escaped sender and subject text, unique rows, and zero mailbox writes. Manually open the mock preview and check keyboard navigation.

**Verification record.** Offline `.venv/bin/python -B -m pytest -q` passed all 9 tests. Manual browser and keyboard verification passed (reported by the user).

## Phase 2 — Confirm labels and recover from failures

- [x] Add session-bound previews, checkbox selection, confirmation, cancellation, expiry, and results.
- [x] Implement label rechecks, duplicate-submit protection, conflict handling, and per-message failure reporting.
- **Verify:** Run the full pytest suite. Through the form routes and mock mailbox, exercise cancel, deselection, forged IDs, invalid CSRF, expiry, repeated and concurrent confirmation, and a label added between preview and confirmation. Simulate one successful write, one already-labeled row, and one failed write. Confirm that the counts reconcile and the next run changes only the unresolved message. At this point the complete offline portfolio demo is usable.

**Verification record.** Offline `.venv/bin/python -B -m pytest -q` passed 19 tests. The Flask test client and mock mailbox verified cancellation, deselection, invalid selections, CSRF, session ownership, expiry, replay, concurrent confirmation, label and inbox rechecks, mixed outcomes, interrupted writes, and retry from a fresh preview.

## Phase 3 — Add the optional Gmail adapter and finish the demo

- [x] Implement dedicated-account OAuth, account verification, Gmail message normalization, and confirmed category-label writes. Keep Google dependencies optional for mock users.
- [x] Add mock-transport tests for Gmail requests and document mock startup, the demo sequence, and optional dedicated-account setup in the project README.
- **Verify:** Run `python -m pytest -q` without credentials or network access. Assert that an account mismatch stops before mail access, preview issues only reads, and confirmed writes target the selected message and allowed label. Cover existing and newly created labels, HTML-only mail, permission loss, rate limiting, and a timeout with an uncertain write outcome. Verify mock startup with the Gmail dependency group absent.
- **Optional manual verification:** On the dedicated account, use fictional recruitment messages. Preview two eligible rows, confirm one, inspect both in Gmail, then rescan. The selected message should carry its category label, the deselected message should retain its original labels, and the next preview should identify the completed row. Record this check separately from automated test evidence.

**Verification record.** `.venv/bin/python -B -m pytest -q` passed all 29 tests. The network-restricted run `.venv/bin/python -B -m pytest -q -s -p no:cacheprovider` also passed all 29. Simulated Gmail requests verified profile mismatch, read-only preview, HTML and MIME normalization, exact label creation and reuse, selected-message writes, permission loss, rate limiting, and timeout reconciliation. Mock startup passed with all four Gmail extras absent. Live OAuth and the optional dedicated-account smoke test are pending.

**Corrective review.** Fixed interview availability and booking attention rules,
resolved README merge markers, added isolated OAuth setup and callback failure
tests, reused one Gmail label map per nonempty preview, and documented the actual
mailbox contract. Confirmation still fetches current labels. The full suite
passed all 39 tests with
`unshare -Un sh -c 'readlink /proc/self/ns/net && cat /proc/net/dev /proc/net/route && exec .venv/bin/python -B -m pytest -q'`.
The Linux network namespace had only loopback and an empty IPv4 routing table.
`git diff --check` passed. OAuth tests simulate the provider's state validation
and exercise the app's handling of rejection and timeout. Live OAuth and the
dedicated-account smoke test remain unverified.

**Live smoke test (partial, user-reported).** The Google Cloud project and Gmail
API were configured, OAuth consent was set to External Testing, and the desktop
client JSON was stored outside the repository with permission `600`. The
optional Gmail dependencies installed successfully. The wizard launched Flask,
OAuth succeeded, and the app verified the dedicated Gmail account. A live scan
retrieved 50 messages and correctly categorized the two fictional messages as
Interview invitation and Application confirmation.

The live interview preview showed **Attention required: No** for a request to
confirm availability. Synthetic plain-text and HTML-only Gmail fixtures
reproduced the symptom and retained the full request after MIME extraction.
The classifier now recognizes indirect requests such as “Could you confirm
whether you’re available?” while honoring “No reply needed.” Both synthetic
cases failed before the change. After the fix, all 45 tests passed with
`unshare -Un .venv/bin/python -B -m pytest -q`. The Linux network namespace
provided the network isolation. `git diff --check` passed.

**Pending live verification.** Restart the app and verify the interview now
shows **Attention required: Yes**. After separate approval, apply exactly one
selected label, verify the deselected message retains its original labels,
and rescan to confirm the selected message shows **Already labeled**.

**Live follow-up (user-reported).** After restarting, the interview still showed
**Attention required: No**. Confirmation reported Selected 2, Applied 0,
Already labeled 0, Failed 0, Unverified 2, and Unprocessed 0. These outcomes
do not establish whether Gmail applied either label.

**Offline diagnosis.** The checkout virtual environment imported the corrected
classifier through the Flask workflow and flagged the existing synthetic
availability question. Prior plain-text and HTML-only probes preserved that
question through Gmail normalization. The live process import and exact
fictional message wording and MIME parts were unavailable, so the live
attention cause remains open.

The Gmail client uses a 15-second HTTP timeout, zero Google API request retries,
and zero replays after an authorization challenge in the auth wrapper. The app
rechecks labels and inbox membership, optionally creates the exact user label,
then calls `messages.modify` with only `addLabelIds`. The installed Google API
client emitted the expected requests against fake HTTP. The previous result
collapsed a label creation error, an unexpected create response, and a message
modification timeout into the same text. Fake transports reproduced the two
unverified rows and confirmed the app now reports the stage and a safe reason
without including raw error details. The live cause is still unknown. The
timeout and retry settings were not changed.

**Verification.** All 47 tests passed with
`unshare -Un sh -c 'readlink /proc/self/ns/net && cat /proc/net/dev /proc/net/route && exec .venv/bin/python -B -m pytest -q'`.
The namespace had only loopback and no IPv4 route. `git diff --check` passed.
Live verification remains open. Reconcile both uncertain writes by previewing
again before considering any new label operation.

**Live attention finding (user-confirmed).** Both MIME parts of the original
fictional email contained only “Interview invitation.” Neither part contained
an availability request. The classifier correctly showed **Attention required:
No**. The discrepancy came from the test input, so no application change was
needed. The two unverified label operations and the remaining live label checks
are still open.

**Live Gmail smoke test passed (user-reported).** A fresh scan retrieved 50
messages. The new IT Support interview invitation showed **Attention required:
Yes**. Both earlier uncertain writes reconciled as **Already labeled**. The user
selected one new interview message and reported Applied 1, Failed 0,
Unverified 0, and Unprocessed 0. The Gmail label check and rescan passed.

**UI refinement passed (user-reported).** The user approved the current design
and manually verified Start, Preview, Results, and rescan behavior, including
both visual presentation and functionality.

**Portfolio release preparation.** The README now covers installation,
mock and optional Gmail usage, testing, architecture, security, and known
limitations. The full regression suite passed all 47 tests with
`unshare -Un .venv/bin/python -B -m pytest -q`. `git diff --check` passed.
Git ignore checks confirmed coverage for `.venv/`, Python and pytest caches,
`.env` variants, `credentials.json`, and `token.json`. Alternate names such
as downloaded `client_secret_*.json`, `venv/`, and generated `*.egg-info/`
are not covered by the current rules. Keep all OAuth files outside the
repository. Release version metadata and publication remain pending.

**v1.0 release preparation verified.** Package source metadata is now
`1.0.0`. The README mock command explicitly selects mock mode, and the Flask
CLI accepts the documented launch options. The new Git exclusions cover
`client_secret_*.json`, `venv/`, and `*.egg-info/`. Git reported no tracked
paths covered by ignore rules or matching the additional credential and build
path checks. The full suite passed all 47 tests with
`unshare -Un .venv/bin/python -B -m pytest -q`, using a namespace with only
loopback and no IPv4 routes. `git diff --check` passed. Commit, tag, and
publication are pending.

**v1.0 clean-install verification.** In a temporary copy of the release
worktree, a fresh virtual environment successfully installed the README's
`.[test]` extra in editable mode and reported `recruitment-mail 1.0.0`.
Mock Start returned HTTP 200 through Flask's test client. The documented
`.[gmail]` extra also installed, and `pip check` found no broken requirements.
The Flask CLI loaded the mock app and listed its routes. Both before and after
installing the Gmail extra, all 47 tests passed with
`unshare -Un .venv/bin/python -B -m pytest -q`. No Gmail connection was made.

The tracked and nonignored release paths were checked for credential filenames,
common key and token signatures, and generated artifacts. No matches were
found. `bash -n scripts/gmail-smoke-wizard.sh` and `git diff --check` passed.
The untracked release paths are `recruitment_mail/gmail.py`,
`scripts/gmail-smoke-wizard.sh`, `tests/conftest.py`, `tests/test_gmail.py`,
and `tests/test_gmail_oauth.py`. These belong in the release alongside the
modified tracked files. The index and release refs were left untouched.
