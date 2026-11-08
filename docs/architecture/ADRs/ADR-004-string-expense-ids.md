ADR-004: Expense ids are strings (uuid4 hex)

**Status** Accepted
**Date** 2026-11-08

## Context
SQLite generated integer ids with autoincrement. DynamoDB has no autoincrement, and a counter item would add a write bottleneck and a race condition.

## Decision
Generate the id in the service with `uuid.uuid4().hex`. `id` is a `str` in the API schemas and in URLs (`/expenses/{expense_id}`).

## Consequences
- **+** No coordination between writers; ids are safe to generate anywhere.
- **−** Breaking API change: clients that assumed integers must treat the id as opaque. The frontend only uses it as a key, but the upload result now shows a long hex id.
- **−** uuid4 is not time-sortable; ordering comes from the GSI sort key (the expense date), not from the id.
