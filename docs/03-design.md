# Interface design

## Screens

| Screen | Content and action |
|---|---|
| Start | Show **Mock inbox** or **Dedicated Gmail test account**, the verified account address in live mode, the scan limit, and **Preview inbox**. |
| Preview | Show the scan count and a table with selection, sender, subject, received date, proposed category, attention, and status. Eligible rows start checked. **Apply selected labels** confirms the checked rows. **Cancel** discards the preview. |
| Results | Show selected, applied, already labeled, failed or unverified, and unprocessed counts. Identify affected rows and give a recovery action. **Preview again** starts a fresh scan. |

## Components

Use native checkboxes, buttons, table headings, and a text status message. Give each checkbox an accessible name that identifies its message. Show **Needs review**, **Already labeled**, and **Conflicting label** rows as nonselectable, with a short explanation. An empty preview has one action to return to Start.

## Visual rules

Use a system sans-serif font, light background, dark text, and one accent color for the confirmation action. Allow long subjects to wrap. Align dates and statuses consistently, and show a timezone with the received date. On small screens, keep the table in a horizontally scrollable region.

## Accessibility

Provide visible keyboard focus, logical tab order, labeled controls, and text for every status. Use **Yes** and **No** for attention. Associate errors with the affected form or row. All actions work with a keyboard and with JavaScript disabled.
