# Product requirements

## Problem

Recruitment emails mix status updates with requests that need action. A job seeker reviewing an inbox should be able to identify both the kind of message and whether it needs attention, then decide which Gmail labels to apply.

## Users

One job seeker using the app locally. A portfolio reviewer can exercise the complete workflow with a fictional inbox and no Google account.

## MVP features

- Start a scan on demand. Classify individual messages into application confirmation, interview invitation, assessment invitation, rejection, or response request.
- Preview sender, subject, date, proposed category, and **Attention required**. Let the user deselect any proposed change before confirming.
- Apply one category label per confirmed message. The attention flag appears in the preview only.
- Show a run summary, preserve successful changes when another row fails, and allow a fresh preview before retrying.

## Acceptance criteria

- [ ] A fresh mock-mode launch completes preview, confirmation, and results offline.
- [ ] A fixture for each supported category produces its expected label. An interview asking for availability shows **Interview invitation · Attention required: Yes**. An ordinary receipt shows **Application confirmation · Attention required: No**.
- [ ] Previewing, canceling, and deselecting a row cause zero mailbox writes for the affected messages. This includes creating labels.
- [ ] Duplicate IDs, repeated confirmations, and rescans cause no duplicate label application. Two messages with the same subject and different IDs are evaluated independently.
- [ ] A mixed-success run identifies every selected row’s outcome. On a fresh preview, successful rows appear as already labeled and unresolved rows can be reconsidered.
- [ ] The optional Gmail integration verifies the dedicated account before reading messages and applies only the confirmed category labels.

## Exclusions

Deletion, archiving, sending, automatic replies, scheduling, AI classification, additional categories, database storage, and persistent run history are outside v1.

**Planning assumptions for approval.** V1 supports English-language messages, one local user, and a scan of up to 50 inbox messages per run. Ambiguous recruitment messages are visible for manual review and ineligible for labeling. Category overrides and pagination controls are outside the MVP.
