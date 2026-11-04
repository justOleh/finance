ADR-001: Migrating the Terraform's state to local file

**Status** Accepted
**Date** 2026-11-04

## Context 
The remote S3 state setup added complexity and a bootstrap problem (the state bucket must exist before Terraform can use it). This is a single-developer personal finance project.

## Decision
Store Terraform state locally and keep the state file out of version control.

## Consequences
- **+** Simpler setup, no bootstrap resources.
- **−** No state locking or sharing, and a lost laptop means lost state.
- Revisit if more contributors join or the infrastructure grows.