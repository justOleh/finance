ADR-006: Test DynamoDB code with moto, not Localstack

**Status** Accepted
**Date** 2026-11-08

## Context
After the move to DynamoDB, tests need a table. Options: moto (in-process mock), Localstack or DynamoDB Local (a container with an HTTP endpoint), or a real test table.

## Decision
Use `moto` (`mock_aws`). A pytest fixture creates a table with the same keys and GSI as the Terraform definition, and tests override the `get_table` dependency. An autouse fixture sets dummy AWS credentials and unsets `AWS_PROFILE` so tests can never reach a real account. Tests cover the service layer directly and the API through `TestClient`.

## Consequences
- **+** Fast, free, no Docker or network; runs the same locally and in CI.
- **+** Supports GSIs, conditional writes and pagination, which is what the code uses.
- **−** It does not model IAM, throttling or index build times; those only surface against real AWS.
- **−** The fixture schema is duplicated from Terraform and must be kept in sync by hand.
- Revisit with DynamoDB Local if a real HTTP endpoint or end-to-end tests are needed.
