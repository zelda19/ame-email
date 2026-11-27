# Agent guide

Detailed requirements live in `docs/`. Do not duplicate them here.

## What to read first

| Task | Read |
|---|---|
| Any implementation | `docs/01-prd.md`, `docs/06-plan.md` |
| Architecture, stack, dependencies | `docs/02-trd.md` |
| UI changes | `docs/03-design.md`, `docs/04-appflow.md` |
| Data or API changes | `docs/05-schema.md` |

## Rules

- Work only on the current unchecked phase in `docs/06-plan.md`.
- Don't add features or dependencies that aren't in the PRD/TRD. Ask first.
- `TBD` means unknown: ask, don't guess. `Not applicable` means skip it.
- If behavior changes, update the affected docs in the same change.
- Tick a plan checkbox only after its verification passes.
