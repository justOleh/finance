ADR-003: Store expenses in DynamoDB (single table with one GSI)

**Status** Accepted (key layout superseded by [ADR-009](ADR-009-cognito-authentication.md))
**Date** 2026-11-08

## Context
The backend used SQLAlchemy with a local SQLite file. That does not work for a containerised service on ECS (ephemeral disk, no shared state), and the goal of the project is to learn cloud-native AWS. Required access patterns: get/update/delete by id, list by date range (newest first) with an optional store filter, and a monthly summary.

## Decision
- Replace SQLAlchemy/SQLite with boto3 and one DynamoDB table (`app`, on-demand billing), provisioned by Terraform.
- Item key: `pk = EXPENSE#<id>`, `sk = META`.
- One GSI, `gsi1`: `gsi1pk = EXPENSES` (constant), `gsi1sk = <yyyy-mm-dd>#<id>`. A date range is a single `Query`.
- Store search is a case-insensitive substring match using a lowercase `store_lower` attribute and a `FilterExpression`.
- Monthly summary is aggregated in Python from a date-range query.
- Numbers are converted to `Decimal` on write and back on read; dates are ISO strings; `items` is a native list of maps.
- The table name is configuration (`DYNAMODB_TABLE_NAME`, from `terraform output -raw app_table_name`), never hard-coded.

## Consequences
- **+** No server to run; pay per request (cents at personal scale); no idle cost.
- **+** The service is stateless and can run on ECS or Lambda unchanged.
- **−** A constant GSI partition key is a hot partition; fine for one user, not for multi-tenant scale.
- **−** Store filtering and monthly aggregation read more data than they return; acceptable at this size, revisit with pre-aggregated items if data grows.
- **−** Updating an item is read-modify-write (the date is part of the GSI sort key).
- **−** Existing SQLite data is not migrated.
- Adding a GSI to an existing table is asynchronous; the code fails with "table does not have the specified index" until the index is `ACTIVE`.
