ADR-005: Backend accesses DynamoDB through a dedicated, least-privilege IAM role

**Status** Accepted
**Date** 2026-11-08

## Context
The backend needs AWS credentials to reach DynamoDB, locally now and from ECS later. Using a developer's admin credentials would hide permission problems until deployment.

## Decision
- Terraform module `iam` creates a backend role. Its trust policy currently allows only listed local-dev principals (`local_dev_principal_arns`) to assume it through an AWS CLI profile. An `ecs-tasks.amazonaws.com` statement is added when the backend moves to ECS, and the same role serves as the task role.
- The permissions policy allows only `PutItem`, `GetItem`, `UpdateItem`, `DeleteItem`, `Query` and `BatchWriteItem`, on the table ARN and `<table-arn>/index/*` (a `Query` on a GSI is authorised against the index ARN).
- No `Scan`, no table administration.
- Application code relies on boto3's default credential chain (profile locally, task role on ECS); it never reads keys itself.

## Consequences
- **+** Permission gaps show up in local runs, not only after deploy.
- **+** A leaked backend credential cannot modify infrastructure or read other tables.
- **−** Local runs need an AWS profile that assumes the role.
- **−** Docker containers have no credentials unless `~/.aws` is mounted; running the backend outside Docker is simpler locally.
- Receipt storage (S3) and any parser/Bedrock access will need additional statements.
