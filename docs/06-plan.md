# Phased implementation

**Ownership.** `coder` owns implementation and automated verification in each phase. Work in a fresh session for the first unchecked phase and tick its tasks only after verification passes. Use `debugger` for a reproducible failure needing isolated diagnosis, `specialist` for a difficult cross-component issue, and `reviewer` for independent inspection when necessary. Each phase uses `tdd` at the public interfaces listed below.

## Phase 1 — Preview a fictional inbox

- [ ] Build the Flask app factory, mock mailbox, deterministic classifier, and start and preview screens.
- [ ] Include fixtures for all five categories, overlapping invitation and reply language, negative wording, unrelated mail, ambiguous messages, and distinct messages with identical subjects.
- **Verify:** Run `python -m pytest -q` offline. Assert expected categories and attention flags through the classifier interface. Use the Flask test client to verify required preview columns, escaped sender and subject text, unique rows, and zero mailbox writes. Manually open the mock preview and check keyboard navigation.

**Verification record.** Offline `.venv/bin/python -B -m pytest -q` passed all 9 tests. Manual browser and keyboard verification is pending.

## Phase 2 — Confirm labels and recover from failures

- [ ] Add session-bound previews, checkbox selection, confirmation, cancellation, expiry, and results.
- [ ] Implement label rechecks, duplicate-submit protection, conflict handling, and per-message failure reporting.
- **Verify:** Run the full pytest suite. Through the form routes and mock mailbox, exercise cancel, deselection, forged IDs, invalid CSRF, expiry, repeated and concurrent confirmation, and a label added between preview and confirmation. Simulate one successful write, one already-labeled row, and one failed write. Confirm that the counts reconcile and the next run changes only the unresolved message. At this point the complete offline portfolio demo is usable.

## Phase 3 — Add the optional Gmail adapter and finish the demo

- [ ] Implement dedicated-account OAuth, account verification, Gmail message normalization, and confirmed category-label writes. Keep Google dependencies optional for mock users.
- [ ] Add mock-transport tests for Gmail requests and document mock startup, the demo sequence, and optional dedicated-account setup in the project README.
- **Verify:** Run `python -m pytest -q` without credentials or network access. Assert that an account mismatch stops before mail access, preview issues only reads, and confirmed writes target the selected message and allowed label. Cover existing and newly created labels, HTML-only mail, permission loss, rate limiting, and a timeout with an uncertain write outcome. Verify mock startup with the Gmail dependency group absent.
- **Optional manual verification:** On the dedicated account, use fictional recruitment messages. Preview two eligible rows, confirm one, inspect both in Gmail, then rescan. The selected message should carry its category label, the deselected message should retain its original labels, and the next preview should identify the completed row. Record this check separately from automated test evidence.
