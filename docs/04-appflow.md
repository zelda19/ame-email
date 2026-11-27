# Application flow

## Entry points

Launch in mock mode and open the local start page. Optional live mode requires explicit startup configuration and successful account verification. Display the active source before the first scan.

## Journeys

1. **Preview.** Read up to 50 inbox message IDs, deduplicate them, fetch message content and labels, and classify each readable message. Retain display fields and proposed actions in the server-side preview. Report unreadable rows separately. Preview performs no mailbox writes.
2. **Review.** The user can deselect any eligible row. Rows with the intended label are already complete. A different existing app-managed category label makes the row a conflict for manual review. Other Gmail labels do not affect eligibility.
3. **Confirm.** Validate the session, preview, CSRF token, and full selection before any write. Atomically claim the preview so concurrent submissions cannot start a second application. For each selected ID, recheck its current labels and inbox membership, then apply the proposed label if still eligible.
4. **Inspect and retry.** Redirect to results. Refreshing results is read-only. A new preview rereads mailbox state, so previously successful changes and uncertain outcomes are reconciled before the user confirms again.

## Navigation

Start → Preview → Results. Cancel returns to Start and invalidates the preview. Returning to an old browser tab cannot reactivate an expired or consumed confirmation.

## Error paths

| Condition | User-visible behavior |
|---|---|
| Empty inbox or no matches | Show the scan count, explain the empty result, and offer a return to Start. |
| Missing credentials, account mismatch, or scan-wide read failure | Stop the scan, show the cause and recovery step, and offer a fresh preview after correction. |
| Individual message read failure | Count the row as unreadable, exclude it from selection, and continue previewing the rest. |
| Invalid selection, expired preview, or CSRF failure | Reject the submission before writing. Offer a fresh preview. |
| Message disappeared, left the inbox, or acquired a conflicting label | Record the row as unprocessed with a reason and continue. |
| One label operation fails or times out | Continue independent rows. If the outcome is uncertain, identify it as unverified. For Gmail writes, report whether creation or modification was unverified and give a safe reason when available. Recheck mailbox state on the next preview. |
| Authorization loss or account-wide rate limit during confirmation | Stop issuing writes. Preserve completed results, identify the interrupted row, and mark remaining selected rows unprocessed. |
